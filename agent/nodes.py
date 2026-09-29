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

def job_search_agent(state: State):
  """Stage 1: Job Discovery Agent (Dynamic Vector-Driven Search)."""
  user_id = state.get("user_id", "anonymous")
  structured_profile = state.get('structured_profile', {})
  
  user_intent = state["messages"][0].content if state["messages"] else "Find jobs"
  
  profile_query = "core skills job titles industries current role"
  query_vector = vector_store.embeddings.embed_query(profile_query)
  
  vector_results = vector_store.collection.query(
      query_embeddings=[query_vector],
      n_results=2,
      where={"user_id": user_id}
  )
  
  retrieved_chunks = vector_results.get("documents", [[]])[0]
  actual_user_profile = "\n".join(retrieved_chunks) if retrieved_chunks else "No resume uploaded."

  preferred_titles = structured_profile.get('preferred_job_titles') or "Data Analyst"
  preferred_locations = structured_profile.get('preferred_locations') or "Thailand"

  # 1. Ask LLM to determine the best search keyword based on the profile
  keyword_prompt = f"""
    User intent: "{user_intent}"
    Preferred Titles: "{preferred_titles}"
    
    Output exactly ONE short job title to use as a search query on LinkedIn (e.g., Data Scientist). Do not add any quotes or extra text.
  """
  keyword_res = llm.invoke([HumanMessage(content=keyword_prompt)])
  search_keyword = extract_text_from_response(keyword_res.content).strip()

  # 2. Call the tool to fetch real LinkedIn jobs
  from tools.job_tools import search_linkedin_jobs
  tool_results = search_linkedin_jobs.invoke({"keyword": search_keyword, "location": preferred_locations})
  print(f"Serper API results for {search_keyword}:", tool_results)

  # 3. Ask LLM to parse the real results into a JSON array
  parse_prompt = f"""
    You are extracting real job postings into JSON.
    
    Here are the actual LinkedIn search results:
    {tool_results}
    
    Task:
    Extract up to 3 jobs from these results. If the results show an API error or no results, fallback to generating 1-2 realistic mock jobs based on: {search_keyword}.
    
    You MUST respond with a JSON array of objects. Each object must have exactly these keys:
    - "title": The job title (from the results).
    - "company": The company name (extract it from the title or snippet, e.g. if title says "at Google", company is Google. If unknown, use "Unknown Company").
    - "snippet": A 2-3 sentence description from the snippet.
    - "link": The actual URL link provided in the results (or '#' if mock).
    
    DO NOT output anything other than the JSON array. Do not include markdown codeblocks, just the JSON.
    """
    
  response = llm.invoke([HumanMessage(content=parse_prompt)])
  content_text = extract_text_from_response(response.content)
  
  try:
      if content_text.startswith("```json"):
          content_text = content_text[7:-3]
      elif content_text.startswith("```"):
          content_text = content_text[3:-3]
      raw_jobs = json.loads(content_text.strip())
  except Exception as e:
      raw_jobs = [
          {"title": f"{search_keyword} Role", "company": "Unknown", "snippet": str(content_text), "link": "#"}
      ]

  return {
      "messages": [HumanMessage(content=f"Found {len(raw_jobs)} matching roles for {search_keyword}.")],
      "raw_jobs": raw_jobs,
  }

def matching_screening_agent(state: State):
  """Stage 2: Matching & Screening Agent (Dynamic Multi-User)."""
  user_id = state.get("user_id", "anonymous")
  structured_profile = state.get('structured_profile', {})
  raw_jobs = state.get('raw_jobs', [])
  
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

  prompt = f"""
    You are an expert Technical Recruiter and Matching Agent.
    
    Candidate Profile (Extracted from CV):
    {actual_user_profile}

    Structured Profile:
    University: {university} | Degree: {degree} | GPA: {gpa} | Skills: {skills}
    
    Target Jobs:
    {json.dumps(raw_jobs, indent=2, ensure_ascii=False)}
    
    Task:
    Analyze how well the candidate fits EACH of the Target Jobs.
    
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
    Select the absolute #1 top-matching job from the evaluation above and write:
    1. **Tailored Cover Letter**: 3 paragraphs addressing the exact problems using the candidate's actual projects.
    2. **Resume Bullet Points**: 3 high-impact resume bullet points.
    
    Format the output cleanly in markdown.
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
  print("🛑 [PAUSED] STAGE 4: HUMAN-IN-THE-LOOP REVIEW")
  print("=" * 60)
  print(assets)
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

    print("\n" + "✨" * 30)
    print("✅ STAGE 5: Application successfully logged to tracker!")
    print(f"📁 Saved to: {tracker_file}")
    print("✨" * 30)

  except Exception as e:
    print(f"Warning: Could not save to tracker file: {e}")

  return {
      "messages": [(
          "system",
          "Application approved and successfully logged by Tracker Agent.",
      )]
  }