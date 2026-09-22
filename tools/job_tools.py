import os
import requests
from langchain_core.tools import tool


@tool
def search_linkedin_jobs(keyword: str, location: str = "Thailand") -> str:
  """Search specifically for open job positions on LinkedIn using Serper API.

  Use this tool whenever the user wants to find live job listings on LinkedIn.

  Args:
      keyword: The job title, tech stack, or skill (e.g., 'Data Scientist',
        'Python Developer').
      location: The target location or country (default is 'Thailand').
  """
  api_key = os.getenv("SERPER_API_KEY")
  if not api_key:
    return (
        "Error: SERPER_API_KEY is not set in the environment variables."
        " Please add it to your .env file."
    )

  # Construct a targeted query restricting results to LinkedIn job pages
  query = f"site:linkedin.com/jobs {keyword} {location}"

  url = "https://google.serper.dev/search"
  payload = {"q": query, "num": 5}  # Fetch top 5 results
  headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

  try:
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()

    organic_results = data.get("organic", [])
    if not organic_results:
      return (
          f"No live LinkedIn job postings found for '{keyword}' in"
          f" '{location}'."
      )

    formatted_results = []
    for item in organic_results:
      title = item.get("title", "No Title")
      snippet = item.get("snippet", "No description available.")
      link = item.get("link", "#")
      formatted_results.append(
          f"- **{title}**\n  Snippet: {snippet}\n  Link: {link}"
      )

    return f"Found {len(formatted_results)} live LinkedIn jobs for '{keyword}' in {location}:\n\n" + "\n\n".join(
        formatted_results
    )

  except Exception as e:
    return f"An error occurred while connecting to the Serper API: {str(e)}"