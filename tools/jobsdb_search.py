def jobsdb_direct_search(keyword: str, location: str, num_jobs: int = 5):
    """Directly scrapes the JobsDB search page using Playwright."""
    from playwright.sync_api import sync_playwright
    import urllib.parse
    
    # Format query for URL
    query = urllib.parse.quote(keyword)
    loc = urllib.parse.quote(location)
    url = f"https://th.jobsdb.com/th/search-jobs/{query}"
    
    jobs = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1000) # Give React time
            
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
                    
                    if title and link:
                        jobs.append({
                            "title": title,
                            "company": company,
                            "snippet": snippet,
                            "link": link,
                            "platform": "JobsDB",
                            "date": "", # JobsDB doesn't easily show date on the card
                            "logo_url": "" # Will be populated by the scraper later
                        })
                except Exception:
                    continue
                    
            browser.close()
    except Exception as e:
        print(f"JobsDB direct scrape error: {e}")
        
    return jobs
