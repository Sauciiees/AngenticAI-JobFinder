import sys
import os
sys.path.append(os.getcwd())

from tools.scraper import scrape_job_description

test_url = "https://www.linkedin.com/jobs/view/4473768675/"
res = scrape_job_description(test_url)

with open("scratch/scraped_output.txt", "w", encoding="utf-8") as f:
    f.write(res)
print("Saved to scratch/scraped_output.txt")
