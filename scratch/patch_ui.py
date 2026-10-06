import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# We need to replace the `sessions_res = api_get("/api/chat-sessions")` loop inside the sidebar.
sidebar_loop_target = '''    sessions_res = api_get("/api/chat-sessions")
    if sessions_res and sessions_res.status_code == 200:
        sessions = sessions_res.json()
        for s in sessions:
            # Highlight active session
            is_active = st.session_state.get("sidebar_session_id") == s["session_id"]
            if st.button(f"💬 {s['title'][:20]}", key=f"session_{s['session_id']}", use_container_width=True, type="primary" if is_active else "secondary"):
                st.session_state["sidebar_session_id"] = s["session_id"]
                st.session_state["pipeline_status"] = "idle"
                st.session_state["page"] = "finder"
                st.rerun()'''

new_sidebar_loop = '''    sessions_res = api_get("/api/chat-sessions")
    if sessions_res and sessions_res.status_code == 200:
        sessions = sessions_res.json()
        for s in sessions:
            is_active = st.session_state.get("sidebar_session_id") == s["session_id"]
            
            # Create a row for the session button and the settings popover
            col1, col2 = st.columns([8, 2])
            with col1:
                if st.button(f"💬 {s['title'][:15]}", key=f"session_{s['session_id']}", use_container_width=True, type="primary" if is_active else "secondary"):
                    st.session_state["sidebar_session_id"] = s["session_id"]
                    st.session_state["pipeline_status"] = "idle"
                    st.session_state["page"] = "finder"
                    st.rerun()
            with col2:
                with st.popover("⚙️"):
                    st.markdown("**Rename Chat**")
                    new_title = st.text_input("Title", value=s["title"], key=f"rename_{s['session_id']}", label_visibility="collapsed")
                    if st.button("Save", key=f"save_{s['session_id']}", use_container_width=True):
                        res = api_put(f"/api/chat-sessions/{s['session_id']}", json={"title": new_title})
                        if res and res.status_code == 200:
                            st.rerun()
                    
                    st.markdown("---")
                    if st.button("🗑️ Delete", key=f"del_{s['session_id']}", use_container_width=True, type="primary"):
                        res = api_delete(f"/api/chat-sessions/{s['session_id']}")
                        if res and res.status_code == 200:
                            if st.session_state.get("sidebar_session_id") == s["session_id"]:
                                st.session_state["sidebar_session_id"] = None
                            st.rerun()'''

if sidebar_loop_target in content:
    content = content.replace(sidebar_loop_target, new_sidebar_loop)
else:
    print("Could not find the target loop block!")

# We also need to add api_put and api_delete helpers to app.py if they don't exist
# Look for def api_post
api_helpers_target = '''def api_post(endpoint, json=None, files=None, params=None):
    try:
        return requests.post(f"{API_URL}{endpoint}", headers=get_headers(), json=json, files=files, params=params)
    except requests.exceptions.ConnectionError:
        return None'''

api_put_delete_helpers = '''def api_put(endpoint, json=None):
    try:
        return requests.put(f"{API_URL}{endpoint}", headers=get_headers(), json=json)
    except requests.exceptions.ConnectionError:
        return None

def api_delete(endpoint):
    try:
        return requests.delete(f"{API_URL}{endpoint}", headers=get_headers())
    except requests.exceptions.ConnectionError:
        return None'''

if "def api_put" not in content and api_helpers_target in content:
    content = content.replace(api_helpers_target, api_helpers_target + "\n\n" + api_put_delete_helpers)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("app.py patched!")
