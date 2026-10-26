"""
Auto-Apply Browser Agent
========================
Uses Playwright + Gemini Vision to autonomously fill out job application forms.

Architecture (pure vision: nothing is injected into the page):
1. SCREENSHOT: Capture the page exactly as the applicant would see it
2. REASON: Gemini Vision picks the next action and points at its target on the screenshot
3. ACT: Real mouse and keyboard input at that point via Playwright (click, type, select, upload)
4. LOOP: Repeat until form is submitted or max steps reached

Runs in headless=False mode so the user can intervene for CAPTCHAs.
"""

import os
import json
import time
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


# --- Constants ---
MAX_ACTIONS = 30
PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "browser_profile")
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")

# The vision model answers with points on a 0-1000 grid over the screenshot ([y, x], Gemini's convention).
POINT_SCALE = 1000


def _get_vision_llm():
    """Initialize a Gemini Vision model for screenshot analysis."""
    import google.genai as genai
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    return client


def _build_vision_prompt(
    user_profile: dict,
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
    
    return f"""You are an AI agent filling out a job application form in a web browser. You see a screenshot of
the browser and act on it with a mouse and keyboard.

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

HOW TO POINT:
Locate the element you want to act on in the screenshot and give the CENTER of it as "point": [y, x],
normalized to 0-{POINT_SCALE} (top-left is [0, 0], bottom-right is [{POINT_SCALE}, {POINT_SCALE}]).
- For "type", point inside the empty input box itself, not at its label.
- For checkboxes and radio buttons, point at the box or circle (or its label text).
- For a custom dropdown that opens a list, "click" it first; on the next step "click" the option.

INSTRUCTIONS:
1. Look at the screenshot carefully, including any dialog or modal in front of the page.
2. Decide the single best NEXT action to progress through the application form.
3. CRITICAL: If you do not see the expected "Next", "Review", or "Submit Application" button on the screen, it is likely off-screen. Use the "scroll_down" action to scroll the page and look for it! Do NOT guess random elements.
4. CRITICAL: If the "Review" or "Submit" button is visible but GREYED OUT (disabled), it means you missed a required field! Look carefully at all empty input fields and fill them out.
5. If you see a CAPTCHA or "verify you are human" challenge, respond with the "captcha" action.
5b. NEVER sign in, log in, enter a password or create an account. The applicant signs in to job boards
    themselves beforehand. If the page asks you to sign in or join before you can apply (a login form,
    "Sign in to apply", "Join now"), respond with the "login_required" action instead.
6. If you see a success/confirmation page (e.g. "Application submitted", "Thank you"), respond with the "done" action.
7. If you see a cookie consent banner or popup blocking the form, dismiss it first.
8. For file upload fields (resume/CV), use the "upload" action.
9. Fill fields in logical order: name, email, phone, then other fields.
10. Do NOT re-fill fields that already have correct values.

Respond with EXACTLY ONE JSON object (no markdown, no explanation):
{{"action": "<action_type>", "point": [y, x], "target": "<short description of what you are pointing at>", "value": "<text>"}}

Valid action types:
- "click": Click at "point". No "value" needed.
- "type": Clear the input at "point" and type "value".
- "select": Open the native dropdown at "point" and choose the option whose text is "value".
- "upload": Click the upload/attach button at "point" and attach the CV. "value" is the CV file path.
- "scroll_down" / "scroll_up": Scroll. Give "point" inside the area to scroll (e.g. a modal), or omit it for the page.
- "captcha": Pause for human to solve CAPTCHA. No point or value needed.
- "login_required": The site wants the applicant to sign in first. Stop. No point or value needed.
- "done": Application submitted successfully. No point or value needed.
- "stuck": Cannot proceed further. No point or value needed.

Respond with ONLY the JSON object."""


def _parse_llm_action(response_text: str) -> dict:
    """Parse the LLM's JSON action response."""
    text = (response_text or "").strip()
    candidates = [text]
    match = re.search(r'\{.*\}', text, re.DOTALL)  # tolerate a markdown fence or stray words around it
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            action = json.loads(candidate)
            if isinstance(action, list) and action:  # some models wrap the object in a list
                action = action[0]
            if isinstance(action, dict):
                return action
        except Exception:
            pass
    return {"action": "stuck", "reason": f"Failed to parse LLM response: {text[:200]}"}


def _to_pixels(page, point) -> tuple:
    """Converts the model's [y, x] point on the 0-1000 grid into viewport pixels."""
    if not (isinstance(point, (list, tuple)) and len(point) == 2):
        raise ValueError(f"expected point [y, x], got {point!r}")
    y, x = float(point[0]), float(point[1])
    viewport = page.viewport_size or {"width": 1280, "height": 900}
    px = min(max(x, 0), POINT_SCALE) / POINT_SCALE * (viewport["width"] - 1)
    py = min(max(y, 0), POINT_SCALE) / POINT_SCALE * (viewport["height"] - 1)
    return px, py


def _mark_screenshot(screenshot_path: str, page, point) -> None:
    """Draws where the agent acted onto the saved screenshot file (never onto the page), for debugging."""
    try:
        from PIL import Image, ImageDraw
        x, y = _to_pixels(page, point)
        img = Image.open(screenshot_path).convert("RGB")
        scale = img.width / (page.viewport_size or {"width": img.width})["width"]
        x, y, r = x * scale, y * scale, 14 * scale
        draw = ImageDraw.Draw(img)
        draw.ellipse([x - r, y - r, x + r, y + r], outline=(255, 0, 0), width=max(2, int(3 * scale)))
        draw.line([x - r * 1.6, y, x + r * 1.6, y], fill=(255, 0, 0), width=max(1, int(2 * scale)))
        draw.line([x, y - r * 1.6, x, y + r * 1.6], fill=(255, 0, 0), width=max(1, int(2 * scale)))
        img.save(screenshot_path)
    except Exception as e:
        print(f"Could not mark screenshot: {e}")


def _execute_action(page, action: dict, cv_filepath: str = "") -> str:
    """Execute one action with real mouse and keyboard input at the model's point. Returns an error or ""."""
    action_type = action.get("action", "")
    value = str(action.get("value") or "")
    point = action.get("point")

    try:
        if action_type in ("click", "type", "select", "upload"):
            x, y = _to_pixels(page, point)

        if action_type == "click":
            page.mouse.click(x, y)
            return ""

        elif action_type == "type":
            page.mouse.click(x, y)
            page.wait_for_timeout(200)
            page.keyboard.press("ControlOrMeta+A")  # clear whatever is already in the field
            page.keyboard.press("Backspace")
            page.keyboard.type(value, delay=15)
            return ""

        elif action_type == "select":
            # Native <select>: open it, type the option's text to jump to it, confirm with Enter.
            page.mouse.click(x, y)
            page.wait_for_timeout(300)
            page.keyboard.type(value, delay=30)
            page.keyboard.press("Enter")
            return ""

        elif action_type == "upload":
            # Always attach the applicant's own CV, whatever path the model wrote.
            filepath = cv_filepath or value
            if not (filepath and os.path.exists(filepath)):
                return f"No CV file to upload (looked for: {filepath or 'nothing'})"
            try:
                with page.expect_file_chooser(timeout=4000) as fc_info:
                    page.mouse.click(x, y)
                fc_info.value.set_files(filepath)
                return ""
            except Exception:
                return "Clicking there did not open a file picker. Point at the upload/attach button itself."

        elif action_type in ("scroll_down", "scroll_up"):
            # Scroll where the model pointed (e.g. inside a modal), or the middle of the page.
            if point:
                x, y = _to_pixels(page, point)
            else:
                viewport = page.viewport_size or {"width": 1280, "height": 900}
                x, y = viewport["width"] / 2, viewport["height"] / 2
            page.mouse.move(x, y)
            page.mouse.wheel(0, 500 if action_type == "scroll_down" else -500)
            return ""

        elif action_type in ["captcha", "done", "stuck", "login_required"]:
            return ""  # These are handled by the main loop

        else:
            return f"Unknown action type: {action_type}"

    except Exception as e:
        return f"Action failed at {point}: {str(e)[:200]}"


def auto_apply_to_job(
    job_url: str,
    user_profile: dict,
    cv_filepath: str = "",
    on_status_update=None,
    on_captcha_detected=None,
    profile_dir: str = PROFILE_DIR,
) -> dict:
    """
    Main entry point: Autonomously applies to a single job using vision-driven browser automation.
    
    Args:
        job_url: The URL of the job application page.
        user_profile: Dict with full_name, email, phone, university, degree, gpa, skills, work_experience.
        cv_filepath: Absolute path to the user's CV/resume PDF file.
        on_status_update: Optional callback(step, action_description) for progress updates.
        on_captcha_detected: Optional callback() that blocks until human solves CAPTCHA.
        profile_dir: Browser profile holding the applicant's own job-board sign-ins (see tools/job_boards.py).

    Returns:
        dict with keys:
            - "success": bool
            - "steps_taken": int
            - "final_status": str ("submitted", "captcha_timeout", "stuck", "login_required", "max_steps_reached", "error")
            - "screenshot_path": str (path to final screenshot)
            - "action_log": list of action descriptions
    """
    from playwright.sync_api import sync_playwright
    
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    os.makedirs(profile_dir, exist_ok=True)
    
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
                user_data_dir=profile_dir,
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
                
                # 1. SCREENSHOT: Capture the page as it is (after letting any navigation settle)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass
                screenshot_path = os.path.join(SCREENSHOT_DIR, f"step_{step}.png")
                screenshot_bytes = page.screenshot(full_page=False)
                with open(screenshot_path, "wb") as f:
                    f.write(screenshot_bytes)
                result["screenshot_path"] = screenshot_path
                
                # 2. REASON: Send the screenshot to Gemini Vision, which points at its target
                error_msg = action_history[-1].split(" | Error: ")[1] if action_history and "| Error:" in action_history[-1] else ""

                prompt = _build_vision_prompt(
                    user_profile=user_profile,
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
                        config=genai.types.GenerateContentConfig(response_mime_type="application/json"),
                    )
                    llm_response = response.text
                except Exception as e:
                    print(f"Vision LLM error: {e}")
                    action_history.append(f"Step {step}: Vision LLM failed - {str(e)[:100]}")
                    continue
                
                # 3. PARSE: Extract action from LLM response
                action = _parse_llm_action(llm_response)
                action_type = action.get("action", "stuck")

                # The history the model reads back says what it aimed at, not just where.
                action_desc = f"Step {step}: {action_type}"
                if action.get("target"):
                    action_desc += f" on \"{str(action['target'])[:60]}\""
                if action.get("point"):
                    action_desc += f" at {action['point']}"
                if action.get("value"):
                    safe_val = str(action['value'])[:50].encode('ascii', 'ignore').decode('ascii')
                    action_desc += f" value=\"{safe_val}\""

                if on_status_update:
                    on_status_update(step, action_desc)

                # HANDLE SPECIAL ACTIONS
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
                
                if action_type == "login_required":
                    result["final_status"] = "login_required"
                    action_history.append(f"Step {step}: LOGIN REQUIRED - stopped; the applicant must sign in first")
                    result["action_log"] = action_history
                    break

                if action_type == "stuck":
                    result["final_status"] = "stuck"
                    action_history.append(f"Step {step}: STUCK - Agent cannot proceed")
                    result["action_log"] = action_history
                    break
                
                # 4. ACT: Real mouse/keyboard input at the model's point; mark it on the saved screenshot
                if action.get("point"):
                    _mark_screenshot(screenshot_path, page, action["point"])
                error = _execute_action(page, action, cv_filepath)
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
    user_key: str = "anonymous",
) -> list:
    """
    Apply to multiple jobs sequentially, in the user's own browser profile.

    Args:
        jobs: List of job dicts, each with at least "title", "company", "link".
        user_profile: User profile dict.
        cv_filepath: Path to CV file.
        on_job_status_update: Optional callback(job_index, job_title, status_message).
        user_key: The applicant's id ("user_3"); selects their browser profile and sign-ins.

    Returns:
        List of result dicts, one per job.
    """
    from tools import job_boards

    lock = job_boards.profile_lock(user_key)
    with lock:  # never share the profile with an open sign-in window
        return _apply_each(jobs, user_profile, cv_filepath, on_job_status_update, user_key)


def _apply_each(jobs, user_profile, cv_filepath, on_job_status_update, user_key):
    from tools import job_boards

    results = []
    signed_in = job_boards.load_state(user_key)

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

        # Only apply on boards the applicant has signed in to themselves; never log in for them.
        board = job_boards.board_for_url(url)
        if board and not signed_in.get(board, {}).get("signed_in"):
            results.append({
                "job": job,
                "success": False,
                "final_status": "login_required",
                "steps_taken": 0,
                "action_log": [f"Not signed in to {job_boards.BOARDS[board]['name']}; skipped"],
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
            profile_dir=job_boards.profile_dir(user_key),
        )
        result["job"] = job
        results.append(result)

        # The board's session has expired: ask the user to sign in again next time.
        if board and result["final_status"] == "login_required":
            job_boards.set_signed_in(user_key, board, False)
            signed_in = job_boards.load_state(user_key)
        
        if on_job_status_update:
            status = "Success" if result["success"] else result["final_status"]
            on_job_status_update(i, title, f"Finished: {status}")
    
    return results
