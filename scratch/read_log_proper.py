import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver
import json

conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
memory = SqliteSaver(conn)

cursor = conn.cursor()
cursor.execute("SELECT thread_id FROM checkpoints ORDER BY thread_id DESC LIMIT 10")
threads = list(set([r[0] for r in cursor.fetchall()]))

found = False
for t in threads:
    config = {"configurable": {"thread_id": t}}
    try:
        state = memory.get_tuple(config)
        results = state.checkpoint.get("channel_values", {}).get("application_results", [])
        if results:
            found = True
            for res in results:
                print(f"\n====================================")
                print(f"Job: {res.get('title')} at {res.get('company')}")
                print(f"Success: {res.get('success')} | Final Status: {res.get('final_status')}")
                print(f"====================================")
                print("Action Log:")
                for action in res.get("action_log", []):
                    print("  -", action)
            break
    except Exception as e:
        print("Error on thread", t, e)

if not found:
    print("No application_results found.")
