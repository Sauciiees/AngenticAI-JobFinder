import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
memory = SqliteSaver(conn)

cursor = conn.cursor()
cursor.execute("SELECT thread_id FROM checkpoints ORDER BY thread_id DESC LIMIT 1")
t = cursor.fetchone()[0]

config = {"configurable": {"thread_id": t}}
state = memory.get_tuple(config)
if hasattr(state, "values") and isinstance(state.values, dict):
    print("Keys in latest state:", list(state.values.keys()))
    if "application_results" in state.values:
        for res in state.values["application_results"]:
            print(f"Status: {res.get('final_status')}")
            for action in res.get("action_log", []):
                print("  -", action)
    else:
        print("NO application_results key.")
else:
    print("State has no values dict:", dir(state))
