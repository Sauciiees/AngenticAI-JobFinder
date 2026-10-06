import requests
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
res = requests.get("https://th.indeed.com/jobs?q=Data+Scientist", headers=headers)
print("Status:", res.status_code)
if res.status_code != 200:
    print(res.text[:500])
else:
    print("Success! Can read HTML.")
