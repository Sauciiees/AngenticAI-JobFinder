from tools.scraper import _enrich_single_job
import json

job_jobsdb = {"link": "https://th.jobsdb.com/th/job-expert-jobs/in-%E0%B8%99%E0%B8%99%E0%B8%97%E0%B8%9A%E0%B8%B8%E0%B8%A3%E0%B8%B5", "platform": "JobsDB"}
res = _enrich_single_job(job_jobsdb)
print(json.dumps(res, indent=2))
