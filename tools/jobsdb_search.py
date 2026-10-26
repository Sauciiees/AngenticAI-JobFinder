import re
import urllib.parse

# Google-style time filter -> JobsDB "daterange" (days since listed)
_DATERANGE = {"qdr:d": 1, "qdr:w": 7, "qdr:m": 31}
# Locations that mean "anywhere": search the whole country instead of one place
_ANYWHERE = {"", "thailand", "anywhere", "remote", "ทั่วประเทศ", "ประเทศไทย"}


def _slug(text: str) -> str:
    """JobsDB path segment: words joined by hyphens, e.g. "Data Analyst" -> "data-analyst"."""
    return urllib.parse.quote(re.sub(r"[\s/]+", "-", text.strip()))


def jobsdb_search_url(keyword: str, location: str, time_filter: str = "qdr:w") -> str:
    """e.g. https://th.jobsdb.com/th/data-analyst-jobs/in-Bangkok?daterange=7"""
    url = f"https://th.jobsdb.com/th/{_slug(keyword.lower())}-jobs"
    if location.strip().lower() not in _ANYWHERE:
        url += f"/in-{_slug(location)}"
    return f"{url}?daterange={_DATERANGE.get(time_filter, 7)}"


def jobsdb_direct_search(keyword: str, location: str, num_jobs: int = 5, time_filter: str = "qdr:w"):
    """Directly scrapes the JobsDB search page using Playwright, filtered by location and listing date."""
    from playwright.sync_api import sync_playwright

    url = jobsdb_search_url(keyword, location, time_filter)
    
    jobs = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            # Give React time: cards render first and the company logos a moment later.
            try:
                page.wait_for_selector("article", timeout=8000)
                page.wait_for_selector("article [data-automation='company-logo'] img", timeout=5000)
            except Exception:
                pass  # no logos on this page (or a slow load): carry on with what rendered
            
            cards = page.query_selector_all("article")
            for card in cards[:num_jobs]:
                try:
                    title_el = card.query_selector("h1, h2, h3")
                    title = title_el.inner_text().strip() if title_el else ""
                    
                    link_el = card.query_selector("a")
                    link = f"https://th.jobsdb.com{link_el.get_attribute('href')}" if link_el else ""
                    
                    company_el = card.query_selector("a[data-automation='jobCompany']")
                    company = company_el.inner_text().strip() if company_el else "Unknown Company"
                    
                    snippet_el = card.query_selector("ul")
                    snippet = snippet_el.inner_text().replace("\n", " ") if snippet_el else ""

                    # The card carries the advertiser's logo: an <img> inside the company-logo wrapper
                    # (images are blocked, but its src is still set). Job pages have no JSON-LD, so the
                    # scraper can't fill this in later.
                    logo_el = card.query_selector("[data-automation='company-logo'] img")
                    logo_url = (logo_el.get_attribute("src") or "") if logo_el else ""

                    location_el = card.query_selector("[data-automation='jobCardLocation']")
                    date_el = card.query_selector("[data-automation='jobListingDate']")

                    if title and link:
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": " ".join(location_el.inner_text().split()) if location_el else "",
                            "snippet": snippet,
                            "link": link,
                            "platform": "JobsDB",
                            "date": date_el.inner_text().strip() if date_el else "",  # e.g. "2 ชั่วโมงที่ผ่านมา"
                            "logo_url": logo_url,  # empty when the advertiser has no branding
                        })
                except Exception:
                    continue
                    
            browser.close()
    except Exception as e:
        print(f"JobsDB direct scrape error: {e}")
        
    return jobs
