"""
Browser Profile Setup Script
=============================
Run this script ONCE to log into job boards (LinkedIn, JobsDB, Indeed, etc.)
in a visible browser window. Your login sessions will be saved to the
'browser_profile' folder, allowing the Auto-Apply Agent to reuse them later.

Usage:
    python tools/browser_profile.py

Instructions:
    1. A Chrome browser window will open.
    2. Navigate to any job board and log in manually.
    3. Once logged in, close the browser window or press Ctrl+C in the terminal.
    4. Your sessions are saved automatically.
"""

import os
import sys

# Add parent dir to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "browser_profile")


def setup_browser_profile():
    """Opens a persistent browser for the user to log into job boards."""
    from playwright.sync_api import sync_playwright
    
    os.makedirs(PROFILE_DIR, exist_ok=True)
    
    print("=" * 60)
    print("  Browser Profile Setup")
    print("=" * 60)
    print()
    print("A Chrome browser window will open now.")
    print("Please log into any job boards you want to auto-apply on:")
    print("  - LinkedIn: https://www.linkedin.com/login")
    print("  - JobsDB: https://th.jobsdb.com/th")
    print("  - Indeed: https://secure.indeed.com/auth")
    print()
    print("When you are done, simply CLOSE the browser window.")
    print("Your login sessions will be saved automatically.")
    print("=" * 60)
    print()
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        
        page = browser.new_page()
        page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        
        print("Browser is open. Log in and close the window when done...")
        print()
        
        # Wait for the browser to be closed by the user
        try:
            # This blocks until all pages are closed
            browser.pages[0].wait_for_event("close", timeout=0)
        except Exception:
            pass
        
        try:
            browser.close()
        except Exception:
            pass
    
    print()
    print("Browser profile saved successfully!")
    print(f"Profile directory: {PROFILE_DIR}")
    print()
    print("You can now use the Auto-Apply Agent. Your logins will be remembered.")


if __name__ == "__main__":
    setup_browser_profile()
