import requests
import streamlit as st
import os
# FastAPI Backend URL
API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Agentic AI Job Finder", page_icon="🤖", layout="wide")

# 1. Initialize Authentication State
if "token" not in st.session_state:
    st.session_state["token"] = None
if "username" not in st.session_state:
    st.session_state["username"] = None
if "cv_filename" not in st.session_state:         
    st.session_state["cv_filename"] = None

# ==========================================
# 🛑 UNAUTHENTICATED VIEW (LOGIN/SIGNUP)
# ==========================================
if not st.session_state["token"]:
    st.title("🔐 Welcome to Agentic AI Job Finder")
    st.markdown("Please log in or create an account to access the AI agents.")
    
    # Create clean tabs for Login and Sign Up
    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])
    
    with tab_login:
        with st.form("login_form"):
            st.subheader("Log In")
            login_user = st.text_input("Username")
            login_pass = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", type="primary")
            
            if submitted:
                try:
                    res = requests.post(f"{API_URL}/api/login", json={"username": login_user, "password": login_pass})
                    if res.status_code == 200:
                        data = res.json()
                        # Update the login success block
                        st.session_state["token"] = data["access_token"]
                        st.session_state["username"] = data["username"]
                        st.session_state["cv_filename"] = data.get("cv_filename")  # <--- Save filename
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")
                except requests.exceptions.ConnectionError:
                    st.error("Could not connect to server. Is uvicorn running?")

    with tab_signup:
        with st.form("signup_form"):
            st.subheader("Create a New Account")
            new_user = st.text_input("Choose a Username")
            new_pass = st.text_input("Choose a Password", type="password")
            new_pass_confirm = st.text_input("Confirm Password", type="password")
            signup_submitted = st.form_submit_button("Sign Up")
            
            if signup_submitted:
                if new_pass != new_pass_confirm:
                    st.error("Passwords do not match!")
                else:
                    try:
                        res = requests.post(f"{API_URL}/api/signup", json={"username": new_user, "password": new_pass})
                        if res.status_code == 200:
                            st.success("Account created successfully! You can now log in.")
                        else:
                            st.error(res.json().get("detail", "Error creating account."))
                    except requests.exceptions.ConnectionError:
                        st.error("Could not connect to server.")

# ==========================================
# 🟢 AUTHENTICATED VIEW (MAIN DASHBOARD)
# ==========================================
else:
    # Every request to FastAPI must now include this JWT in the headers
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}

    st.title("🤖 Autonomous Agentic AI Job Finder")
    st.markdown(f"**Welcome back, {st.session_state['username']}!**")

    # Sidebar for Session and Profile Setup
   # Sidebar for Session and Profile Setup
    with st.sidebar:
        st.header("⚙️ Profile Control")
        if st.button("Log Out"):
            st.session_state.clear()
            st.rerun()

        st.markdown("---")
        session_id = st.text_input("Thread ID (LangGraph)", value="job_finder_session_1")

        st.subheader("📄 Upload Resume / CV")
        
        # Display the current active file cleanly above the uploader
        if st.session_state.get("cv_filename"):
            st.markdown(f"**Current active CV:** `{st.session_state['cv_filename']}`")
            
        uploaded_file = st.file_uploader("Upload a new CV to replace it", type=["pdf"], key="resume_uploader")

        if uploaded_file and st.button("Upload & Vectorize CV"):
            with st.spinner("Parsing and vectorizing securely..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                
                response = requests.post(
                    f"{API_URL}/api/upload-resume",
                    params={"session_id": session_id},
                    headers=headers,
                    files=files,
                )
                if response.status_code == 200:
                    st.success("CV successfully parsed and stored securely!")
                    # Update the live session state with the new filename
                    st.session_state["cv_filename"] = uploaded_file.name 
                    st.rerun()
                else:
                    st.error(f"Error: {response.json().get('detail', 'Unknown error')}")

    # Main Interface Tabs
    tab1, tab2 = st.tabs(["🚀 Job Discovery & Review", "📊 Application Tracker"])

    with tab1:
        st.subheader("Step 1: Run Multi-Agent Pipeline")
        search_query = st.text_input("Job Search Prompt", value="Find Data Scientist jobs in Thailand")

        if st.button("Start Job Finder Agent Pipeline", type="primary"):
            with st.spinner("Agents are searching, matching, and tailoring..."):
                payload = {"session_id": session_id, "query": search_query}
                
                # Attach the JWT headers here!
                response = requests.post(f"{API_URL}/api/job-finder/start", json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    st.session_state["pipeline_status"] = data["status"]
                    st.session_state["tailored_assets"] = data.get("tailored_assets", "No assets found.")
                    st.rerun()
                else:
                    st.error(f"Error: {response.json().get('detail', response.text)}")

        if st.session_state.get("pipeline_status") == "paused_for_review":
            st.markdown("---")
            st.markdown("### 🛑 Stage 4: Human-in-the-Loop Review")
            st.markdown(st.session_state.get("tailored_assets", ""))

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve & Log Application", type="primary"):
                    with st.spinner("Resuming pipeline..."):
                        resume_payload = {"session_id": session_id, "feedback": "approve"}
                        # Attach JWT here too
                        res_response = requests.post(
                            f"{API_URL}/api/job-finder/resume", 
                            json=resume_payload, 
                            headers=headers
                        )

                        if res_response.status_code == 200:
                            st.success("Application approved and logged successfully!")
                            st.session_state["pipeline_status"] = "completed"
                            st.rerun()
                        else:
                            st.error("Failed to resume pipeline.")
            with col2:
                if st.button("❌ Reject / Request Changes"):
                    st.warning("Session paused. You can modify your prompt or retry.")

    with tab2:
        st.subheader("📊 Application Tracker History")
        st.markdown("Here is the history of all jobs you have approved and tracked through the agent pipeline.")

        if st.button("🔄 Refresh History"):
            st.rerun()

        # Call the protected FastAPI endpoint with your JWT headers
        try:
            res = requests.get(f"{API_URL}/api/applications", headers=headers)
            
            if res.status_code == 200:
                apps_data = res.json()
                
                if not apps_data:
                    st.info("No applications logged yet. Run the Job Discovery agent and approve a role to start tracking!")
                else:
                    # Render the applications neatly in an interactive Streamlit table
                    import pandas as pd
                    df = pd.DataFrame(apps_data)
                    
                    # Reorder/rename columns for clean presentation
                    df = df[["timestamp", "status", "assets_preview"]]
                    df.columns = ["Timestamp", "Status", "Job Details Preview"]
                    
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.error("Failed to load application history from the database.")
        except requests.exceptions.ConnectionError:
            st.error("Could not connect to the backend server.")