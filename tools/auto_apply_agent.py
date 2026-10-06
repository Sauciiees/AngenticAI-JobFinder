"""
Auto-Apply Browser Agent
========================
Uses Playwright + Gemini Vision to autonomously fill out job application forms.

Architecture:
1. LABEL: Inject numbered labels onto every interactive element on the page
2. SCREENSHOT: Capture the labeled page as a PNG
3. REASON: Send screenshot to Gemini Vision LLM to decide the next action
4. ACT: Execute the action (click, type, upload, select, etc.) via Playwright
5. LOOP: Repeat until form is submitted or max steps reached

Runs in headless=False mode so the user can intervene for CAPTCHAs.
"""

import os
import json
import base64
import time
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


# --- Constants ---
MAX_ACTIONS = 30
PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "browser_profile")
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")

# JavaScript to inject numbered labels on every interactive element
LABEL_INJECTION_JS = """
() => {
    // Create a container in the Top Layer using popover to bypass ALL z-index and native <dialog> overlay issues
    let container = document.getElementById('agy-label-container');
    if (container) container.remove();
    
    container = document.createElement('div');
    container.id = 'agy-label-container';
    container.popover = 'manual'; // Puts it in the Top Layer
    container.style.cssText = 'position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 2147483647; background: transparent; border: none; padding: 0; margin: 0; overflow: visible;';
    document.body.appendChild(container);
    try { container.showPopover(); } catch(e) {}

    const interactiveSelectors = [
        'input:not([type="hidden"])',
        'textarea',
        'select',
        'button',
        'a[href]',
        '[role="button"]',
        '[role="link"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="combobox"]',
        '[role="listbox"]',
        '[role="menuitem"]',
        '[role="tab"]',
        '[contenteditable="true"]',
        'label[for]',
    ];

    const elements = document.querySelectorAll(interactiveSelectors.join(','));
    let id = 1;
    const elementMap = {};
    window.__agyElements = {}; // Store direct references to DOM nodes

    elements.forEach(el => {
        const isFileInput = el.tagName.toLowerCase() === 'input' && el.getAttribute('type') === 'file';
        
        const rect = el.getBoundingClientRect();
        
        // Draw labels for all elements that have a valid coordinate
        if (rect.width === 0 && rect.height === 0) return;
        if (rect.top > window.innerHeight || rect.bottom < 0) return;
        if (rect.left > window.innerWidth || rect.right < 0) return;

        // Create label
        if (!isFileInput) {
            const label = document.createElement('div');
            label.textContent = id;
            label.style.cssText = `
                position: absolute;
                top: ${rect.top + window.scrollY - 10}px;
                left: ${rect.left + window.scrollX - 10}px;
                background: #FF0000;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 4px;
                pointer-events: none;
                font-family: sans-serif;
                box-shadow: 0 2px 4px rgba(0,0,0,0.5);
                border: 1px solid white;
            `;
            container.appendChild(label);
        }

        // Store element info
        window.__agyElements[id] = el;
        elementMap[id] = {
            tag: el.tagName.toLowerCase(),
            type: el.getAttribute('type') || '',
            name: el.getAttribute('name') || '',
            id: el.getAttribute('id') || '',
            placeholder: el.getAttribute('placeholder') || '',
            text: (el.innerText || '').substring(0, 80),
            value: el.value || '',
            ariaLabel: el.getAttribute('aria-label') || '',
        };
        id++;
    });

    return elementMap;
}
"""

# JavaScript to get the element map without re-injecting labels
GET_ELEMENT_MAP_JS = "() => window.__agyElementMap || {}"


def _get_vision_llm():
    """Initialize a Gemini Vision model for screenshot analysis."""
    import google.genai as genai
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    return client


def _screenshot_to_base64(screenshot_bytes: bytes) -> str:
    """Convert screenshot bytes to base64 string."""
    return base64.b64encode(screenshot_bytes).encode("utf-8").decode("utf-8")


def _build_vision_prompt(
    user_profile: dict,
    element_map: dict,
    action_history: list,
    error_message: str = "",
    cv_filepath: str = "",
) -> str:
    """Build the prompt for the vision LLM to decide the next action."""
    
    name = user_profile.get("full_name", "")
    email = user_profile.get("email", "")
    phone = user_profile.get("phone", "")
    university = user_profile.get("university", "")
    degree = user_profile.get("degree", "")
    gpa = user_profile.get("gpa", "")
    skills = user_profile.get("skills", "")
    work_experience = user_profile.get("work_experience", "")
    
    history_text = ""
    if action_history:
        recent = action_history[-5:]  # Last 5 actions
        history_text = "Recent actions taken:\n" + "\n".join(
            [f"  Step {i+1}: {a}" for i, a in enumerate(recent)]
        )
    
    error_text = ""
    if error_message:
        error_text = f"\n!! PREVIOUS ACTION FAILED: {error_message}\nPlease try a different approach.\n"
    
    # Compact element map for context
    elem_summary = ""
    for eid, info in element_map.items():
        parts = [f"[{eid}] <{info['tag']}"]
        if info.get('type'): parts.append(f" type={info['type']}")
        if info.get('placeholder'): parts.append(f" placeholder=\"{info['placeholder']}\"")
        if info.get('name'): parts.append(f" name=\"{info['name']}\"")
        if info.get('ariaLabel'): parts.append(f" aria-label=\"{info['ariaLabel']}\"")
        if info.get('text') and info['tag'] in ['button', 'a', 'label']:
            parts.append(f" text=\"{info['text'][:50]}\"")
        if info.get('value'):
            parts.append(f" value=\"{info['value'][:30]}\"")
        parts.append(">")
        elem_summary += "".join(parts) + "\n"
    
    return f"""You are an AI agent filling out a job application form in a web browser.

APPLICANT INFORMATION (use this data to fill forms):
- Full Name: {name}
- Email: {email}
- Phone: {phone or 'Not provided'}
- University: {university}
- Degree: {degree}
- GPA: {gpa}
- Skills: {skills}
- Work Experience: {work_experience or 'See CV'}
- CV File Path: {cv_filepath or 'Not available'}

{error_text}
{history_text}

INTERACTIVE ELEMENTS ON THE PAGE (each has a red numbered label visible in the screenshot):
{elem_summary}

INSTRUCTIONS:
1. Look at the screenshot. Each interactive element has a red numbered label.
2. Decide the single best NEXT action to progress through the application form.
3. CRITICAL: If you do not see the expected "Next", "Review", or "Submit Application" button on the screen, it is likely off-screen. Use the "scroll_down" action to scroll the page and look for it! Do NOT guess random elements.
4. CRITICAL: If the "Review" or "Submit" button is visible but GREYED OUT (disabled), it means you missed a required field! Look carefully at all empty input fields and fill them out.
5. If you see a CAPTCHA or "verify you are human" challenge, respond with the "captcha" action.
6. If you see a success/confirmation page (e.g. "Application submitted", "Thank you"), respond with the "done" action.
7. If you see a cookie consent banner or popup blocking the form, dismiss it first.
8. For file upload fields (resume/CV), use the "upload" action.
9. Fill fields in logical order: name, email, phone, then other fields.
10. Do NOT re-fill fields that already have correct values.

Respond with EXACTLY ONE JSON object (no markdown, no explanation):
{{"action": "<action_type>", "element_id": <number>, "value": "<text_to_type>"}}

Valid action types:
- "click": Click element. No "value" needed.
- "type": Clear and type into input/textarea. Provide "value".
- "select": Select dropdown option. Provide "value" with option text.
- "upload": Upload file. Provide "value" with file path.
- "scroll_down": Scroll page down. No element_id or value needed.
- "scroll_up": Scroll page up. No element_id or value needed.
- "captcha": Pause for human to solve CAPTCHA. No element_id or value needed.
- "done": Application submitted successfully. No element_id or value needed.
- "stuck": Cannot proceed further. No element_id or value needed.

Respond with ONLY the JSON object."""


def _parse_llm_action(response_text: str) -> dict:
    """Parse the LLM's JSON action response."""
    try:
        # Try to extract JSON from response
        match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
        if match:
            action = json.loads(match.group(0))
            return action
    except Exception:
        pass
    return {"action": "stuck", "reason": f"Failed to parse LLM response: {response_text[:200]}"}


def _execute_action(page, action: dict, element_map: dict) -> str:
    """Execute a single action on the Playwright page. Returns error message or empty string."""
    action_type = action.get("action", "")
    element_id = action.get("element_id")
    value = action.get("value", "")
    
    # We use page.evaluate to execute directly on the DOM node to bypass React stripping attributes
    try:
        if action_type == "click":
            # Temporarily re-add the attribute in case React stripped it, then use Playwright's robust click
            # which automatically handles scrolling, waiting for stability, and actionability checks
            page.evaluate(f"window.__agyElements[{element_id}].scrollIntoView({{behavior: 'auto', block: 'center'}})")
            page.evaluate(f"window.__agyElements[{element_id}].setAttribute('data-agy-id', '{element_id}')")
            el = page.locator(f'[data-agy-id="{element_id}"]')
            el.click(timeout=5000)
            return ""
            
        elif action_type == "type":
            page.evaluate(f"window.__agyElements[{element_id}].scrollIntoView({{behavior: 'auto', block: 'center'}})")
            page.wait_for_timeout(500)
            # Use Playwright locator for typing to simulate actual keystrokes
            # Since React might strip data-agy-id, we temporarily re-add it
            page.evaluate(f"window.__agyElements[{element_id}].setAttribute('data-agy-id', '{element_id}')")
            el = page.locator(f'[data-agy-id="{element_id}"]')
            el.click(timeout=3000)
            el.fill(value, timeout=5000)
            return ""
            
        elif action_type == "select":
            page.evaluate(f"window.__agyElements[{element_id}].scrollIntoView({{behavior: 'auto', block: 'center'}})")
            page.wait_for_timeout(500)
            page.evaluate(f"window.__agyElements[{element_id}].setAttribute('data-agy-id', '{element_id}')")
            el = page.locator(f'[data-agy-id="{element_id}"]')
            try:
                el.select_option(label=value, timeout=5000)
            except Exception:
                el.select_option(value=value, timeout=5000)
            return ""
            
        elif action_type == "upload":
            filepath = value
            if not (filepath and os.path.exists(filepath)):
                return f"File not found: {filepath}"
                
            box = page.evaluate(f"""(() => {{
                const el = window.__agyElements[{element_id}];
                const rect = el.getBoundingClientRect();
                return {{x: rect.left + rect.width / 2, y: rect.top + rect.height / 2}};
            }})()""")
            
            try:
                # Try clicking the element and waiting for a file chooser (works for buttons)
                with page.expect_file_chooser(timeout=3000) as fc_info:
                    if box:
                        page.mouse.click(box['x'], box['y'])
                    else:
                        page.evaluate(f"window.__agyElements[{element_id}].click()")
                file_chooser = fc_info.value
                file_chooser.set_files(filepath)
                return ""
            except Exception:
                # Fallback: try setting input files directly if it's an input element
                try:
                    page.evaluate(f"window.__agyElements[{element_id}].setAttribute('data-agy-id', '{element_id}')")
                    el = page.locator(f'[data-agy-id="{element_id}"]')
                    el.set_input_files(filepath, timeout=3000)
                    return ""
                except Exception as e:
                    return f"Failed to upload: {str(e)}"
                
        elif action_type == "scroll_down":
            viewport = page.viewport_size
            if viewport:
                page.mouse.move(viewport['width'] / 2, viewport['height'] / 2)
            page.mouse.wheel(0, 500)
            return ""
            
        elif action_type == "scroll_up":
            viewport = page.viewport_size
            if viewport:
                page.mouse.move(viewport['width'] / 2, viewport['height'] / 2)
            page.mouse.wheel(0, -500)
            return ""
            
        elif action_type in ["captcha", "done", "stuck"]:
            return ""  # These are handled by the main loop
            
        else:
            return f"Unknown action type: {action_type}"
            
    except Exception as e:
        return f"Action failed on element [{element_id}]: {str(e)[:200]}"


def auto_apply_to_job(
    job_url: str,
    user_profile: dict,
    cv_filepath: str = "",
    on_status_update=None,
    on_captcha_detected=None,
) -> dict:
    """
    Main entry point: Autonomously applies to a single job using vision-driven browser automation.
    
    Args:
        job_url: The URL of the job application page.
        user_profile: Dict with full_name, email, phone, university, degree, gpa, skills, work_experience.
        cv_filepath: Absolute path to the user's CV/resume PDF file.
        on_status_update: Optional callback(step, action_description) for progress updates.
        on_captcha_detected: Optional callback() that blocks until human solves CAPTCHA.
    
    Returns:
        dict with keys:
            - "success": bool
            - "steps_taken": int
            - "final_status": str ("submitted", "captcha_timeout", "stuck", "max_steps_reached", "error")
            - "screenshot_path": str (path to final screenshot)
            - "action_log": list of action descriptions
    """
    from playwright.sync_api import sync_playwright
    
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    os.makedirs(PROFILE_DIR, exist_ok=True)
    
    vision_client = _get_vision_llm()
    action_history = []
    result = {
        "success": False,
        "steps_taken": 0,
        "final_status": "error",
        "screenshot_path": "",
        "action_log": [],
    }
    
    try:
        with sync_playwright() as p:
            # Launch browser with persistent profile (keeps login sessions)
            browser = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=False,  # Visible so user can solve CAPTCHAs
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            )
            
            page = browser.new_page()
            
            # Navigate to job URL
            if on_status_update:
                on_status_update(0, f"Opening {job_url}")
            
            page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)  # Wait for page to fully render
            
            for step in range(1, MAX_ACTIONS + 1):
                result["steps_taken"] = step
                
                # ALWAYS focus on the most recently opened tab
                pages = browser.pages
                if pages:
                    page = pages[-1]
                    page.bring_to_front()
                
                if on_status_update:
                    on_status_update(step, f"Step {step}/{MAX_ACTIONS}: Analyzing page...")
                
                # 1. LABEL: Inject numbered labels
                try:
                    element_map = page.evaluate(LABEL_INJECTION_JS)
                except Exception as e:
                    print(f"Label injection failed: {e}")
                    element_map = {}
                
                if not element_map:
                    # Page might have navigated, wait and retry
                    page.wait_for_timeout(2000)
                    try:
                        element_map = page.evaluate(LABEL_INJECTION_JS)
                    except Exception:
                        element_map = {}
                
                # 2. SCREENSHOT: Capture the labeled page
                screenshot_path = os.path.join(SCREENSHOT_DIR, f"step_{step}.png")
                screenshot_bytes = page.screenshot(full_page=False)
                with open(screenshot_path, "wb") as f:
                    f.write(screenshot_bytes)
                result["screenshot_path"] = screenshot_path
                
                # 3. REASON: Send to Gemini Vision
                error_msg = action_history[-1].split(" | Error: ")[1] if action_history and "| Error:" in action_history[-1] else ""
                
                prompt = _build_vision_prompt(
                    user_profile=user_profile,
                    element_map=element_map,
                    action_history=action_history,
                    error_message=error_msg,
                    cv_filepath=cv_filepath,
                )
                
                try:
                    import google.genai as genai
                    
                    response = vision_client.models.generate_content(
                        model="gemini-3.1-flash-lite",
                        contents=[
                            genai.types.Part.from_bytes(
                                data=screenshot_bytes,
                                mime_type="image/png",
                            ),
                            prompt,
                        ],
                    )
                    llm_response = response.text
                except Exception as e:
                    print(f"Vision LLM error: {e}")
                    action_history.append(f"Step {step}: Vision LLM failed - {str(e)[:100]}")
                    continue
                
                # 4. PARSE: Extract action from LLM response
                action = _parse_llm_action(llm_response)
                action_type = action.get("action", "stuck")
                
                action_desc = f"Step {step}: {action_type}"
                if action.get("element_id"):
                    action_desc += f" on [{action['element_id']}]"
                if action.get("value"):
                    safe_val = action['value'][:50].encode('ascii', 'ignore').decode('ascii')
                    action_desc += f" value=\"{safe_val}\""
                
                if on_status_update:
                    on_status_update(step, action_desc)
                
                # 5. HANDLE SPECIAL ACTIONS
                if action_type == "done":
                    result["success"] = True
                    result["final_status"] = "submitted"
                    action_history.append(f"Step {step}: DONE - Application submitted!")
                    result["action_log"] = action_history
                    # Take final screenshot
                    final_ss = os.path.join(SCREENSHOT_DIR, "final_success.png")
                    page.screenshot(path=final_ss, full_page=False)
                    result["screenshot_path"] = final_ss
                    break
                
                if action_type == "captcha":
                    action_history.append(f"Step {step}: CAPTCHA detected - waiting for human")
                    if on_captcha_detected:
                        on_captcha_detected()  # This blocks until human resolves
                    else:
                        # Default: wait 30 seconds for manual intervention
                        print("CAPTCHA detected! Please solve it in the browser window...")
                        page.wait_for_timeout(30000)
                    continue
                
                if action_type == "stuck":
                    result["final_status"] = "stuck"
                    action_history.append(f"Step {step}: STUCK - Agent cannot proceed")
                    result["action_log"] = action_history
                    break
                
                # 6. ACT: Execute the action
                error = _execute_action(page, action, element_map)
                if error:
                    action_desc += f" | Error: {error}"
                
                action_history.append(action_desc)
                
                # Wait for page to react
                page.wait_for_timeout(1500)
            
            else:
                # Max steps reached
                result["final_status"] = "max_steps_reached"
            
            result["action_log"] = action_history
            
            # Final screenshot
            try:
                final_ss = os.path.join(SCREENSHOT_DIR, "final_state.png")
                page.screenshot(path=final_ss, full_page=False)
                result["screenshot_path"] = final_ss
            except Exception:
                pass
            
            browser.close()
    
    except Exception as e:
        result["final_status"] = "error"
        result["action_log"] = action_history + [f"Fatal error: {str(e)[:300]}"]
        print(f"Auto-apply agent error: {e}")
    
    return result


def auto_apply_to_jobs(
    jobs: list,
    user_profile: dict,
    cv_filepath: str = "",
    on_job_status_update=None,
) -> list:
    """
    Apply to multiple jobs sequentially.
    
    Args:
        jobs: List of job dicts, each with at least "title", "company", "link".
        user_profile: User profile dict.
        cv_filepath: Path to CV file.
        on_job_status_update: Optional callback(job_index, job_title, status_message).
    
    Returns:
        List of result dicts, one per job.
    """
    results = []
    
    for i, job in enumerate(jobs):
        title = job.get("title", "Unknown")
        company = job.get("company", "Unknown")
        url = job.get("link", "")
        
        safe_title = title.encode('ascii', 'ignore').decode('ascii')
        print(f"\n{'='*50}")
        print(f"Auto-applying (v2) to: {safe_title} at {company}")
        print(f"URL: {url}")
        print(f"{'='*50}")
        
        if not url:
            results.append({
                "job": job,
                "success": False,
                "final_status": "no_url",
                "steps_taken": 0,
                "action_log": ["No application URL provided"],
            })
            continue
        
        if on_job_status_update:
            on_job_status_update(i, title, "Starting application...")
        
        def status_callback(step, desc):
            if on_job_status_update:
                on_job_status_update(i, title, desc)
        
        result = auto_apply_to_job(
            job_url=url,
            user_profile=user_profile,
            cv_filepath=cv_filepath,
            on_status_update=status_callback,
        )
        result["job"] = job
        results.append(result)
        
        if on_job_status_update:
            status = "Success" if result["success"] else result["final_status"]
            on_job_status_update(i, title, f"Finished: {status}")
    
    return results
