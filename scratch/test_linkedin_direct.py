import requests
from bs4 import BeautifulSoup
url = "https://www.linkedin.com/jobs/search/?keywords=marketing&location=Thailand&f_TPR=r604800"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
res = requests.get(url, headers=headers)
soup = BeautifulSoup(res.text, "lxml")
cards = soup.find_all("div", class_="base-card")
for card in cards[:5]:
    title_el = card.find("h3", class_="base-search-card__title")
    print(title_el.get_text(strip=True) if title_el else "Unknown")
