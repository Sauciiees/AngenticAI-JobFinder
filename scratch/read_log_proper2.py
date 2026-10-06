import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
memory = SqliteSaver(conn)

cursor = conn.cursor()
cursor.execute("SELECT thread_id FROM checkpoints ORDER BY thread_id DESC LIMIT 10")
threads = list(set([r[0] for r in cursor.fetchall()]))

for t in threads:
    config = {"configurable": {"thread_id": t}}
    state = memory.get_tuple(config)
    # in langgraph 0.1+, state.values is a dict
    if hasattr(state, "values") and isinstance(state.values, dict):
        if "application_results" in state.values and state.values["application_results"]:
            print(f"--- FOUND RESULTS IN THREAD {t} ---")
            for res in state.values["application_results"]:
                print(f"Job: {res.get('title')}")
                print(f"Status: {res.get('final_status')}")
                for action in res.get("action_log", []):
                    print("  -", action)
            break
