import re
import sys

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace the advanced settings thread id in sidebar with the Chat History sidebar
old_sidebar = """    # Session config (collapsible)
    with st.expander("Advanced Settings"):
        session_id = st.text_input("Thread ID", value="job_finder_session_1", key="sidebar_session_id")
    
    if "sidebar_session_id" not in st.session_state:
        st.session_state["sidebar_session_id"] = "job_finder_session_1"

    # Spacer + Logout
    st.markdown("<br>" * 3, unsafe_allow_html=True)
    if st.button("Log Out", use_container_width=True):
        st.session_state.clear()
        st.rerun()


# Get session_id from sidebar
session_id = st.session_state.get("sidebar_session_id", "job_finder_session_1")"""

new_sidebar = """    st.markdown("---")
    st.markdown("### Chat History")
    
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        res = api_post("/api/chat-sessions", json={"title": "New Chat"})
        if res and res.status_code == 200:
            st.session_state["sidebar_session_id"] = res.json()["session_id"]
            st.session_state["pipeline_status"] = "idle"
            st.rerun()

    sessions_res = api_get("/api/chat-sessions")
    if sessions_res and sessions_res.status_code == 200:
        sessions = sessions_res.json()
        for s in sessions:
            # Highlight active session
            is_active = st.session_state.get("sidebar_session_id") == s["session_id"]
            if st.button(f"💬 {s['title'][:20]}", key=f"session_{s['session_id']}", use_container_width=True, type="primary" if is_active else "secondary"):
                st.session_state["sidebar_session_id"] = s["session_id"]
                st.session_state["pipeline_status"] = "idle"
                st.rerun()
                
    if st.session_state["page"] == "finder":
        st.markdown("---")
        st.markdown("### Search Settings")
        time_options = {
            "Past 24 hours": "qdr:d",
            "Past week (default)": "qdr:w",
            "Past month": "qdr:m",
        }
        selected_time_label = st.selectbox("Job Time Filter", options=list(time_options.keys()), index=1)
        st.session_state["time_filter"] = time_options[selected_time_label]

    # Spacer + Logout
    st.markdown("<br>" * 3, unsafe_allow_html=True)
    if st.button("Log Out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# Get session_id from sidebar, or create one
session_id = st.session_state.get("sidebar_session_id")
if not session_id and st.session_state.get("page") == "finder":
    res = api_post("/api/chat-sessions", json={"title": "New Chat"})
    if res and res.status_code == 200:
        session_id = res.json()["session_id"]
        st.session_state["sidebar_session_id"] = session_id
"""

if old_sidebar in content:
    content = content.replace(old_sidebar, new_sidebar)
else:
    print("Warning: could not find old_sidebar to replace")

# 2. Rewrite the finder page logic to use chat interface
finder_start = content.find('if st.session_state["page"] == "finder":')

if finder_start != -1:
    new_finder = '''if st.session_state["page"] == "finder":
    st.markdown('<div class="gradient-title">Job Finder</div>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Chat with AI to search for jobs, or let it run the pipeline</p>', unsafe_allow_html=True)
    
    # Fetch chat history
    history = []
    if session_id:
        res = api_get(f"/api/chat-sessions/{session_id}/history")
        if res and res.status_code == 200:
            data = res.json()
            history = data.get("history", [])
            # Only update status if it's currently idle or not set locally
            if st.session_state.get("pipeline_status", "idle") in ["idle", "completed"]:
                st.session_state["pipeline_status"] = data.get("status", "idle")
                st.session_state["raw_jobs_for_selection"] = data.get("raw_jobs", [])
                st.session_state["scored_jobs"] = data.get("scored_jobs", [])
                st.session_state["tailored_assets"] = data.get("tailored_assets", {})

    # Display chat history in continuous layout
    for idx, msg in enumerate(history):
        st.chat_message(msg["role"]).markdown(msg["content"])
        
    # Show pipeline UI at the bottom if paused
    pipeline_status = st.session_state.get("pipeline_status")
    
    if pipeline_status == "paused_for_selection":
        st.markdown("---")
        st.markdown("### 📋 Select Jobs to Apply")
        
        raw_jobs = st.session_state.get("raw_jobs_for_selection", [])
        if not raw_jobs:
            st.warning("No jobs found. Try a different search query.")
        else:
            if "selected_job_indices" not in st.session_state:
                st.session_state["selected_job_indices"] = []
                
            col_sel1, col_sel2, _ = st.columns([1, 1, 3])
            with col_sel1:
                if st.button("Select All"):
                    st.session_state["selected_job_indices"] = list(range(len(raw_jobs)))
                    st.rerun()
            with col_sel2:
                if st.button("Deselect All"):
                    st.session_state["selected_job_indices"] = []
                    st.rerun()
                    
            for idx, job in enumerate(raw_jobs):
                is_selected = st.checkbox(f"**{job.get('title')}** at {job.get('company')}", value=idx in st.session_state.get("selected_job_indices", []), key=f"job_{idx}")
                current_selections = st.session_state.get("selected_job_indices", [])
                if is_selected and idx not in current_selections:
                    current_selections.append(idx)
                elif not is_selected and idx in current_selections:
                    current_selections.remove(idx)
                st.session_state["selected_job_indices"] = current_selections
                
            if st.button(f"Continue with {len(st.session_state.get('selected_job_indices', []))} Jobs", type="primary"):
                with st.spinner("AI agents are screening and tailoring..."):
                    payload = {"session_id": session_id, "selected_indices": st.session_state["selected_job_indices"]}
                    res = api_post("/api/job-finder/select-jobs", json=payload)
                    if res and res.status_code == 200:
                        data = res.json()
                        st.session_state["pipeline_status"] = data["status"]
                        st.session_state["tailored_assets"] = data.get("tailored_assets", "No assets found.")
                        st.session_state["scored_jobs"] = data.get("scored_jobs", [])
                        st.rerun()
            if st.button("Cancel & Clear", type="secondary"):
                st.session_state["pipeline_status"] = "idle"
                st.rerun()

    elif pipeline_status == "paused_for_review":
        st.markdown("---")
        st.markdown("### 📝 Review & Apply")
        scored_jobs = st.session_state.get("scored_jobs", [])
        if scored_jobs:
            job_options = {f"{j.get('title')} at {j.get('company')}": j for j in scored_jobs}
            selected_job_label = st.radio("Select a Job Match to Proceed", options=list(job_options.keys()))
            selected_job = job_options[selected_job_label]
            
            with st.expander("View Generated Cover Letter / Resume"):
                st.markdown(str(st.session_state.get("tailored_assets", "")))
                
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Approve & Apply", type="primary"):
                    with st.spinner("Finalizing application..."):
                        payload = {"session_id": session_id, "feedback": "approve", "job_title": selected_job.get('title'), "company": selected_job.get('company')}
                        res = api_post("/api/job-finder/resume", json=payload)
                        if res and res.status_code == 200:
                            st.success("Application approved and logged!")
                            st.session_state["pipeline_status"] = "completed"
                            st.rerun()
            with col2:
                if st.button("Reject", type="secondary"):
                    st.session_state["pipeline_status"] = "idle"
                    st.rerun()

    # Chat Input (Sticky at Bottom)
    prompt = st.chat_input("Ask a question or search for a job...")
    if prompt:
        st.chat_message("user").markdown(prompt)
        time_filter = st.session_state.get("time_filter", "qdr:w")
        
        with st.spinner("AI is thinking..."):
            payload = {"session_id": session_id, "query": prompt, "time_filter": time_filter}
            res = api_post("/api/job-finder/start", json=payload)
            if res and res.status_code == 200:
                data = res.json()
                st.session_state["pipeline_status"] = data["status"]
                if data["status"] == "paused_for_selection":
                    st.session_state["raw_jobs_for_selection"] = data.get("raw_jobs", [])
                elif data["status"] == "paused_for_review":
                    st.session_state["tailored_assets"] = data.get("tailored_assets", {})
                    st.session_state["scored_jobs"] = data.get("scored_jobs", [])
                st.rerun()
            else:
                st.error("Failed to connect.")

# ============================================================
# PAGE: MY PROFILE
'''
    
    profile_page_marker = "# PAGE: MY PROFILE"
    marker_pos = content.find(profile_page_marker)
    
    content = content[:finder_start] + new_finder + content[marker_pos:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("app.py patched!")
