from agent.nodes import (
    application_tracker_node,
    asset_tailoring_agent,
    human_approval_node,
    job_search_agent,
    matching_screening_agent,
)
from agent.state import State
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from tools import ALL_TOOLS

workflow = StateGraph(State)

# 1. Add all 5 nodes
workflow.add_node("job_discovery_agent", job_search_agent)
workflow.add_node("tools", ToolNode(ALL_TOOLS))
workflow.add_node("matching_screening_agent", matching_screening_agent)
workflow.add_node("asset_tailoring_agent", asset_tailoring_agent)
workflow.add_node("human_approval_node", human_approval_node)
workflow.add_node("application_tracker_node", application_tracker_node)

# 2. Define full 5-stage pipeline flow
workflow.add_edge(START, "job_discovery_agent")

workflow.add_conditional_edges(
    "job_discovery_agent",
    tools_condition,
    {"tools": "tools", END: "matching_screening_agent"},
)

workflow.add_edge("tools", "job_discovery_agent")
workflow.add_edge("job_discovery_agent", "matching_screening_agent")
workflow.add_edge("matching_screening_agent", "asset_tailoring_agent")
workflow.add_edge("asset_tailoring_agent", "human_approval_node")

# Route human review directly to Stage 5 tracker upon approval
workflow.add_edge("human_approval_node", "application_tracker_node")
workflow.add_edge("application_tracker_node", END)

# 3. Compile graph with checkpointer
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)