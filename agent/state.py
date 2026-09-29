from typing import Annotated, Any, Dict, List, TypedDict
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