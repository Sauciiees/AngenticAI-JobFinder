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


def job_search_agent(state: State):
  """Stage 1: Job Discovery Agent (Dynamic Vector-Driven Search)."""
  user_id = state.get("user_id", "anonymous")
  
  # 1. Get the user's intent from the frontend (e.g., location or preference)
  user_intent = state["messages"][0].content if state["messages"] else "Find jobs"
  
  # 2. Fetch the candidate's core skills and titles from ChromaDB
  profile_query = "core skills job titles industries current role"
  query_vector = vector_store.embeddings.embed_query(profile_query)
  
  vector_results = vector_store.collection.query(
      query_embeddings=[query_vector],
      n_results=2, # Just need a quick summary of who they are
      where={"user_id": user_id}
  )
  
  retrieved_chunks = vector_results.get("documents", [[]])[0]
  actual_user_profile = (
      "\n".join(retrieved_chunks)
      if retrieved_chunks
      else "No resume uploaded."
  )

  # 3. Ask the LLM to write a targeted Google/Serper search query
  query_prompt = f"""
    You are an expert technical recruiter sourcing roles.
    
    User's Request/Preferences: "{user_intent}"
    Candidate's Actual CV Highlights: {actual_user_profile}
    
    Task:
    Generate a highly targeted Google Search query to find live job postings on LinkedIn that match this exact candidate.
    Use boolean operators to maximize relevance based on their actual background.
    Example format: site:linkedin.com/jobs "Job Title" ("Skill 1" OR "Skill 2") "Location"
    
    ONLY output the search string. Do not include quotes around the entire string, and do not provide any other text.
    """
    
  chain = llm | StrOutputParser()
  refined_search_query = chain.invoke([HumanMessage(content=query_prompt)]).strip()
  
  print(f"🔍 Optimized Search Query for {user_id}: {refined_search_query}")

  # 4. Execute your actual search tool (Serper API) using the optimized query
  # raw_jobs = your_search_tool_function(refined_search_query)
  
  # Mocking the job response for demonstration
  dummy_jobs = [
      {"title": "Role based on dynamic search", "snippet": "...", "link": "#"}
  ]

  # We append an AI message so the next nodes know what search was executed
  return {
      "messages": [HumanMessage(content=f"Executed search using: {refined_search_query}")],
      "raw_jobs": dummy_jobs,
  }


def matching_screening_agent(state: State):
  """Stage 2: Matching & Screening Agent (Dynamic Multi-User)."""
  user_id = state.get("user_id", "anonymous")
  
  # Extract raw jobs from message history or state
  last_message = state["messages"][-1]
  content_text = last_message.content if hasattr(last_message, "content") else str(last_message)
  dummy_jobs = [{"title": "Target Role", "snippet": content_text, "link": "#"}]
  
  # 1. Fetch the user's ACTUAL background from the Vector DB
  # We use a broad query to capture their general skills and education
  profile_query = "education background skills work experience projects"
  query_vector = vector_store.embeddings.embed_query(profile_query)
  
  vector_results = vector_store.collection.query(
      query_embeddings=[query_vector],
      n_results=4,
      where={"user_id": user_id}  # Ensure we only pull THIS user's CV
  )
  
  retrieved_chunks = vector_results.get("documents", [[]])[0]
  actual_user_profile = (
      "\n".join(retrieved_chunks)
      if retrieved_chunks
      else f"No resume documents uploaded yet for user {user_id}."
  )

  # 2. Evaluate the jobs against the dynamic profile
  prompt = f"""
    You are an expert Technical Recruiter and Matching Agent.
    
    Here is the Candidate's Actual Profile (Extracted from their uploaded CV):
    {actual_user_profile}
    
    Here are the target jobs to evaluate:
    {dummy_jobs}
    
    Task:
    1. Analyze these jobs against the candidate's actual skills and experience.
    2. Assign a match percentage score (0-100%).
    3. Provide a brief breakdown of matching strengths and missing skills.
    
    Format your response cleanly in markdown.
    """

  response = llm.invoke([HumanMessage(content=prompt)])

  return {
      "messages": [response],
      "scored_jobs": [{"evaluation": response.content}],
  }

def asset_tailoring_agent(state: State):
  """Stage 3: Asset Tailoring Agent (Multi-User Safe)."""
  
  # 1. Safely extract user_id from the state
  user_id = state.get("user_id", "anonymous")
  
  scored_jobs = state.get("scored_jobs", [])
  evaluation_text = (
      scored_jobs[-1]["evaluation"]
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

  prompt = f"""
    You are an expert Career Coach and Professional Resume Writer.
    
    Here is the Candidate's Real Profile (Retrieved via Vector DB):
    {user_background_context}
    
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