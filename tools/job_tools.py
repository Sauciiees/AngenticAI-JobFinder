import os
import requests
from langchain_core.tools import tool


def _serper_search_structured(keyword: str, location: str, site: str, platform_name: str, time_filter: str = "qdr:w", num: int = 10) -> list:
  """Internal function that returns structured job data as a list of dicts."""
  api_key = os.getenv("SERPER_API_KEY")
  if not api_key:
    return []

  query = f"site:{site} {keyword} {location}"
  url = "https://google.serper.dev/search"
  payload = {"q": query, "num": num, "tbs": time_filter}
  headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

  try:
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()

    organic_results = data.get("organic", [])
    jobs = []
    import re
    
    for item in organic_results:
      title = item.get("title", "")
      link = item.get("link", "")
      snippet = item.get("snippet", "")
      
      # Heuristic filters to ignore search/directory pages:
      # 1. Title contains numbers with plus (e.g. "1000+", "75+")
      if re.search(r'\d+\+', title):
          continue
      # 2. Title has "(XX Open Roles)" or "งาน" search directories
      if re.search(r'(?i)\bopen roles\b', title):
          continue
      # 3. LinkedIn specific: Real jobs usually have "/view/" in the URL, not just "/jobs/some-category"
      if "linkedin.com" in link and "/view/" not in link:
          continue
          
      clean_title, company_name = _clean_title_and_company(title, snippet)
      
      jobs.append({
          "title": clean_title,
          "company": company_name,
          "snippet": snippet,
          "link": link,
          "platform": platform_name,
          "date": item.get("date", ""),
      })
    return jobs

  except Exception as e:
    print(f"Serper API error for {platform_name}: {str(e)}")
    return []


def _clean_title_and_company(title: str, snippet: str):
  """Extracts clean job title and company from Google Search title."""
  company = "Unknown Company"
  clean_title = title
  
  import re
  
  # Remove common trailing platform junk
  clean_title = re.sub(r'(?i)\s*-\s*Indeed\.com.*$', '', clean_title)
  clean_title = re.sub(r'(?i)\s*-\s*JobsDB.*$', '', clean_title)
  clean_title = re.sub(r'(?i)\s*-\s*JOBBKK.*$', '', clean_title)
  clean_title = re.sub(r'(?i)\s*\|\s*LinkedIn.*$', '', clean_title)
  clean_title = re.sub(r'(?i)\s*jobs in\s+.*$', '', clean_title)
  clean_title = re.sub(r'(?i)\s*งาน\s+.*$', '', clean_title) # Thai "jobs in"
  
  # 1. Handle LinkedIn format: "Company hiring Title in Location"
  if " hiring " in clean_title or " กำลังรับสมัคร " in clean_title:
      split_word = " hiring " if " hiring " in clean_title else " กำลังรับสมัคร "
      parts = clean_title.split(split_word, 1)
      company = parts[0].strip()
      clean_title = parts[1].strip()
      clean_title = re.sub(r' in .*$', '', clean_title).strip()
      clean_title = re.sub(r' ใน .*$', '', clean_title).strip()
      
  # 2. Handle "Title at Company" or "Title @ Company"
  elif " at " in clean_title.lower() or " @ " in clean_title:
      splitter = " at " if " at " in clean_title.lower() else " @ "
      parts = re.split(splitter, clean_title, maxsplit=1, flags=re.IGNORECASE)
      clean_title = parts[0].strip()
      company = parts[1].strip()
      
  # 3. Handle Indeed/JobsDB format: "Title - Company"
  elif " - " in clean_title:
      parts = clean_title.split(" - ")
      # Often [Title, Company] or [Title, Location, Company]
      clean_title = parts[0].strip()
      # Usually the last part is the company name before we stripped the Indeed.com junk
      company = parts[-1].strip()
      
  # Clean up any leftover punctuation
  clean_title = clean_title.rstrip(" ...").rstrip("-").strip()
  company = company.rstrip(" ...").rstrip("-").strip()
  
  # If company wasn't found in title, try to guess from snippet
  if company == "Unknown Company" and snippet:
      # Very basic heuristic: Look for capitalized words near the start of the snippet
      match = re.search(r'^([A-Z][a-zA-Z0-9\s]+)\b', snippet)
      if match and len(match.group(1)) > 3:
          # Actually, it's too risky. Let's leave it as Unknown Company if not in title.
          pass
          
  return clean_title, company


def _format_results_as_string(jobs: list, platform_name: str, keyword: str, location: str) -> str:
  """Format structured job list into a readable string for LangChain tool output."""
  if not jobs:
    return f"No live {platform_name} job postings found for '{keyword}' in '{location}'."

  formatted_results = []
  for job in jobs:
    formatted_results.append(
        f"- **{job['title']}**\n  Company: {job['company']}\n  Snippet: {job['snippet']}\n  Link: {job['link']}"
    )

  return f"Found {len(formatted_results)} live {platform_name} jobs for '{keyword}' in {location}:\n\n" + "\n\n".join(
      formatted_results
  )


@tool
def search_linkedin_jobs(keyword: str, location: str = "Thailand") -> str:
  """Search specifically for open job positions on LinkedIn using direct LinkedIn API.

  Use this tool whenever the user wants to find live job listings on LinkedIn.

  Args:
      keyword: The job title, tech stack, or skill (e.g., 'Data Scientist',
        'Python Developer').
      location: The target location or country (default is 'Thailand').
  """
  from tools.linkedin_search import linkedin_direct_search
  jobs = linkedin_direct_search(keyword, location, "qdr:w", 10)
  return _format_results_as_string(jobs, "LinkedIn (Direct)", keyword, location)

@tool
def search_indeed_jobs(keyword: str, location: str = "Thailand") -> str:
  """Search specifically for open job positions on Indeed using Serper API.

  Use this tool whenever the user wants to find live job listings on Indeed.

  Args:
      keyword: The job title, tech stack, or skill.
      location: The target location or country (default is 'Thailand').
  """
  jobs = _serper_search_structured(keyword, location, "indeed.com/viewjob", "Indeed")
  return _format_results_as_string(jobs, "Indeed", keyword, location)

@tool
def search_jobsdb_jobs(keyword: str, location: str = "Thailand") -> str:
  """Search specifically for open job positions on JobsDB using direct scraping.

  Use this tool whenever the user wants to find live job listings on JobsDB.

  Args:
      keyword: The job title, tech stack, or skill.
      location: The target location or country (default is 'Thailand').
  """
  from tools.jobsdb_search import jobsdb_direct_search
  jobs = jobsdb_direct_search(keyword, location, 10)
  return _format_results_as_string(jobs, "JobsDB (Direct)", keyword, location)

@tool
def search_jobbkk_jobs(keyword: str, location: str = "Thailand") -> str:
  """Search specifically for open job positions on JobBKK using Serper API.

  Use this tool whenever the user wants to find live job listings on JobBKK.

  Args:
      keyword: The job title, tech stack, or skill.
      location: The target location or country (default is 'Thailand').
  """
  jobs = _serper_search_structured(keyword, location, "jobbkk.com/jobs/detail", "JobBKK")
  return _format_results_as_string(jobs, "JobBKK", keyword, location)