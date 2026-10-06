import asyncio
from concurrent.futures import ThreadPoolExecutor
from tools.scraper import enrich_jobs_with_scraper

jobs = [
  {
    "title": "Marketing Executive",
    "link": "https://www.jobbkk.com/jobs/detail/203753/1121277",
    "platform": "JobBKK"
  }
]

async def main():
    print("Running in async loop...")
    # Simulate FastAPI async endpoint calling synchronous code
    loop = asyncio.get_running_loop()
    
    # In LangGraph, it runs the node directly, but we are inside an async function!
    # Let's call enrich_jobs_with_scraper which internally uses ThreadPoolExecutor
    res = enrich_jobs_with_scraper(jobs)
    print("Result:", res)

asyncio.run(main())
