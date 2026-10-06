import os
import requests
import json
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("SERPER_API_KEY")
url = "https://google.serper.dev/search"

payload = {"q": "site:jobsdb.com/th/en/job Data Scientist Thailand", "num": 5}
headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
res = requests.post(url, json=payload, headers=headers)
print("En JobsDB:")
for o in res.json().get("organic", []):
    print(o.get("link"))

payload = {"q": "site:th.jobsdb.com Data Scientist", "num": 10}
res = requests.post(url, json=payload, headers=headers)
print("Broad JobsDB:")
for o in res.json().get("organic", []):
    print(o.get("link"))
