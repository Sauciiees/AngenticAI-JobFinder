import requests
from bs4 import BeautifulSoup
import json

# Force Thai LinkedIn (this is what the user sees)
url = "https://th.linkedin.com/jobs/search/?keywords=Data%20Analyst&location=Bangkok&f_TPR=r604800"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
}

res = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(res.text, "lxml")
cards = soup.find_all("div", class_="base-card")

print(f"Found {len(cards)} cards\n")

for i, card in enumerate(cards[:3]):
    print(f"=== CARD {i} ===")
    # Dump h3 and h4 raw
    h3 = card.find("h3")
    h4 = card.find("h4")
    sr = card.find("span", class_="sr-only")
    img = card.find("img")
    link_el = card.find("a", class_="base-card__full-link")
    
    print(f"H3 text: '{h3.text.strip() if h3 else 'N/A'}'")
    print(f"H4 text: '{h4.text.strip() if h4 else 'N/A'}'")
    print(f"sr-only: '{sr.text.strip() if sr else 'N/A'}'")
    print(f"Link href: '{link_el['href'][:100] if link_el else 'N/A'}'")
    if img:
        src = img.get("data-delayed-url") or img.get("src", "")
        print(f"IMG src: '{src[:120]}'")
    print()
