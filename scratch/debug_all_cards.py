import requests
from bs4 import BeautifulSoup

# Search for the exact query the user used
url = "https://www.linkedin.com/jobs/search/?keywords=AI%20Engineer%20Internship&location=Bangkok&f_TPR=r604800"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

res = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(res.text, "lxml")
cards = soup.find_all("div", class_="base-card")

print(f"Found {len(cards)} cards\n")

for i, card in enumerate(cards):
    h3 = card.find("h3", class_="base-search-card__title")
    h4 = card.find("h4", class_="base-search-card__subtitle")
    sr = card.find("span", class_="sr-only")
    link_el = card.find("a", class_="base-card__full-link")
    img = card.find("img")

    title = h3.text.strip() if h3 else "N/A"
    company = h4.text.strip() if h4 else "N/A"
    sr_text = sr.text.strip() if sr else "N/A"
    link = link_el["href"].split("?")[0] if link_el and "href" in link_el.attrs else "#"
    logo = ""
    if img:
        logo = img.get("data-delayed-url") or img.get("src", "")
    
    print(f"{i+1}. TITLE: '{title}' | COMPANY: '{company}' | SR: '{sr_text}' | LOGO: {'YES' if logo and 'company-logo' in logo else 'NO'}")
