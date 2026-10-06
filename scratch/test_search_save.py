import sys
import os
import json
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

from tools.job_tools import _serper_search_structured

try:
    results = _serper_search_structured("AI Engineer", "Bangkok", "linkedin.com/jobs", "LinkedIn", "qdr:w", 10)
    
    with open("scratch/search_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully saved {len(results)} results to scratch/search_results.json")
except Exception as e:
    import traceback
    traceback.print_exc()
