from dotenv import load_dotenv
from langgraph.types import Command

load_dotenv()

from agent.graph import app

if __name__ == "__main__":
  config = {"configurable": {"thread_id": "job_finder_session_1"}}

  initial_state = {
      "messages": [
          (
              "user",
              "ช่วยหาตำแหน่ง Data Scientist หรือ AI Engineer ในไทยจาก LinkedIn"
              " ให้หน่อยครับ",
          )
      ],
      "user_profile": {
          "role": "Data Science & AI Engineer",
          "skills": [
              "Python",
              "PyTorch",
              "Pandas",
              "LangChain",
              "SQL",
              "Docker",
              "Azure",
          ],
      },
      "raw_jobs": [],
      "scored_jobs": [],
      "tailored_assets": {},
  }

  print("--- Running Multi-Agent Pipeline (With HITL) ---")

  # 1. Run until the first interrupt
  for event in app.stream(initial_state, config, stream_mode="values"):
    pass

  # 2. Check if interrupted
  state_snapshot = app.get_state(config)
  if state_snapshot.next:
    print("\n💡 Pipeline paused at node:", state_snapshot.next)
    feedback = input(
        "\n👉 Enter your feedback or type 'approve' to continue: "
    )

    print("\n--- Resuming Pipeline with User Input ---")

    # 3. Resume execution by passing the feedback using Command(resume=...)
    for event in app.stream(Command(resume=feedback), config, stream_mode="values"):
      pass

    print("\n✨ Pipeline execution completed successfully!")