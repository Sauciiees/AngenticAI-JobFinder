import requests
from bs4 import BeautifulSoup
import json

url = "https://www.linkedin.com/jobs/search/?keywords=AI%20Engineer&location=Bangkok%2C%20Thailand"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, "lxml")
jobs = soup.find_all("div", class_="base-card")

extracted = []
for job in jobs[:5]:
    title_el = job.find("h3", class_="base-search-card__title")
    company_el = job.find("h4", class_="base-search-card__subtitle")
    link_el = job.find("a", class_="base-card__full-link")
    date_el = job.find("time")
    
    title = title_el.text.strip() if title_el else ""
    company = company_el.text.strip() if company_el else ""
    link = link_el["href"].split("?")[0] if link_el and "href" in link_el.attrs else ""
    date = date_el.text.strip() if date_el else ""
    
    extracted.append({
        "title": title,
        "company": company,
        "link": link,
        "date": date
    })

print(json.dumps(extracted, indent=2, ensure_ascii=False))
