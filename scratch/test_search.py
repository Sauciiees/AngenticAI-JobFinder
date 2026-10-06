import sys
import os
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

from tools.job_tools import _serper_search_structured

try:
    results = _serper_search_structured("AI Engineer", "Bangkok", "linkedin.com/jobs", "LinkedIn", "qdr:w", 10)
    print("Found:", len(results))
    print(results)
except Exception as e:
    import traceback
    traceback.print_exc()
