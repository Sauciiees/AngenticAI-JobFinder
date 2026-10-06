import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

user_intent = "marketing job in thailand"
preferred_titles = "Data Analyst"
preferred_locations = "Thailand"

keyword_prompt = f"""
    User intent: "{user_intent}"
    Preferred Titles: "{preferred_titles}"
    Preferred Locations: "{preferred_locations}"
    
    Extract the exact job title and location the user wants to search for based on their intent.
    CRITICAL INSTRUCTION: If the User intent contains a specific job title (e.g. "marketing", "ai engineer", "software developer"), you MUST use that exact title!
    Only fallback to using the Preferred Titles if the User intent is completely empty or just says something generic like "find me a job".
    
    Respond strictly in JSON format like this:
    {{"title": "AI Engineer", "location": "Bangkok"}}
"""

res = llm.invoke([HumanMessage(content=keyword_prompt)])
print("LLM OUTPUT:", res.content)
