import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target_block = '''            for idx, job in enumerate(raw_jobs):
                is_selected = st.checkbox(f"**{job.get('title')}** at {job.get('company')}", value=idx in st.session_state.get("selected_job_indices", []), key=f"job_{idx}")
                current_selections = st.session_state.get("selected_job_indices", [])
                if is_selected and idx not in current_selections:
                    current_selections.append(idx)
                elif not is_selected and idx in current_selections:
                    current_selections.remove(idx)
                st.session_state["selected_job_indices"] = current_selections'''

new_block = '''            st.markdown("<br>", unsafe_allow_html=True)
            for idx, job in enumerate(raw_jobs):
                with st.container(border=True):
                    col1, col2, col3 = st.columns([1, 8, 2])
                    
                    company_name = job.get('company', 'Unknown')
                    
                    # Generate logo URL using Clearbit
                    logo_url = "https://ui-avatars.com/api/?name=Job&background=random"
                    if company_name and company_name != "Unknown Company" and company_name != "Unknown":
                        domain_guess = company_name.split()[0].lower() + ".com"
                        # We use an img tag with an onerror fallback
                        logo_html = f'<img src="https://logo.clearbit.com/{domain_guess}" onerror="this.onerror=null; this.src=\'https://ui-avatars.com/api/?name={company_name}&background=random\';" width="50" style="border-radius: 8px;">'
                    else:
                        logo_html = f'<img src="{logo_url}" width="50" style="border-radius: 8px;">'
                        
                    with col1:
                        st.markdown(logo_html, unsafe_allow_html=True)
                        
                    with col2:
                        st.markdown(f"**{job.get('title')}**")
                        st.markdown(f"🏢 **{company_name}** &nbsp;•&nbsp; 🕒 {job.get('date', 'Unknown')}")
                        st.caption(job.get('snippet', 'No description preview available.')[:150] + "...")
                        st.markdown(f"[View Job on {job.get('platform', 'Website')}]({job.get('link', '#')})")
                        
                    with col3:
                        is_selected = st.checkbox("Select", value=idx in st.session_state.get("selected_job_indices", []), key=f"job_{idx}")
                        
                current_selections = st.session_state.get("selected_job_indices", [])
                if is_selected and idx not in current_selections:
                    current_selections.append(idx)
                elif not is_selected and idx in current_selections:
                    current_selections.remove(idx)
                st.session_state["selected_job_indices"] = current_selections'''

if target_block in content:
    content = content.replace(target_block, new_block)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced job card UI!")
else:
    print("Could not find target block!")
