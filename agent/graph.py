# agent/graph.py
from agent.nodes import job_search_agent
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from tools import ALL_TOOLS  # Import clean tool array

workflow = StateGraph(State)

# Add nodes using the separated tools
workflow.add_node("agent", job_search_agent)
workflow.add_node("tools", ToolNode(ALL_TOOLS))

# ... wire up edges and compile graph ...