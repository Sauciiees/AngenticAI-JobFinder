from agent.nodes import (
    application_tracker_node,
    asset_tailoring_agent,
    auto_apply_node,
    conversational_router,
    general_chat_node,
    human_approval_node,
    job_search_agent,
    job_selection_node,
    matching_screening_agent,
)
from agent.state import State
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from tools import ALL_TOOLS


def route_by_intent(state: State):
  """Conditional edge: routes to chat or job pipeline based on classified intent."""
  intent = state.get("route_intent", "chat")
  if intent == "job_search":
    return "job_discovery_agent"
  else:
    return "general_chat_node"


workflow = StateGraph(State)

# 1. Add all nodes
workflow.add_node("conversational_router", conversational_router)
workflow.add_node("general_chat_node", general_chat_node)
workflow.add_node("job_discovery_agent", job_search_agent)
workflow.add_node("job_selection_node", job_selection_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))
workflow.add_node("matching_screening_agent", matching_screening_agent)
workflow.add_node("asset_tailoring_agent", asset_tailoring_agent)
workflow.add_node("human_approval_node", human_approval_node)
workflow.add_node("auto_apply_node", auto_apply_node)
workflow.add_node("application_tracker_node", application_tracker_node)

# 2. Entry point: always go to the router first
workflow.add_edge(START, "conversational_router")

# 3. Router decides: chat or job search pipeline
workflow.add_conditional_edges(
    "conversational_router",
    route_by_intent,
    {
        "general_chat_node": "general_chat_node",
        "job_discovery_agent": "job_discovery_agent",
    },
)

# 4. Chat node ends the conversation
workflow.add_edge("general_chat_node", END)

# 5. Job search pipeline:
#    Discovery -> Selection (interrupt) -> Matching -> Tailoring -> Human Review -> Auto Apply -> Tracker
workflow.add_edge("job_discovery_agent", "job_selection_node")
workflow.add_edge("job_selection_node", "matching_screening_agent")
workflow.add_edge("matching_screening_agent", "asset_tailoring_agent")
workflow.add_edge("asset_tailoring_agent", "human_approval_node")
workflow.add_edge("human_approval_node", "auto_apply_node")
workflow.add_edge("auto_apply_node", "application_tracker_node")
workflow.add_edge("application_tracker_node", END)

# 6. Compile graph with checkpointer
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# Create or connect to the checkpoint database
conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
memory = SqliteSaver(conn)
app = workflow.compile(checkpointer=memory)