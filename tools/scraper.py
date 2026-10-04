from bs4 import BeautifulSoup
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


def scrape_job_description(url: str) -> str:
    """Synchronous scraper that returns the full page text."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        for script in soup(["script", "style", "noscript", "meta", "link", "header", "footer", "nav"]):
            script.extract()
        text = soup.get_text(separator=' ')
        text = re.sub(r'\s+', ' ', text).strip()
        return text if len(text) > 50 else ""
    except Exception:
        return ""


def _enrich_single_job(job):
    """Scrapes a single job URL using Playwright and enriches the job dict with full JD, clean title, and company."""
    url = job.get("link", "")
    if not url:
        return job
        
    try:
        from playwright.sync_api import sync_playwright
        import json
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            # Abort heavy assets to speed up scraping
            page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            
            # Give React/Next.js time to hydrate JSON-LD (Cloudflare bypass)
            page.wait_for_timeout(2000)
            
            html = page.content()
            browser.close()
            
            soup = BeautifulSoup(html, 'lxml')
            
            # 1. Try JSON-LD for perfect extraction of Title, Company, Logo
            ld_scripts = soup.find_all("script", type="application/ld+json")
            for script in ld_scripts:
                try:
                    if not script.string: continue
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        for item in data:
                            if item.get("@type") == "JobPosting":
                                data = item
                                break
                    
                    if data.get("@type") == "JobPosting":
                        is_linkedin = job.get("platform") == "LinkedIn"
                        
                        if data.get("title") and not is_linkedin:
                            job["title"] = data.get("title")
                        
                        org = data.get("hiringOrganization", {})
                        if isinstance(org, dict):
                            if org.get("name") and not is_linkedin:
                                job["company"] = org.get("name")
                            if org.get("logo") and not is_linkedin:
                                logo = org.get("logo")
                                if isinstance(logo, str):
                                    job["logo_url"] = logo
                                elif isinstance(logo, dict) and logo.get("url"):
                                    job["logo_url"] = logo.get("url")
                        break
                except Exception:
                    pass
            
            # 2. Extract full text for JD
            for script in soup(["script", "style", "noscript", "meta", "link", "header", "footer", "nav"]):
                script.extract()
            text = soup.get_text(separator=' ')
            text = re.sub(r'\s+', ' ', text).strip()
            
            job["full_jd"] = text if len(text) > 100 else "Scraped content too short."
            
    except Exception as e:
        job["full_jd"] = f"Failed to scrape ({str(e)})"
        
    return job


def enrich_jobs_with_scraper(jobs: list) -> list:
    """Takes a list of job dicts, scrapes them concurrently using threads, and updates title/company/full_jd."""
    if not jobs:
        return []
    try:
        enriched = [None] * len(jobs)
        # Using 3 workers max because Playwright opens 3 Chrome instances
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_idx = {executor.submit(_enrich_single_job, job): idx for idx, job in enumerate(jobs)}
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    enriched[idx] = future.result()
                except Exception:
                    enriched[idx] = jobs[idx]
        return enriched
    except Exception as e:
        print(f"Thread scrape error: {e}")
        return jobs
