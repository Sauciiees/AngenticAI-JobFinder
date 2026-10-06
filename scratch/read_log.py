import sqlite3
import pickle
import json

conn = sqlite3.connect("checkpoints.sqlite")
cursor = conn.cursor()

# Get the most recent checkpoint
cursor.execute("SELECT checkpoint FROM checkpoints ORDER BY thread_id DESC, checkpoint_id DESC LIMIT 1")
row = cursor.fetchone()
if row:
    checkpoint = pickle.loads(row[0])
    # The channel 'application_results' might be in the state
    results = checkpoint.get("channel_values", {}).get("application_results", [])
    for res in results:
        print(f"\nJob: {res.get('title')} at {res.get('company')}")
        print(f"Status: {res.get('final_status')}")
        print("Action Log:")
        for action in res.get("action_log", []):
            print("  -", action)
else:
    print("No checkpoints found.")
