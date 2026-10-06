import sys
import os
import json
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

from agent.nodes import llm, extract_text_from_response
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

keyword_res = llm.invoke([HumanMessage(content=keyword_prompt)])
raw_response = extract_text_from_response(keyword_res.content).strip()
print("raw:", repr(raw_response))

try:
    if raw_response.startswith("```json"):
        raw_response = raw_response[7:-3]
    elif raw_response.startswith("```"):
        raw_response = raw_response[3:-3]
    search_data = json.loads(raw_response.strip())
    print("Parsed data:", search_data)
except Exception as e:
    print("Failed to parse JSON:", str(e))
