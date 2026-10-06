import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("SERPER_API_KEY")
url = "https://google.serper.dev/search"
payload = {"q": "site:indeed.com/viewjob", "num": 1}
headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
res = requests.post(url, json=payload, headers=headers)
print(res.json().get("organic", [])[0].get("link"))

payload = {"q": "site:jobsdb.com/job/", "num": 1}
res = requests.post(url, json=payload, headers=headers)
print(res.json().get("organic", [])[0].get("link"))

payload = {"q": "site:jobbkk.com/jobs/detail", "num": 1}
res = requests.post(url, json=payload, headers=headers)
print(res.json().get("organic", [])[0].get("link"))
