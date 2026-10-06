import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re

async def fetch_url(session, url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with session.get(url, headers=headers, timeout=10) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'lxml')
            
            # Extract title
            page_title = soup.title.string if soup.title else ""
            
            # Clean text
            for script in soup(["script", "style", "noscript", "meta", "link", "header", "footer", "nav"]):
                script.extract()
            text = soup.get_text(separator=' ')
            text = re.sub(r'\s+', ' ', text).strip()
            
            return {"url": url, "page_title": page_title, "text_len": len(text)}
    except Exception as e:
        return {"url": url, "error": str(e)}

async def main():
    urls = [
        "https://www.linkedin.com/jobs/view/4473768675/",
        "https://th.linkedin.com/jobs/view/automation-ai-engineer-intern-at-siemens-4472585520"
    ]
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, u) for u in urls]
        results = await asyncio.gather(*tasks)
        for r in results:
            print(r)

if __name__ == "__main__":
    asyncio.run(main())
