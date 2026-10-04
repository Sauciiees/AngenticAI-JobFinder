import requests
from bs4 import BeautifulSoup

def linkedin_direct_search(keyword: str, location: str, time_filter: str = "qdr:w", num: int = 10) -> list:
    """Directly scrapes LinkedIn guest search page for perfect job data."""
    # Convert Google time_filter to LinkedIn time_filter
    f_tpr = "r604800"  # default: past week
    if time_filter == "qdr:d":
        f_tpr = "r86400"
    elif time_filter == "qdr:m":
        f_tpr = "r2592000"
        
    url = f"https://www.linkedin.com/jobs/search/?keywords={requests.utils.quote(keyword)}&location={requests.utils.quote(location)}&f_TPR={f_tpr}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    jobs = []
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "lxml")
            cards = soup.find_all("div", class_="base-card")
            
            for card in cards[:num]:
                # --- Title ---
                # Prefer h3 with class, fallback to sr-only span
                title_el = card.find("h3", class_="base-search-card__title")
                sr_el = card.find("span", class_="sr-only")
                
                if title_el:
                    title = title_el.get_text(strip=True)
                elif sr_el:
                    title = sr_el.get_text(strip=True)
                else:
                    title = "Unknown Title"
                
                # --- Company ---
                company_el = card.find("h4", class_="base-search-card__subtitle")
                if company_el:
                    # Get just the inner link text (clean company name)
                    link_inside = company_el.find("a")
                    if link_inside:
                        company = link_inside.get_text(strip=True)
                    else:
                        company = company_el.get_text(strip=True)
                else:
                    company = "Unknown Company"
                
                # --- Location ---
                loc_el = card.find("span", class_="job-search-card__location")
                location_text = loc_el.get_text(strip=True) if loc_el else ""
                
                # --- Link ---
                link_el = card.find("a", class_="base-card__full-link")
                link = link_el["href"].split("?")[0] if link_el and "href" in link_el.attrs else "#"
                
                # --- Date ---
                date_el = card.find("time")
                date = date_el.get_text(strip=True) if date_el else ""
                
                # --- Company Logo ---
                img_el = card.find("img")
                logo_url = ""
                if img_el:
                    logo_url = img_el.get("data-delayed-url") or img_el.get("src", "")
                    # Filter out ghost/placeholder images
                    if "ghost" in logo_url or "static.licdn" in logo_url:
                        logo_url = ""
                
                jobs.append({
                    "title": title,
                    "company": company,
                    "location": location_text,
                    "snippet": "",
                    "link": link,
                    "platform": "LinkedIn",
                    "date": date,
                    "logo_url": logo_url,
                })
    except Exception as e:
        print(f"LinkedIn direct search failed: {e}")
        
    return jobs

if __name__ == "__main__":
    import json
    res = linkedin_direct_search("AI Engineer", "Bangkok")
    print(f"Found {len(res)} jobs.")
    for j in res[:5]:
        print(f"  {j['title']} @ {j['company']} | Logo: {'YES' if j['logo_url'] else 'NO'}")
