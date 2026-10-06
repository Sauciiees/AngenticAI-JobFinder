import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("SERPER_API_KEY")
url = "https://google.serper.dev/search"
payload = {"q": "site:indeed.com/viewjob Data Scientist Thailand", "num": 3}
headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

res = requests.post(url, json=payload, headers=headers)
data = res.json()
jobs = data.get("organic", [])

if jobs:
    job_url = jobs[0].get("link")
    print(f"Testing URL: {job_url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    html_res = requests.get(job_url, headers=headers)
    print(f"Status: {html_res.status_code}")
    
    soup = BeautifulSoup(html_res.text, 'lxml')
    print("TITLE:", soup.title.string)
    
    # Try finding JSON-LD
    import json
    ld_scripts = soup.find_all("script", type="application/ld+json")
    print(f"Found {len(ld_scripts)} JSON-LD scripts")
    for s in ld_scripts:
        if "JobPosting" in s.string:
            print(s.string[:500])
            
    # Look for Indeed specific meta tags
    print("Meta tags:")
    for meta in soup.find_all("meta"):
        if meta.get("property") and "og:" in meta.get("property"):
            print(meta.get("property"), meta.get("content"))
