import requests
from bs4 import BeautifulSoup
import json

url = "https://www.linkedin.com/jobs/search/?keywords=Data%20Analyst&location=Bangkok%2C%20Thailand&f_TPR=r604800"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

res = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(res.text, "lxml")
cards = soup.find_all("div", class_="base-card")

print(f"Found {len(cards)} cards\n")

# Dump the full HTML of first 2 cards
for i, card in enumerate(cards[:2]):
    print(f"=== CARD {i} HTML ===")
    print(card.prettify()[:2000])
    print("=" * 50)
    
    title_el = card.find("h3", class_="base-search-card__title")
    company_el = card.find("h4", class_="base-search-card__subtitle")
    link_el = card.find("a", class_="base-card__full-link")
    date_el = card.find("time")
    img_el = card.find("img")
    
    print(f"TITLE: '{title_el.text.strip() if title_el else 'N/A'}'")
    print(f"COMPANY: '{company_el.text.strip() if company_el else 'N/A'}'")
    print(f"LINK: '{link_el['href'][:80] if link_el else 'N/A'}'")
    print(f"DATE: '{date_el.text.strip() if date_el else 'N/A'}'")
    print(f"IMG: '{img_el['data-delayed-url'] if img_el and img_el.has_attr('data-delayed-url') else (img_el['src'] if img_el and img_el.has_attr('src') else 'N/A')}'")
    print()
