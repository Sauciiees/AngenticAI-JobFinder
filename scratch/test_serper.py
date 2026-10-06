import os
import requests
import json
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("SERPER_API_KEY")
url = "https://google.serper.dev/search"
payload = {"q": "site:jobsdb.com/th/job Data Scientist", "num": 1}
headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
res = requests.post(url, json=payload, headers=headers)
print(json.dumps(res.json().get("organic", [])[0], indent=2))
