import requests
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
res = requests.get("https://th.indeed.com/rss?q=Data+Scientist", headers=headers)
print(res.status_code)
print(res.text[:500])
