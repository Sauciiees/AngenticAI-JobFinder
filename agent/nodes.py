import os
from agent import state
from agent.state import State
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tools import ALL_TOOLS
from langgraph.types import interrupt
from agent.vector_store import index_and_search_jobs
from agent.vector_store import vector_store
from langchain_core.output_parsers import StrOutputParser

# Initialize Gemini models (using a stable model version)
llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.2)
llm_with_tools = llm.bind_tools(ALL_TOOLS)

import json

def extract_text_from_response(content):
    if isinstance(content, list):
        if len(content) > 0 and isinstance(content[0], dict) and "text" in content[0]:
            return content[0]["text"]
    elif isinstance(content, str):
        return content
    return str(content)


def conversational_router(state: State):
  """Router Node: Decides if the user wants general chat or job-search actions.
  
  Acts as the entry point. Classifies the user's intent and routes accordingly.
  """
  user_message = ""
  if state["messages"]:
    last_msg = state["messages"][-1]
    user_message = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

  classification_prompt = f"""You are an intent classifier for a Job Finder AI assistant.

The user said: "{user_message}"

Classify the user's intent into exactly ONE of these categories:
- "job_search": The user EXPLICITLY wants to trigger a job search, look for open job listings, or apply to specific positions (e.g. "Find me jobs", "Search for Data Scientist roles", "Apply to Google").
- "chat": The user is asking for career advice, asking what you think about their CV/resume, asking for feedback on their skills, making general conversation, or asking questions.

Respond with ONLY the single word: job_search OR chat
Do not add any other text."""

  response = llm.invoke([HumanMessage(content=classification_prompt)])
  intent = extract_text_from_response(response.content).strip().lower()

  # Default to chat if the classification is unclear
  if "job_search" in intent:
    route = "job_search"
  else:
    route = "chat"

  return {
      "route_intent": route,
  }


def general_chat_node(state: State):
  """General Chat Node: Career Advisor Chatbot.
  
  This node responds to casual questions, career advice, and resume feedback.
  It loads the user's CV from the vector store so it knows their background.
  """
  # Build conversation history for context
  chat_history = []
  for msg in state["messages"]:
    if hasattr(msg, "content"):
      role = "user" if msg.type == "human" else "assistant"
      chat_history.append(f"{role}: {msg.content}")

  history_text = "\n".join(chat_history[-10:])  # Last 10 messages for context

  user_id = state.get("user_id", "anonymous")
  structured_profile = state.get("structured_profile", {})
  user_name = structured_profile.get("full_name", "there")
  
  # Fetch the user's uploaded CV from the vector database
  from agent.vector_store import vector_store
  vector_results = vector_store.collection.get(
      where={"user_id": user_id}
  )
  retrieved_chunks = vector_results.get("documents", [[]])[0]
  actual_user_profile = "\n".join(retrieved_chunks) if retrieved_chunks else "No resume documents uploaded yet."

  prompt = f"""You are an expert Career Advisor and AI Assistant called "JobFinder AI". 
You are speaking with {user_name}.

Here is their uploaded CV/Resume content:
{actual_user_profile}

Here is their manually entered profile:
{json.dumps(structured_profile, ensure_ascii=False, indent=2)}

Your Job:
1. Act as a career advisor. Answer their questions about their career, resume, skills, or what roles they should apply for based on their CV.
2. If they ask about their CV or profile, use the information provided above.
3. If they want to search for actual live jobs, tell them to explicitly ask you to "Search for jobs" and the system will automatically run the job search pipeline for them.
4. Be friendly, concise, and highly constructive. If they speak Thai, answer in Thai. If in English, answer in English.

Recent conversation:
{history_text}
"""

  response = llm.invoke([HumanMessage(content=prompt)])
  chat_text = extract_text_from_response(response.content)

  return {
      "messages": [response],
      "chat_response": chat_text,
  }

def job_search_agent(state: State):
  """Stage 1: Job Discovery Agent — fetches ALL jobs from 4 platforms with time filter."""
  user_id = state.get("user_id", "anonymous")
  structured_profile = state.get('structured_profile', {})
  time_filter = state.get("time_filter", "qdr:w")  # Default: past week
  # Get the LATEST message from the user
  user_intent = ""
  if state["messages"]:
      last_msg = state["messages"][-1]
      user_intent = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
  
  preferred_titles = structured_profile.get('preferred_job_titles') or "Data Analyst"
  preferred_locations = structured_profile.get('preferred_locations') or "Thailand"

  # 1. Ask LLM to determine the best search keyword based on the profile
  keyword_prompt = f"""
    User intent: "{user_intent}"
    Preferred Titles (from profile fallback): "{preferred_titles}"
    Preferred Locations (from profile fallback): "{preferred_locations}"
    
    You are a job search assistant. 
    Analyze the 'User intent'. If the user mentions a field (e.g. "marketing", "ai engineer"), translate it into the most appropriate, professional job title for a search query.
    
    IMPORTANT: Only use the "Preferred Titles" if the User intent is completely empty or highly generic (e.g., "find me a job"). Do NOT force the user into their Preferred Title if they asked for something else.
    
    Respond strictly in JSON format like this:
    {{"title": "AI Engineer", "location": "Bangkok"}}
  """
  keyword_res = llm.invoke([HumanMessage(content=keyword_prompt)])
  raw_response = extract_text_from_response(keyword_res.content).strip()
  
  try:
      import re
      match = re.search(r'\{.*\}', raw_response, re.DOTALL)
      if match:
          search_data = json.loads(match.group(0))
          search_keyword = search_data.get("title", preferred_titles)
          search_location = search_data.get("location", preferred_locations)
      else:
          search_keyword = preferred_titles
          search_location = preferred_locations
  except Exception:
      search_keyword = preferred_titles
      search_location = preferred_locations

  from tools.linkedin_search import linkedin_direct_search
  from tools.jobsdb_search import jobsdb_direct_search
  from tools.job_tools import _serper_search_structured
  
  all_jobs = []
  
  # 1. LinkedIn (Direct Search for perfect data)
  safe_kw = search_keyword.encode('ascii', 'ignore').decode('ascii')
  print(f"Direct searching LinkedIn for {safe_kw}...")
  all_jobs.extend(linkedin_direct_search(search_keyword, search_location, time_filter, 10))
  
  # 2. JobsDB (Direct Search via Playwright in a separate thread)
  print(f"Direct searching JobsDB for {safe_kw}...")
  from concurrent.futures import ThreadPoolExecutor
  with ThreadPoolExecutor(max_workers=1) as executor:
      future = executor.submit(jobsdb_direct_search, search_keyword, search_location, 5)
      try:
          all_jobs.extend(future.result())
      except Exception as e:
          print(f"Failed to run JobsDB search thread: {e}")
  
  # 3. Other platforms (via Serper)
  platforms = [
      ("indeed.com/viewjob", "Indeed"),
      ("jobbkk.com/jobs/detail", "JobBKK"),
  ]
  
  for site, platform_name in platforms:
    results = _serper_search_structured(
        keyword=search_keyword,
        location=search_location,
        site=site,
        platform_name=platform_name,
        time_filter=time_filter,
        num=5, # Reduce to 5 for others to keep cards clean
    )
    all_jobs.extend(results)
    
  from tools.scraper import enrich_jobs_with_scraper
  print("Enriching jobs with async scraper...")
  all_jobs = enrich_jobs_with_scraper(all_jobs)
  
  safe_kw = search_keyword.encode('ascii', 'ignore').decode('ascii')
  print(f"Total jobs found for '{safe_kw}': {len(all_jobs)}")

  return {
      "messages": [HumanMessage(content=f"Found {len(all_jobs)} jobs for '{search_keyword}' across LinkedIn, Indeed, JobsDB, and JobBKK.")],
      "raw_jobs": all_jobs,
  }


def job_selection_node(state: State):
  """Stage 1.5: Pauses so the user can review job cards and select which ones to process.
  
  Uses LangGraph interrupt to pause execution. The frontend displays job cards
  and sends back the user's selected jobs as a list of indices.
  """
  raw_jobs = state.get("raw_jobs", [])
  
  # Interrupt and wait for user to select jobs
  selected_indices = interrupt({
      "question": "Please select the jobs you want to apply to.",
      "jobs": raw_jobs,
  })
  
  # selected_indices is a list of integer indices the user picked
  if isinstance(selected_indices, list):
    selected_jobs = [raw_jobs[i] for i in selected_indices if i < len(raw_jobs)]
  else:
    # Fallback: if something unexpected comes back, use all jobs
    selected_jobs = raw_jobs

  return {
      "messages": [HumanMessage(content=f"User selected {len(selected_jobs)} jobs for matching.")],
      "selected_jobs": selected_jobs,
  }

def matching_screening_agent(state: State):
  """Stage 2: Matching & Screening Agent (Dynamic Multi-User)."""
  user_id = state.get("user_id", "anonymous")
  structured_profile = state.get('structured_profile', {})
  raw_jobs = state.get('selected_jobs', []) or state.get('raw_jobs', [])
  
  profile_query = "education background skills work experience projects"
  query_vector = vector_store.embeddings.embed_query(profile_query)
  
  vector_results = vector_store.collection.query(
      query_embeddings=[query_vector],
      n_results=4,
      where={"user_id": user_id}
  )
  
  retrieved_chunks = vector_results.get("documents", [[]])[0]
  actual_user_profile = "\n".join(retrieved_chunks) if retrieved_chunks else f"No resume documents uploaded yet for user {user_id}."

  university = structured_profile.get('university') or "Not specified"
  degree = structured_profile.get('degree') or "Not specified"
  gpa = structured_profile.get('gpa') or "Not specified"
  skills = structured_profile.get('skills') or "Not specified"

  from tools.scraper import scrape_job_description

  # Try to extract the full Job Description by scraping the URL for the selected jobs
  # (No longer needed here since job_search_agent now async scrapes ALL jobs upfront)

  prompt = f"""
    You are an expert Technical Recruiter and Matching Agent.
    
    Candidate Profile (Extracted from CV):
    {actual_user_profile}

    Structured Profile:
    University: {university} | Degree: {degree} | GPA: {gpa} | Skills: {skills}
    
    Target Jobs (with Full Job Descriptions):
    {json.dumps(raw_jobs, indent=2, ensure_ascii=False)}
    
    Task:
    Analyze how well the candidate fits EACH of the Target Jobs. Analyze the 'full_jd' for specific requirements, technologies, and years of experience.
    
    You MUST respond with a JSON array of objects, one for each job. Each object must have exactly these keys:
    - "title": The job title (from Target Jobs).
    - "company": The company name (from Target Jobs).
    - "match_score": A percentage score of how well they match (e.g., "92").
    - "details": Explain WHY they match, referencing specific skills from their CV versus the job snippet.
    - "link": The exact link URL provided in Target Jobs.
    
    DO NOT output anything other than the JSON array. Do not include markdown codeblocks, just the JSON.
    """

  response = llm.invoke([HumanMessage(content=prompt)])
  content_text = extract_text_from_response(response.content)

  try:
      if content_text.startswith("```json"):
          content_text = content_text[7:-3]
      elif content_text.startswith("```"):
          content_text = content_text[3:-3]
      scored_jobs = json.loads(content_text.strip())
      
      # Merge original job data (like logo_url and link) back in to preserve them for the frontend
      for sj in scored_jobs:
          for orig in raw_jobs: # raw_jobs here actually holds selected_jobs
              if sj.get("title") == orig.get("title") and sj.get("company") == orig.get("company"):
                  sj["logo_url"] = orig.get("logo_url", "")
                  sj["link"] = orig.get("link", "")
                  break
                  
  except Exception as e:
      scored_jobs = [{"title": "Parse Error", "company": "Unknown", "match_score": "0", "details": str(content_text)}]

  return {
      "messages": [response],
      "scored_jobs": scored_jobs,
  }

def asset_tailoring_agent(state: State):
  """Stage 3: Asset Tailoring Agent (Multi-User Safe)."""
  
  # 1. Safely extract user_id from the state
  user_id = state.get("user_id", "anonymous")
  structured_profile = state.get('structured_profile', {})
  
  scored_jobs = state.get("scored_jobs", [])
  
  import json
  evaluation_text = (
      json.dumps(scored_jobs, indent=2, ensure_ascii=False)
      if scored_jobs
      else "No specific job evaluation found."
  )

  # 2. Embed the query and filter ChromaDB by user_id
  query = "Python PyTorch LangChain Azure Docker Data Science AI projects experience"
  query_vector = vector_store.embeddings.embed_query(query)
  
  # We query the collection directly to pass the 'where' metadata filter
  vector_results = vector_store.collection.query(
      query_embeddings=[query_vector],
      n_results=4,
      where={"user_id": user_id}  # THE MAGIC FILTER!
  )

  retrieved_chunks = vector_results.get("documents", [[]])[0]
  user_background_context = (
      "\n".join(retrieved_chunks)
      if retrieved_chunks
      else f"No resume documents uploaded yet for user {user_id}."
  )

  full_name = structured_profile.get('full_name') or "Applicant"
  university = structured_profile.get('university') or "Not specified"

  prompt = f"""
    You are an expert Career Coach and Professional Resume Writer.
    
    Here is the Candidate's Real Profile (Retrieved via Vector DB):
    {user_background_context}

    Candidate Name: {full_name}
    University: {university}
    
    Here is the recent job evaluation:
    {evaluation_text}
    
    Task:
    For EVERY job in the evaluation above, write:
    1. **Tailored Cover Letter**: 3 paragraphs addressing the exact problems using the candidate's actual projects.
    2. **Resume Bullet Points**: 3 high-impact resume bullet points.
    
    Format the output cleanly in markdown.
    IMPORTANT: Separate each job's assets clearly with a header like "### 📄 [Job Title] at [Company]".
    """

  response = llm.invoke([HumanMessage(content=prompt)])

  return {
      "messages": [response],
      "tailored_assets": {"top_job_assets": response.content},
  }
def human_approval_node(state: State):
  """Stage 4: Human-in-the-Loop Review.

  Pauses execution so the user can review the generated cover letter and assets
  before final submission or logging.
  """
  assets = state.get("tailored_assets", {}).get(
      "top_job_assets", "No assets generated."
  )

  print("\n" + "=" * 60)
  print("[PAUSED] STAGE 4: HUMAN-IN-THE-LOOP REVIEW")
  print("=" * 60)
  try:
      print(assets.encode('ascii', 'ignore').decode('ascii'))
  except Exception:
      print("Assets successfully generated (omitted from terminal due to encoding constraints).")
  print("=" * 60)

  # LangGraph interrupt pauses execution and waits for external input
  user_decision = interrupt({
      "question": (
          "Do you approve these assets? Type 'approve' to proceed, or provide"
          " feedback for changes:"
      ),
      "assets": assets,
  })

  return {
      "messages": [(
          "user",
          f"Human Review Decision: {user_decision}",
      )]
  }

def application_tracker_node(state: State):
  """Stage 5: Application Tracker Agent.

  Logs approved applications and assets into a local tracking history file.
  """
  import json
  from datetime import datetime
  user_id = state.get("user_id", "anonymous")

  # Safely extract raw assets from state
  raw_assets = state.get("tailored_assets", {}).get(
      "top_job_assets", "No assets generated."
  )

  # Normalize assets into a plain string regardless of whether it's a list or str
  if isinstance(raw_assets, list):
    assets_str = " ".join(
        item.get("text", str(item)) if isinstance(item, dict) else str(item)
        for item in raw_assets
    )
  else:
    assets_str = str(raw_assets)

  log_entry = {
      "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
      "status": "APPROVED",
      "assets_preview": assets_str[:200] + "...",  # Safe string slice
  }

  tracker_file = f"tracker_{user_id}.json"
  try:
    try:
      with open(tracker_file, "r", encoding="utf-8") as f:
        history = json.load(f)
    except FileNotFoundError:
      history = []

    history.append(log_entry)

    with open(tracker_file, "w", encoding="utf-8") as f:
      json.dump(history, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 30)
    print(" STAGE 5: Application successfully logged to tracker!")
    print(f"Saved to: {tracker_file}")
    print("=" * 30)

  except Exception as e:
    print(f"Warning: Could not save to tracker file: {e}")

  return {
      "messages": [(
          "system",
          "Application approved and successfully logged by Tracker Agent.",
      )]
  }