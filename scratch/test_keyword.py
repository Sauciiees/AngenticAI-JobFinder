import sys
import os
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

from agent.nodes import llm
from langchain_core.messages import HumanMessage

keyword_prompt = f"""
    User intent: "search for AI Engineer jobs located in bangkok"
    Preferred Titles: "Data Analyst"
    Preferred Locations: "Thailand"
    
    Extract the job title and location the user wants to search for based on their intent.
    If they didn't specify a title, use the Preferred Titles.
    If they didn't specify a location, use the Preferred Locations.
    
    Respond strictly in JSON format like this:
    {{"title": "AI Engineer", "location": "Bangkok"}}
"""

res = llm.invoke([HumanMessage(content=keyword_prompt)])
print("RAW RESPONSE:")
print(repr(res.content))
