import urllib.parse

# Google-style time filter -> Indeed "fromage" (days since posted)
_FROMAGE = {"qdr:d": 1, "qdr:w": 7, "qdr:m": 30}
_ANYWHERE = {"", "thailand", "anywhere", "ทั่วประเทศ", "ประเทศไทย"}
BASE = "https://th.indeed.com"


def indeed_search_url(keyword: str, location: str, time_filter: str = "qdr:w") -> str:
    """e.g. https://th.indeed.com/jobs?q=data+analyst&l=Bangkok&fromage=7"""
    params = {"q": keyword, "fromage": _FROMAGE.get(time_filter, 7)}
    if location.strip().lower() not in _ANYWHERE:
        params["l"] = location
    return f"{BASE}/jobs?{urllib.parse.urlencode(params)}"


def indeed_direct_search(keyword: str, location: str, num_jobs: int = 5, time_filter: str = "qdr:w") -> list:
    """Directly scrapes the Indeed Thailand search page using Playwright (no Serper)."""
    from playwright.sync_api import sync_playwright

    url = indeed_search_url(keyword, location, time_filter)
    jobs = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
            )
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            try:
                page.wait_for_selector("div.job_seen_beacon", timeout=8000)
            except Exception:
                pass  # no results, or a bot check: return what rendered (likely nothing)

            seen = set()
            for card in page.query_selector_all("div.job_seen_beacon"):
                if len(jobs) >= num_jobs:
                    break
                try:
                    title_el = card.query_selector("h2.jobTitle a, a.jcs-JobTitle")
                    if not title_el:
                        continue
                    title = title_el.inner_text().strip()
                    # The card's own href is a tracking redirect; the job id gives a stable job page.
                    jk = title_el.get_attribute("data-jk")
                    company_el = card.query_selector("[data-testid='company-name']")
                    company = company_el.inner_text().strip() if company_el else "Unknown Company"
                    # Indeed mixes in decoy cards (placeholder ids such as "abcdef0123456789") that copy
                    # a real job: skip those and any repeat of a job already taken.
                    if (jk and jk.startswith("abcdef")) or (title, company) in seen:
                        continue
                    seen.add((title, company))
                    link = f"{BASE}/viewjob?jk={jk}" if jk else urllib.parse.urljoin(BASE, title_el.get_attribute("href") or "")

                    location_el = card.query_selector("[data-testid='text-location']")
                    snippet_el = card.query_selector("[data-testid='jobsnippet_footer'], div.job-snippet")

                    if title and link:
                        jobs.append({
                            "title": title,
                            "company": company,
                            "location": location_el.inner_text().strip() if location_el else "",
                            "snippet": snippet_el.inner_text().replace("\n", " ").strip() if snippet_el else "",
                            "link": link,
                            "platform": "Indeed",
                            "date": "",  # the search is already limited by "fromage"; cards show no date
                            "logo_url": "",  # Indeed cards carry no company logo
                        })
                except Exception:
                    continue
            browser.close()
    except Exception as e:
        print(f"Indeed direct scrape error: {e}")

    return jobs
