import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("SERPER_API_KEY")
url = "https://google.serper.dev/search"
payload = {"q": "site:jobsdb.com/th/job Data Scientist Thailand", "num": 1}
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
    
    import json
    ld_scripts = soup.find_all("script", type="application/ld+json")
    for s in ld_scripts:
        if s.string and "JobPosting" in s.string:
            print(s.string[:500])
