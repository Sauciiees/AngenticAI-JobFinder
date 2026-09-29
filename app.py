import requests
import streamlit as st
import os
import pandas as pd
import json
import ast

API_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="AI Job Finder",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# GEMINI-INSPIRED DARK THEME CSS (EMOJI REDUCED)
# ============================================================
st.markdown("""
<style>
/* ---- Global ---- */
@import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');

:root {
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-card: #1e2a4a;
    --bg-card-hover: #243156;
    --bg-input: #0f1629;
    --text-primary: #e8eaed;
    --text-secondary: #9aa0a6;
    --text-muted: #6b7280;
    --accent-blue: #4285F4;
    --accent-purple: #8B5CF6;
    --accent-gradient: linear-gradient(135deg, #4285F4, #8B5CF6);
    --accent-green: #34A853;
    --accent-red: #EA4335;
    --accent-yellow: #FBBC04;
    --border-color: #2d3748;
    --border-radius: 16px;
    --shadow: 0 2px 12px rgba(0,0,0,0.3);
}

.stApp {
    background: linear-gradient(180deg, #0f0f23 0%, #1a1a2e 50%, #16213e 100%) !important;
    font-family: 'Inter', 'Google Sans', sans-serif !important;
}

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    background: #0d1117 !important;
    border-right: 1px solid var(--border-color) !important;
}

section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {
    color: var(--text-primary) !important;
}

/* ---- Cards ---- */
.gemini-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--border-radius);
    padding: 24px;
    margin-bottom: 16px;
    transition: all 0.2s ease;
}

.gemini-card:hover {
    background: var(--bg-card-hover);
    border-color: var(--accent-blue);
    box-shadow: var(--shadow);
}

.gemini-card h3 {
    color: var(--text-primary) !important;
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 10px;
}

/* ---- Gradient Title ---- */
.gradient-title {
    background: var(--accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-size: 2.2rem;
    font-weight: 700;
    margin-bottom: 4px;
}

.subtitle {
    color: var(--text-secondary);
    font-size: 1rem;
    margin-bottom: 32px;
}

/* ---- Avatar ---- */
.avatar-circle {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: var(--accent-gradient);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 700;
    color: white;
    margin-bottom: 8px;
}

/* ---- Progress Bar ---- */
.progress-container {
    background: var(--bg-input);
    border-radius: 12px;
    height: 8px;
    overflow: hidden;
    margin: 8px 0 4px 0;
}

.progress-bar {
    height: 100%;
    border-radius: 12px;
    background: var(--accent-gradient);
    transition: width 0.5s ease;
}

.progress-label {
    color: var(--text-secondary);
    font-size: 13px;
}

/* ---- Application Card ---- */
.app-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
}

.app-card .status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    background: rgba(52, 168, 83, 0.15);
    color: var(--accent-green);
    border: 1px solid rgba(52, 168, 83, 0.3);
}

.app-card .timestamp {
    color: var(--text-muted);
    font-size: 13px;
}

.app-card .job-title {
    color: var(--text-primary);
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 4px;
}

.app-card .company {
    color: var(--text-secondary);
    font-size: 15px;
    margin-bottom: 12px;
}

/* ---- CV File Badge ---- */
.cv-badge {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 10px;
    background: rgba(66, 133, 244, 0.1);
    border: 1px solid rgba(66, 133, 244, 0.3);
    color: var(--accent-blue);
    font-size: 14px;
    font-weight: 500;
    margin: 8px 0;
}

/* ---- Nav Button ---- */
.nav-btn {
    display: block;
    width: 100%;
    padding: 12px 16px;
    border-radius: 12px;
    border: none;
    text-align: left;
    font-size: 15px;
    font-weight: 500;
    cursor: pointer;
    margin-bottom: 4px;
    transition: all 0.2s ease;
    color: var(--text-secondary);
    background: transparent;
}

.nav-btn:hover {
    background: rgba(66, 133, 244, 0.1);
    color: var(--text-primary);
}

.nav-btn.active {
    background: rgba(66, 133, 244, 0.15);
    color: var(--accent-blue);
}

/* ---- Search Bar (Gemini-style) ---- */
.search-container {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 24px;
    padding: 4px;
    margin: 20px 0;
    transition: border-color 0.2s;
}

.search-container:focus-within {
    border-color: var(--accent-blue);
}

/* ---- Review Card ---- */
.review-card {
    background: linear-gradient(135deg, rgba(66,133,244,0.08), rgba(139,92,246,0.08));
    border: 1px solid rgba(139,92,246,0.3);
    border-radius: var(--border-radius);
    padding: 28px;
    margin: 20px 0;
}

/* ---- Job Choice Card ---- */
.job-choice-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
}

.job-choice-card h4 {
    margin: 0 0 8px 0;
    color: var(--text-primary);
    font-size: 16px;
}

.job-choice-card p {
    margin: 0;
    color: var(--text-secondary);
    font-size: 14px;
}

/* ---- Streamlit Overrides ---- */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div,
.stNumberInput > div > div > input {
    background-color: var(--bg-input) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 12px !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent-blue) !important;
    box-shadow: 0 0 0 1px var(--accent-blue) !important;
}

.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
    background: var(--accent-gradient) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    transition: opacity 0.2s !important;
}

.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {
    opacity: 0.9 !important;
}

.stButton > button[kind="secondary"],
.stButton > button[data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 12px !important;
}

div[data-testid="stFileUploader"] {
    background: var(--bg-input) !important;
    border: 2px dashed var(--border-color) !important;
    border-radius: 12px !important;
    padding: 16px !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: transparent !important;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 10px !important;
    color: var(--text-secondary) !important;
    padding: 8px 20px !important;
}

.stTabs [aria-selected="true"] {
    background: rgba(66, 133, 244, 0.15) !important;
    color: var(--accent-blue) !important;
}

.stMarkdown, .stMarkdown p, .stMarkdown li {
    color: var(--text-primary) !important;
}

h1, h2, h3, h4 {
    color: var(--text-primary) !important;
}

.stAlert {
    border-radius: 12px !important;
}

div[data-testid="stForm"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: var(--border-radius) !important;
    padding: 24px !important;
}

.stSpinner > div > div {
    border-top-color: var(--accent-blue) !important;
}

/* ---- Empty State ---- */
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
}

.empty-state .icon {
    font-size: 48px;
    margin-bottom: 16px;
}

.empty-state .message {
    font-size: 16px;
    color: var(--text-secondary);
}

/* ---- Login Page ---- */
.login-container {
    max-width: 440px;
    margin: 0 auto;
    padding-top: 60px;
}

.login-header {
    text-align: center;
    margin-bottom: 40px;
}

.login-header .logo {
    font-size: 48px;
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def get_headers():
    return {"Authorization": f"Bearer {st.session_state['token']}"}

def api_get(endpoint):
    try:
        return requests.get(f"{API_URL}{endpoint}", headers=get_headers())
    except requests.exceptions.ConnectionError:
        return None

def api_post(endpoint, json=None, files=None, params=None):
    try:
        return requests.post(f"{API_URL}{endpoint}", headers=get_headers(), json=json, files=files, params=params)
    except requests.exceptions.ConnectionError:
        return None

def api_put(endpoint, json=None):
    try:
        return requests.put(f"{API_URL}{endpoint}", headers=get_headers(), json=json)
    except requests.exceptions.ConnectionError:
        return None

def api_delete(endpoint):
    try:
        return requests.delete(f"{API_URL}{endpoint}", headers=get_headers())
    except requests.exceptions.ConnectionError:
        return None

def calculate_profile_completeness(profile):
    fields = [
        profile.get("full_name"),
        profile.get("email"),
        profile.get("university"),
        profile.get("degree"),
        profile.get("gpa"),
        profile.get("skills"),
        profile.get("work_experience"),
        profile.get("cv_filename"),
        profile.get("preferred_job_titles"),
        profile.get("preferred_locations"),
    ]
    filled = sum(1 for f in fields if f)
    return int((filled / len(fields)) * 100)

def extract_text(raw_data):
    """Safely extract text from the agent's raw format."""
    if not raw_data:
        return ""
        
    try:
        # Check if it's a string representation of a list of dicts
        if isinstance(raw_data, str) and raw_data.strip().startswith("[{"):
            parsed = ast.literal_eval(raw_data)
            if isinstance(parsed, list) and len(parsed) > 0:
                if isinstance(parsed[0], dict) and "text" in parsed[0]:
                    return parsed[0]["text"]
        
        # If it's directly a list
        if isinstance(raw_data, list) and len(raw_data) > 0:
            if isinstance(raw_data[0], dict) and "text" in raw_data[0]:
                return raw_data[0]["text"]
                
    except Exception as e:
        # If parsing fails, fall back to string
        pass
        
    return str(raw_data)


# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
for key, default in {
    "token": None,
    "username": None,
    "cv_filename": None,
    "page": "finder",
    "pipeline_status": None,
    "tailored_assets": None,
    "scored_jobs": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ============================================================
# LOGIN / SIGNUP PAGE
# ============================================================
if not st.session_state["token"]:
    st.markdown("""
    <div class="login-container">
        <div class="login-header">
            <div class="gradient-title" style="font-size:1.8rem;">AI Job Finder</div>
            <p class="subtitle">Powered by Agentic AI — Find your perfect role</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_spacer1, col_form, col_spacer2 = st.columns([1, 2, 1])
    
    with col_form:
        tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])

        with tab_login:
            with st.form("login_form"):
                login_user = st.text_input("Username", placeholder="Enter your username")
                login_pass = st.text_input("Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)

                if submitted:
                    try:
                        res = requests.post(f"{API_URL}/api/login", json={"username": login_user, "password": login_pass})
                        if res.status_code == 200:
                            data = res.json()
                            st.session_state["token"] = data["access_token"]
                            st.session_state["username"] = data["username"]
                            st.session_state["cv_filename"] = data.get("cv_filename")
                            st.success("Welcome back!")
                            st.rerun()
                        else:
                            st.error("Invalid username or password.")
                    except requests.exceptions.ConnectionError:
                        st.error("Cannot connect to server.")

        with tab_signup:
            with st.form("signup_form"):
                new_user = st.text_input("Choose a Username", placeholder="Pick a unique username")
                new_pass = st.text_input("Create Password", type="password", placeholder="Min 6 characters")
                new_pass_confirm = st.text_input("Confirm Password", type="password", placeholder="Re-enter password")
                signup_submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)

                if signup_submitted:
                    if new_pass != new_pass_confirm:
                        st.error("Passwords do not match!")
                    elif len(new_pass) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        try:
                            res = requests.post(f"{API_URL}/api/signup", json={"username": new_user, "password": new_pass})
                            if res.status_code == 200:
                                st.success("Account created! Switch to Sign In tab to log in.")
                            else:
                                st.error(res.json().get("detail", "Error creating account."))
                        except requests.exceptions.ConnectionError:
                            st.error("Cannot connect to server.")

    st.stop()


# ============================================================
# AUTHENTICATED — SIDEBAR NAVIGATION
# ============================================================
with st.sidebar:
    # User Avatar
    initials = st.session_state["username"][0].upper() if st.session_state["username"] else "?"
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:12px; padding:8px 0 16px 0;">
        <div class="avatar-circle">{initials}</div>
        <div>
            <div style="color:var(--text-primary); font-weight:600; font-size:15px;">{st.session_state['username']}</div>
            <div style="color:var(--text-muted); font-size:12px;">Active</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Navigation
    if st.button("Job Finder", use_container_width=True, type="primary" if st.session_state["page"] == "finder" else "secondary"):
        st.session_state["page"] = "finder"
        st.rerun()

    if st.button("My Profile", use_container_width=True, type="primary" if st.session_state["page"] == "profile" else "secondary"):
        st.session_state["page"] = "profile"
        st.rerun()

    if st.button("Applications", use_container_width=True, type="primary" if st.session_state["page"] == "applications" else "secondary"):
        st.session_state["page"] = "applications"
        st.rerun()

    st.markdown("---")

    # Session config (collapsible)
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
session_id = st.session_state.get("sidebar_session_id", "job_finder_session_1")


# ============================================================
# PAGE: MY PROFILE
# ============================================================
if st.session_state["page"] == "profile":
    st.markdown('<div class="gradient-title">My Profile</div>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Complete your profile to help our AI agents find the best jobs for you</p>', unsafe_allow_html=True)

    # Fetch current profile
    res = api_get("/api/profile")
    if res and res.status_code == 200:
        profile = res.json()
    else:
        profile = {}

    # Profile completeness
    completeness = calculate_profile_completeness(profile)
    st.markdown(f"""
    <div class="gemini-card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
            <span style="color:var(--text-primary); font-weight:600;">Profile Completeness</span>
            <span style="color:var(--accent-blue); font-weight:700; font-size:18px;">{completeness}%</span>
        </div>
        <div class="progress-container">
            <div class="progress-bar" style="width:{completeness}%;"></div>
        </div>
        <p class="progress-label">{'Great job! Your profile is complete.' if completeness == 100 else 'Fill in more details to improve job matching accuracy.'}</p>
    </div>
    """, unsafe_allow_html=True)

    # Profile form
    with st.form("profile_form"):
        # ---- Personal Information ----
        st.markdown('<div class="gemini-card"><h3>Personal Information</h3></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full Name", value=profile.get("full_name", "") or "", placeholder="e.g. John Doe")
            email = st.text_input("Email Address", value=profile.get("email", "") or "", placeholder="john@example.com")
        with col2:
            phone = st.text_input("Phone Number", value=profile.get("phone", "") or "", placeholder="+66 XXX XXX XXXX")

        st.markdown("---")

        # ---- Education ----
        st.markdown('<div class="gemini-card"><h3>Education</h3></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            university = st.text_input("University / Institution", value=profile.get("university", "") or "", placeholder="e.g. Chulalongkorn University")
            degree = st.text_input("Degree / Program", value=profile.get("degree", "") or "", placeholder="e.g. B.Sc. Computer Science")
        with col2:
            gpa = st.number_input("GPA", min_value=0.0, max_value=4.0, step=0.01, value=float(profile.get("gpa") or 0.0), format="%.2f")
            graduation_year = st.number_input("Graduation Year", min_value=2000, max_value=2035, step=1, value=int(profile.get("graduation_year") or 2025))

        st.markdown("---")

        # ---- Skills & Experience ----
        st.markdown('<div class="gemini-card"><h3>Skills & Experience</h3></div>', unsafe_allow_html=True)
        skills = st.text_area(
            "Technical Skills",
            value=profile.get("skills", "") or "",
            placeholder="e.g. Python, Machine Learning, PyTorch, SQL, Docker, LangChain...",
            help="Separate skills with commas"
        )
        work_experience = st.text_area(
            "Work Experience Summary",
            value=profile.get("work_experience", "") or "",
            placeholder="Briefly describe your relevant work experience, internships, or projects...",
            height=120,
        )

        st.markdown("---")

        # ---- Links ----
        st.markdown('<div class="gemini-card"><h3>Links</h3></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            linkedin_url = st.text_input("LinkedIn URL", value=profile.get("linkedin_url", "") or "", placeholder="https://linkedin.com/in/yourprofile")
        with col2:
            github_url = st.text_input("GitHub URL", value=profile.get("github_url", "") or "", placeholder="https://github.com/yourusername")

        st.markdown("---")

        # ---- Job Preferences ----
        st.markdown('<div class="gemini-card"><h3>Job Preferences</h3></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            preferred_job_titles = st.text_input(
                "Preferred Job Titles",
                value=profile.get("preferred_job_titles", "") or "",
                placeholder="e.g. Data Scientist, ML Engineer, AI Developer"
            )
        with col2:
            preferred_locations = st.text_input(
                "Preferred Locations",
                value=profile.get("preferred_locations", "") or "",
                placeholder="e.g. Bangkok, Remote, Singapore"
            )

        # Save button
        save_submitted = st.form_submit_button("Save Profile", type="primary", use_container_width=True)

        if save_submitted:
            payload = {
                "full_name": full_name or None,
                "email": email or None,
                "phone": phone or None,
                "university": university or None,
                "degree": degree or None,
                "gpa": gpa if gpa > 0 else None,
                "graduation_year": graduation_year if graduation_year > 2000 else None,
                "skills": skills or None,
                "work_experience": work_experience or None,
                "linkedin_url": linkedin_url or None,
                "github_url": github_url or None,
                "preferred_job_titles": preferred_job_titles or None,
                "preferred_locations": preferred_locations or None,
            }
            res = api_put("/api/profile", json=payload)
            if res and res.status_code == 200:
                st.success("Profile saved successfully!")
                st.rerun()
            else:
                st.error("Failed to save profile. Please try again.")

    # ---- CV Upload Section (outside form) ----
    st.markdown("---")
    st.markdown('<div class="gemini-card"><h3>Resume / CV</h3></div>', unsafe_allow_html=True)

    cv_filename = profile.get("cv_filename") or st.session_state.get("cv_filename")

    if cv_filename:
        st.markdown(f'<div class="cv-badge">File: {cv_filename}</div>', unsafe_allow_html=True)
        
        col_del, col_spacer = st.columns([1, 3])
        with col_del:
            if st.button("Remove CV", type="secondary"):
                res = api_delete("/api/profile/cv")
                if res and res.status_code == 200:
                    st.session_state["cv_filename"] = None
                    st.success("CV removed successfully.")
                    st.rerun()
                else:
                    st.error("Failed to remove CV.")
    else:
        st.markdown('<p style="color:var(--text-muted);">No CV uploaded yet. Upload a PDF to enhance job matching.</p>', unsafe_allow_html=True)

    uploaded_file = st.file_uploader("Upload your CV (PDF)", type=["pdf"], key="profile_cv_uploader", label_visibility="collapsed")

    if uploaded_file:
        if st.button("Upload & Process CV", type="primary"):
            with st.spinner("Parsing and vectorizing your CV..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                response = api_post("/api/upload-resume", files=files, params={"session_id": session_id})
                if response and response.status_code == 200:
                    st.session_state["cv_filename"] = uploaded_file.name
                    st.success("CV uploaded and processed!")
                    st.rerun()
                else:
                    detail = response.json().get("detail", "Unknown error") if response else "Connection error"
                    st.error(f"Error: {detail}")


# ============================================================
# PAGE: JOB FINDER
# ============================================================
elif st.session_state["page"] == "finder":
    st.markdown('<div class="gradient-title">Job Finder</div>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Let AI agents search, match, and tailor applications for you</p>', unsafe_allow_html=True)

    # Pipeline status display
    if st.session_state.get("pipeline_status") == "paused_for_review":
        # Human-in-the-Loop Review
        st.markdown("""
        <div class="review-card">
            <h3 style="margin-top:0;">Review Required — Select a Job</h3>
            <p style="color:var(--text-secondary);">The AI agents have identified matching jobs for you. Review and select which one to apply to.</p>
        </div>
        """, unsafe_allow_html=True)

        scored_jobs = st.session_state.get("scored_jobs", [])
        
        if not scored_jobs:
            st.warning("No scored jobs found in the pipeline state.")
        else:
            # Let user select a job to apply to
            job_options = {f"{j.get('title', 'Target Role')} at {j.get('company', 'Company')}": j for j in scored_jobs}
            selected_job_label = st.radio("Select a Job Match to Proceed", options=list(job_options.keys()))
            selected_job = job_options[selected_job_label]

            link = selected_job.get('link', '#')
            link_html = f"<a href='{link}' target='_blank' style='color:var(--accent-blue);'>View on LinkedIn</a>" if link and link != '#' else ""

            st.markdown(f"""
            <div class="job-choice-card">
                <h4>{selected_job.get('title', '')} @ {selected_job.get('company', '')}</h4>
                <p><strong>Match Score:</strong> {selected_job.get('match_score', 'N/A')}%</p>
                <p>{selected_job.get('details', '')}</p>
                <p style="margin-top:8px;">{link_html}</p>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("View Generated Cover Letter / Resume Updates"):
                # Nicely format the raw text
                formatted_assets = extract_text(st.session_state.get("tailored_assets", ""))
                st.markdown(formatted_assets)

            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("Approve & Apply", type="primary", use_container_width=True):
                    with st.spinner("Finalizing application..."):
                        payload = {
                            "session_id": session_id,
                            "feedback": "approve",
                            "job_title": selected_job.get('title', 'Target Role'),
                            "company": selected_job.get('company', 'Target Company')
                        }
                        res = api_post("/api/job-finder/resume", json=payload)
                        if res and res.status_code == 200:
                            st.success("Application approved and logged!")
                            st.session_state["pipeline_status"] = "completed"
                            st.rerun()
                        else:
                            st.error("Failed to resume pipeline.")
            with col2:
                if st.button("Reject All", type="secondary", use_container_width=True):
                    st.session_state["pipeline_status"] = None
                    st.warning("Rejected. You can start a new search.")
                    st.rerun()

    elif st.session_state.get("pipeline_status") == "completed":
        st.success("Last pipeline completed successfully! Start a new search below.")
        st.session_state["pipeline_status"] = None

    # Search interface
    st.markdown("---")
    
    st.markdown("""
    <div class="gemini-card">
        <h3>Start a Job Search</h3>
        <p style="color:var(--text-secondary); margin-bottom:16px;">
            Describe what kind of job you're looking for. The AI agents will search, evaluate matches, and generate tailored application materials.
        </p>
    </div>
    """, unsafe_allow_html=True)

    search_query = st.text_input(
        "What role are you looking for?",
        value="Find Data Scientist jobs in Thailand",
        placeholder="e.g. Find ML Engineer roles in Bangkok with PyTorch experience",
        label_visibility="collapsed",
    )

    if st.button("Start AI Agent Pipeline", type="primary", use_container_width=True):
        with st.spinner("Agents are searching, screening, and tailoring..."):
            payload = {"session_id": session_id, "query": search_query}
            response = api_post("/api/job-finder/start", json=payload)

            if response and response.status_code == 200:
                data = response.json()
                st.session_state["pipeline_status"] = data["status"]
                st.session_state["tailored_assets"] = data.get("tailored_assets", "No assets found.")
                st.session_state["scored_jobs"] = data.get("scored_jobs", [])
                st.rerun()
            elif response:
                st.error(f"Error: {response.json().get('detail', response.text)}")
            else:
                st.error("Cannot connect to backend server.")

    # Pipeline stages info
    with st.expander("How the AI Agent Pipeline Works"):
        st.markdown("""
        The pipeline runs through **5 stages**:
        
        | Stage | Agent | Description |
        |-------|-------|-------------|
        | 1 | **Job Discovery** | Searches LinkedIn for relevant positions using your profile |
        | 2 | **Matching & Screening** | Evaluates jobs against your skills and assigns match scores |
        | 3 | **Asset Tailoring** | Generates a tailored cover letter and resume bullet points |
        | 4 | **Human Review** | You review and approve/reject the generated materials |
        | 5 | **Application Tracker** | Logs approved applications to your tracker |
        """)


# ============================================================
# PAGE: APPLICATIONS
# ============================================================
elif st.session_state["page"] == "applications":
    st.markdown('<div class="gradient-title">Application Tracker</div>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Track all jobs you\'ve reviewed and approved through the AI pipeline</p>', unsafe_allow_html=True)

    def update_status(app_id, key):
        new_status = st.session_state[key]
        res = api_put(f"/api/applications/{app_id}/status", json={"status": new_status})
        if res and res.status_code == 200:
            st.toast(f"Updated status to {new_status}")
        else:
            st.error("Failed to update status")

    res = api_get("/api/applications")

    if res and res.status_code == 200:
        apps_data = res.json()

        if not apps_data:
            st.markdown("""
            <div class="empty-state">
                <div class="message">No applications yet.<br>Run the Job Finder pipeline and approve a role to start tracking!</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"**{len(apps_data)}** application{'s' if len(apps_data) != 1 else ''} tracked")
            st.markdown("---")

            status_options = ["Applied", "Interviewed", "Pending", "Rejected", "Offer"]

            for app in apps_data:
                app_id = app.get("id")
                timestamp = app.get("timestamp", "N/A")
                job_title = app.get("job_title", "Untitled")
                company = app.get("company", "Unknown")
                status = app.get("status", "Applied")
                
                if status not in status_options:
                    status_options.append(status)

                # Ensure status is in options list
                try:
                    default_index = status_options.index(status)
                except ValueError:
                    default_index = 0

                st.markdown(f"""
                <div class="app-card">
                    <div class="job-title">{job_title}</div>
                    <div class="company">{company}</div>
                    <div class="timestamp" style="margin-bottom:12px;">Added on {timestamp}</div>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 2])
                with col1:
                    select_key = f"status_{app_id}"
                    st.selectbox(
                        "Status", 
                        options=status_options, 
                        index=default_index, 
                        key=select_key,
                        on_change=update_status,
                        args=(app_id, select_key),
                        label_visibility="collapsed"
                    )
                with col2:
                    with st.expander("View Application Assets"):
                        formatted_preview = extract_text(app.get("assets_preview", ""))
                        st.markdown(formatted_preview)
                
                st.markdown("<br>", unsafe_allow_html=True)
                
    elif res:
        st.error("Failed to load applications.")
    else:
        st.error("Cannot connect to backend server.")