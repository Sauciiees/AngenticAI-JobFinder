import os
import requests
import json
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("SERPER_API_KEY")
url = "https://google.serper.dev/search"

# Test JobsDB
payload = {"q": "site:jobsdb.com/th/job Data Scientist Thailand", "num": 5}
headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
res = requests.post(url, json=payload, headers=headers)
print("JobsDB Results:")
print(json.dumps(res.json().get("organic", []), indent=2))

# Test Indeed
payload = {"q": "site:indeed.com/viewjob Data Scientist Thailand", "num": 5}
res = requests.post(url, json=payload, headers=headers)
print("Indeed Results:")
print(json.dumps(res.json().get("organic", []), indent=2))

