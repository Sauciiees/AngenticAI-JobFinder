import sys
import os
import json
import requests
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

api_key = os.getenv("SERPER_API_KEY")
url = "https://google.serper.dev/search"
payload = {"q": "site:linkedin.com/jobs AI Engineer Bangkok", "num": 3}
headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers)
    data = response.json()
    with open("scratch/raw_serper_output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Saved raw Serper output!")
except Exception as e:
    import traceback
    traceback.print_exc()
