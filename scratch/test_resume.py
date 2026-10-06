import requests
import json

res = requests.post("http://127.0.0.1:8000/api/job-finder/resume", json={
    "session_id": "test",
    "feedback": "approve",
    "jobs": [{"title": "Test", "company": "Test"}]
})
print(res.status_code)
print(res.text)
