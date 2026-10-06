import os
import requests
import json
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("SERPER_API_KEY")
url = "https://google.serper.dev/search"

payload = {"q": "site:jobbkk.com/jobs/detail Marketing Executive Thailand", "num": 5}
headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
res = requests.post(url, json=payload, headers=headers)
print("JobBKK Results:")
print(json.dumps(res.json().get("organic", []), indent=2))
