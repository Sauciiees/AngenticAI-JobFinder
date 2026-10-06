import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update the Sidebar
# We need to find the sidebar section.
# The sidebar currently has:
# Navigation (Job Finder, My Profile, Applications)
# Chat History
# Search Settings (Time Filter)
# Spacer + Logout

sidebar_start = content.find('with st.sidebar:')
sidebar_end = content.find('# Get session_id from sidebar, or create one')

if sidebar_start != -1 and sidebar_end != -1:
    old_sidebar_code = content[sidebar_start:sidebar_end]
    
    new_sidebar_code = '''with st.sidebar:
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
    st.markdown("### Chat History")
    
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        res = api_post("/api/chat-sessions", json={"title": "New Chat"})
        if res and res.status_code == 200:
            st.session_state["sidebar_session_id"] = res.json()["session_id"]
            st.session_state["pipeline_status"] = "idle"
            st.session_state["page"] = "finder"
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
                st.session_state["page"] = "finder"
                st.rerun()

    st.markdown("---")
    st.markdown("### Account")
    # Navigation
    if st.button("My Profile", use_container_width=True, type="primary" if st.session_state["page"] == "profile" else "secondary"):
        st.session_state["page"] = "profile"
        st.rerun()

    if st.button("Applications", use_container_width=True, type="primary" if st.session_state["page"] == "applications" else "secondary"):
        st.session_state["page"] = "applications"
        st.rerun()

    # Spacer + Logout
    st.markdown("<br>" * 3, unsafe_allow_html=True)
    if st.button("Log Out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

'''
    content = content.replace(old_sidebar_code, new_sidebar_code)
else:
    print("Could not find sidebar block")

# 2. Add time filter to the Chat Input block, and remove old search text input!
# First, let's remove the old search input.
# The old search input is probably around line 1078 to 1145, inside the `if st.session_state.get("page") == "finder":`? Wait, we have the old `elif st.session_state.get("pipeline_status") == "completed":`
# Let's search for `# Search interface` down to `# Pipeline stages info` and remove it entirely.

search_ui_start = content.find('# Search interface')
pipeline_info_start = content.find('# Pipeline stages info')

if search_ui_start != -1 and pipeline_info_start != -1:
    old_search_ui = content[search_ui_start:pipeline_info_start]
    content = content.replace(old_search_ui, "")
else:
    print("Could not find old search UI")

# 3. Add Time Filter pill above st.chat_input
chat_input_line = 'prompt = st.chat_input("Ask a question or search for a job...")'
new_chat_input_block = '''with st.container(border=False):
        # We put the time filter right above the chat input
        time_options = {
            "Past 24 hours": "qdr:d",
            "Past week": "qdr:w",
            "Past month": "qdr:m",
        }
        selected_time_label = st.radio("Search timeframe:", options=list(time_options.keys()), index=1, horizontal=True)
        st.session_state["time_filter"] = time_options[selected_time_label]
        
    # Chat Input (Sticky at Bottom)
    prompt = st.chat_input("Ask a question or search for a job...")'''
    
if chat_input_line in content:
    content = content.replace('    # Chat Input (Sticky at Bottom)\n    ' + chat_input_line, new_chat_input_block)
else:
    print("Could not find st.chat_input")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("app.py patched for sidebar and time filter!")
