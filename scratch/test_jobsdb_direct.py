from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://th.jobsdb.com/th/search-jobs/data-scientist", wait_until="networkidle")
    
    # Try to find job cards
    cards = page.query_selector_all("article")
    print(f"Found {len(cards)} articles")
    for card in cards[:3]:
        title = card.query_selector("h1, h2, h3")
        company = card.query_selector("a[data-automation='jobCompany']")
        print("Title:", title.inner_text() if title else "N/A")
        print("Company:", company.inner_text() if company else "N/A")
    browser.close()
