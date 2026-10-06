from typing import Annotated, Any, Dict, List, Optional, TypedDict
from langgraph.graph.message import add_messages


class State(TypedDict):
  user_id: str
  messages: Annotated[list, add_messages]
  user_profile: Dict[str, Any]
  structured_profile: Dict[str, Any]
  raw_jobs: List[Dict[str, Any]]
  scored_jobs: List[Dict[str, Any]]
  tailored_assets: Dict[
      str, str
  ]  # Stores generated cover letters or resume highlights
  route_intent: str  # "chat" or "job_search" — decided by the router node
  chat_response: str  # The LLM's conversational reply when route_intent is "chat"
  time_filter: str  # Serper time filter: "qdr:d" (24h), "qdr:w" (1 week), "qdr:m" (1 month)
  selected_jobs: List[Dict[str, Any]]  # Jobs the user selected from the card UI
  application_results: List[Dict[str, Any]]  # Results from auto-apply agent (per job: success, status, log)