import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove the active "Job Finder" title and subtitle from the new finder block
title_block = """    st.markdown('<div class="gradient-title">Job Finder</div>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Chat with AI to search for jobs, or let it run the pipeline</p>', unsafe_allow_html=True)"""
if title_block in content:
    content = content.replace(title_block, "")
else:
    print("Could not find active title block")

# 2. Completely remove the old duplicate PAGE: JOB FINDER block
# Let's use regex or string finding to remove from `elif st.session_state["page"] == "finder":` down to the next PAGE: MY PROFILE or PAGE: APPLICATIONS.
# In the file, it is:
# elif st.session_state["page"] == "finder":
# ...
# # ============================================================
# # PAGE: APPLICATIONS
# # ============================================================
# elif st.session_state["page"] == "applications":

old_finder_start = content.find('elif st.session_state["page"] == "finder":')
applications_start = content.find('elif st.session_state["page"] == "applications":')
# Wait, before applications there is the comment header for APPLICATIONS
# Let's search for `# PAGE: APPLICATIONS`
apps_marker = content.find('# PAGE: APPLICATIONS')

if old_finder_start != -1 and apps_marker != -1 and old_finder_start < apps_marker:
    # also remove the header before it if possible, but it doesn't hurt to just remove from `elif` to `apps_marker - 60` or so
    # The header is `# ============================================================ \n# PAGE: JOB FINDER`
    header_start = content.rfind('# PAGE: JOB FINDER', 0, old_finder_start)
    if header_start != -1:
        start_cut = content.rfind('# =====', 0, header_start)
        if start_cut != -1:
            old_finder_start = start_cut
            
    # now cut it out
    content = content[:old_finder_start] + content[apps_marker - 61:]
    print("Removed duplicate finder block.")
else:
    print("Could not find old finder block or applications marker")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("app.py cleaned!")
