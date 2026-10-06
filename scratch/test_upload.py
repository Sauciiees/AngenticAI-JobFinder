import sys
import os
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv()

from agent.vector_store import vector_store

try:
    vector_store.add_documents(["Test doc"], [{"type": "test"}], ["id1"])
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
