import os
import traceback
from typing import Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from pydantic import BaseModel
from dotenv import load_dotenv
from langgraph.types import Command
import models
from fastapi import Depends
from sqlalchemy.orm import Session
from database import engine, get_db
from fastapi import HTTPException, Depends, status
from sqlalchemy.orm import Session
from auth import get_password_hash, verify_password, create_access_token,get_current_user
import models
from database import get_db
from fastapi.staticfiles import StaticFiles
import shutil
from fastapi.responses import FileResponse
import json


load_dotenv()
models.Base.metadata.create_all(bind=engine)

from agent.graph import app as langgraph_app
from agent.parser import parse_and_store_document
from agent.vector_store import vector_store

app = FastAPI(title="Agentic AI Job Finder API", version="1.0")

# 1. Define base uploads directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 2. Mount static files so files can be accessed via URL (e.g. http://localhost:8000/uploads/...)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/")
async def root():
    """Simple health check endpoint."""
    return {"message": "🤖 Agentic AI Job Finder API is online and running!"}

# Updated Pydantic Models to require user_id
class SearchRequest(BaseModel):
    session_id: str
    query: str = "ช่วยหาตำแหน่ง Data Scientist หรือ AI Engineer ในไทยจาก LinkedIn ให้หน่อยครับ"
    time_filter: str = "qdr:w"  # Default: past week. Options: qdr:d (24h), qdr:w (week), qdr:m (month)

class JobSelectionRequest(BaseModel):
    session_id: str
    selected_indices: list  # List of integer indices the user selected

class ResumeSessionRequest(BaseModel):
    session_id: str
    feedback: str = "approve"
    job_title: Optional[str] = None
    company: Optional[str] = None
    jobs: Optional[list] = None

class StatusUpdateRequest(BaseModel):
    status: str

class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    university: Optional[str] = None
    degree: Optional[str] = None
    gpa: Optional[float] = None
    graduation_year: Optional[int] = None
    skills: Optional[str] = None
    work_experience: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    preferred_job_titles: Optional[str] = None
    preferred_locations: Optional[str] = None

class ChatSessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: str

class NewSessionRequest(BaseModel):
    title: str = "New Chat"


# 1. Update upload route to accept user_id and pass it to the parser
# Add db: Session = Depends(get_db) to the parameters
@app.post("/api/upload-resume")
async def upload_resume(
    session_id: str, 
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Create a user-specific folder: uploads/user_1/
        user_folder = os.path.join(UPLOAD_DIR, f"user_{current_user.id}")
        os.makedirs(user_folder, exist_ok=True)
        
        destination_path = os.path.join(user_folder, file.filename)
        
        # Save file directly to server disk
        with open(destination_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Update user record in database
        current_user.cv_filename = file.filename
        current_user.cv_filepath = destination_path
        db.commit()

        # Vectorize document into ChromaDB using saved path
        user_id_str = f"user_{current_user.id}"
        parse_and_store_document(destination_path, user_id=user_id_str, doc_type="resume")
        
        return {
            "status": "success", 
            "message": f"Successfully stored {file.filename}",
            "filepath": destination_path
        }
        
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# 2. Update start route to inject user_id into the LangGraph state
@app.post("/api/job-finder/start")
async def start_job_search(
    req: SearchRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Protected: Only logged-in users can trigger the AI agents."""
    try:
        # Auto-rename if this is a New Chat
        session = db.query(models.ChatSession).filter(models.ChatSession.session_id == req.session_id).first()
        if session and session.title == "New Chat":
            from agent.nodes import llm
            from langchain_core.messages import HumanMessage
            try:
                # Ask LLM for a very short title
                prompt = f"Generate a short title (max 4 words) for this chat based on the user's first message. Message: '{req.query}'. Output ONLY the title, nothing else."
                title_res = llm.invoke([HumanMessage(content=prompt)])
                new_title = title_res.content.strip().replace('"', '')
                session.title = new_title
                db.commit()
            except Exception as e:
                # Fallback to truncating
                session.title = req.query[:30] + ("..." if len(req.query) > 30 else "")
                db.commit()

        config = {"configurable": {"thread_id": req.session_id}}
        
        # Securely inject the verified user ID into the LangGraph state
        user_id_str = f"user_{current_user.id}"
        
        structured_profile = {
            "full_name": current_user.full_name,
            "email": current_user.email,
            "university": current_user.university,
            "degree": current_user.degree,
            "gpa": current_user.gpa,
            "graduation_year": current_user.graduation_year,
            "skills": current_user.skills,
            "work_experience": current_user.work_experience,
            "preferred_job_titles": current_user.preferred_job_titles,
            "preferred_locations": current_user.preferred_locations
        }

        initial_state = {
            "user_id": user_id_str,  
            "messages": [("user", req.query)],
            "user_profile": {},
            "structured_profile": structured_profile,
            "raw_jobs": [],
            "scored_jobs": [],
            "tailored_assets": {},
            "route_intent": "",
            "chat_response": "",
            "time_filter": req.time_filter,
            "selected_jobs": [],
        }

        # Run until the first interrupt
        for event in langgraph_app.stream(initial_state, config, stream_mode="values"):
            pass

        # Check graph state
        state_snapshot = langgraph_app.get_state(config)
        values = state_snapshot.values
        
        # If the router decided this was a chat, return the chat response
        if values.get("route_intent") == "chat":
            return {
                "status": "chat_response",
                "chat_response": values.get("chat_response", ""),
            }

        # If paused at job_selection_node — return all jobs for the card UI
        if state_snapshot.next and "job_selection_node" in state_snapshot.next:
            return {
                "status": "paused_for_selection",
                "raw_jobs": values.get("raw_jobs", []),
            }
        
        # If paused at human_approval_node — return assets for review
        if state_snapshot.next and "human_approval_node" in state_snapshot.next:
            raw_assets = values.get("tailored_assets", {}).get("top_job_assets", "No assets generated.")
            
            if isinstance(raw_assets, list):
                if len(raw_assets) > 0 and isinstance(raw_assets[0], dict) and "text" in raw_assets[0]:
                    assets = raw_assets[0]["text"]
                else:
                    assets = json.dumps(raw_assets)
            elif isinstance(raw_assets, dict):
                assets = raw_assets.get("text", json.dumps(raw_assets))
            else:
                assets = str(raw_assets)
            
            scored_jobs = values.get("scored_jobs", [])
            
            return {
                "status": "paused_for_review",
                "next_node": state_snapshot.next,
                "tailored_assets": assets,
                "scored_jobs": scored_jobs
            }
        
        return {"status": "completed", "values": state_snapshot.values}

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("SERVER ERROR:\n", error_detail)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/job-finder/select-jobs")
async def select_jobs(
    req: JobSelectionRequest,
    current_user: models.User = Depends(get_current_user)
):
    """Resumes the pipeline after user selects jobs from the card UI."""
    try:
        config = {"configurable": {"thread_id": req.session_id}}
        
        # Resume with the selected job indices
        for event in langgraph_app.stream(
            Command(resume=req.selected_indices), config, stream_mode="values"
        ):
            pass

        # Check if we hit the next interrupt (human_approval_node)
        state_snapshot = langgraph_app.get_state(config)
        values = state_snapshot.values
        
        if state_snapshot.next and "human_approval_node" in state_snapshot.next:
            raw_assets = values.get("tailored_assets", {}).get("top_job_assets", "No assets generated.")
            
            if isinstance(raw_assets, list):
                if len(raw_assets) > 0 and isinstance(raw_assets[0], dict) and "text" in raw_assets[0]:
                    assets = raw_assets[0]["text"]
                else:
                    assets = json.dumps(raw_assets)
            elif isinstance(raw_assets, dict):
                assets = raw_assets.get("text", json.dumps(raw_assets))
            else:
                assets = str(raw_assets)
            
            scored_jobs = values.get("scored_jobs", [])
            
            return {
                "status": "paused_for_review",
                "next_node": state_snapshot.next,
                "tailored_assets": assets,
                "scored_jobs": scored_jobs
            }
        
        return {"status": "completed", "values": state_snapshot.values}

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc().encode('ascii', 'ignore').decode('ascii')
        print("SELECT-JOBS ERROR:\n", error_detail)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/job-finder/resume")
async def resume_job_search(
    req: ResumeSessionRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)  # <-- INJECT DATABASE SESSION
):
    """Resumes the paused LangGraph agent and SAVES the result to SQLite."""
    try:
        config = {"configurable": {"thread_id": req.session_id}}
        
        # 1. Resume the agent with the user's approval
        for event in langgraph_app.stream(Command(resume=req.feedback), config, stream_mode="values"):
            pass
            
        # 2. Get the final assets the AI generated
        final_state = langgraph_app.get_state(config).values
        raw_assets = final_state.get("tailored_assets", {}).get("top_job_assets", "Assets generated but empty.")
        
        # Safely convert to a string if the LLM returned a list or dictionary
        if isinstance(raw_assets, list):
            # Try to extract the text block if it's Anthropic format, otherwise dump to JSON string
            if len(raw_assets) > 0 and isinstance(raw_assets[0], dict) and "text" in raw_assets[0]:
                assets_str = raw_assets[0]["text"]
            else:
                assets_str = json.dumps(raw_assets)
        elif isinstance(raw_assets, dict):
            assets_str = json.dumps(raw_assets)
        else:
            assets_str = str(raw_assets)
            
        assets_preview = assets_str[:500] + "..." if len(assets_str) > 500 else assets_str
        
        if req.jobs:
            for j in req.jobs:
                new_app = models.Application(
                    user_id=current_user.id,
                    job_title=j.get("title", "Unknown"),
                    company=j.get("company", "Unknown"),
                    logo_url=j.get("logo_url", ""),
                    status="Applied",
                    assets_preview=assets_preview
                )
                db.add(new_app)
        else:
            new_app = models.Application(
                user_id=current_user.id,
                job_title=req.job_title,
                company=req.company,
                logo_url="",
                status="Applied",
                assets_preview=assets_preview
            )
            db.add(new_app)
            
        db.commit()
        
        return {"status": "completed", "message": "Applications logged successfully!"}

    except Exception as e:
        db.rollback()
        import traceback
        err_msg = traceback.format_exc().encode('ascii', 'ignore').decode('ascii')
        print("RESUME ERROR:\n", err_msg)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/applications/{user_id}")
async def get_user_applications(user_id: int, db: Session = Depends(get_db)):
    """Fetch applications for a specific user directly from SQLite."""
    user_apps = db.query(models.Application).filter(models.Application.user_id == user_id).all()
    return user_apps

# Pydantic model for incoming auth requests
class UserAuthRequest(BaseModel):
    username: str
    password: str

@app.post("/api/signup")
async def signup(user: UserAuthRequest, db: Session = Depends(get_db)):
    """Registers a new user in the database with a hashed password."""
    
    # 1. Check if the username already exists
    existing_user = db.query(models.User).filter(models.User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # 2. Hash the password and save the user
    hashed_password = get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return {"message": "User created successfully. You can now log in."}


@app.post("/api/login")
async def login(user: UserAuthRequest, db: Session = Depends(get_db)):
    """Authenticates a user and returns a JWT access token."""
    
    # 1. Find the user in the database
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    
    # 2. Verify the user exists and the password matches
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    # 3. Generate the JWT (embedding the user's database ID)
    access_token = create_access_token(data={"sub": str(db_user.id)})
    
    # Look at the bottom of your login function and update the return dictionary:
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": db_user.id,
        "username": db_user.username,
        "cv_filename": db_user.cv_filename,
        "full_name": db_user.full_name,
        "email": db_user.email,
        "phone": db_user.phone,
        "university": db_user.university,
        "degree": db_user.degree,
        "gpa": db_user.gpa,
        "graduation_year": db_user.graduation_year,
        "skills": db_user.skills,
        "work_experience": db_user.work_experience,
        "linkedin_url": db_user.linkedin_url,
        "github_url": db_user.github_url,
        "preferred_job_titles": db_user.preferred_job_titles,
        "preferred_locations": db_user.preferred_locations,
        "profile_completed": db_user.profile_completed
    }

@app.get("/api/user/cv")
async def get_user_cv(current_user: models.User = Depends(get_current_user)):
    """Returns the user's stored CV file directly."""
    if not current_user.cv_filepath or not os.path.exists(current_user.cv_filepath):
        raise HTTPException(status_code=404, detail="No CV found for this user.")
        
    return FileResponse(
        path=current_user.cv_filepath, 
        filename=current_user.cv_filename,
        media_type="application/pdf"
    )

@app.delete("/api/applications/{app_id}")
async def delete_application(
    app_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a logged job application."""
    app = db.query(models.Application).filter(
        models.Application.id == app_id,
        models.Application.user_id == current_user.id
    ).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
        
    db.delete(app)
    db.commit()
    return {"message": "Application deleted successfully"}

@app.get("/api/applications")
async def get_user_applications(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch all logged job applications for the authenticated user."""
    try:
        apps = db.query(models.Application).filter(
            models.Application.user_id == current_user.id
        ).order_by(models.Application.timestamp.desc()).all()
        
        results = []
        for app in apps:
            results.append({
                "id": app.id,
                "job_title": app.job_title or "Untitled Position",
                "company": app.company or "Unknown Company",
                "logo_url": getattr(app, "logo_url", ""),
                "timestamp": app.timestamp.strftime("%Y-%m-%d %H:%M:%S") if app.timestamp else "",
                "status": app.status,
                "assets_preview": app.assets_preview
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/applications/{app_id}/status")
async def update_application_status(
    app_id: int,
    req: StatusUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the status of an application."""
    app = db.query(models.Application).filter(
        models.Application.id == app_id,
        models.Application.user_id == current_user.id
    ).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    app.status = req.status
    db.commit()
    return {"status": "success", "message": f"Status updated to '{req.status}'"}

@app.get("/api/profile")
async def get_profile(current_user: models.User = Depends(get_current_user)):
    return {
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "university": current_user.university,
        "degree": current_user.degree,
        "gpa": current_user.gpa,
        "graduation_year": current_user.graduation_year,
        "skills": current_user.skills,
        "work_experience": current_user.work_experience,
        "linkedin_url": current_user.linkedin_url,
        "github_url": current_user.github_url,
        "preferred_job_titles": current_user.preferred_job_titles,
        "preferred_locations": current_user.preferred_locations,
        "profile_completed": current_user.profile_completed,
        "cv_filename": current_user.cv_filename,
    }

@app.put("/api/profile")
async def update_profile(
    req: ProfileUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    current_user.full_name = req.full_name
    current_user.email = req.email
    current_user.phone = req.phone
    current_user.university = req.university
    current_user.degree = req.degree
    current_user.gpa = req.gpa
    current_user.graduation_year = req.graduation_year
    current_user.skills = req.skills
    current_user.work_experience = req.work_experience
    current_user.linkedin_url = req.linkedin_url
    current_user.github_url = req.github_url
    current_user.preferred_job_titles = req.preferred_job_titles
    current_user.preferred_locations = req.preferred_locations
    
    has_full_name = bool(current_user.full_name)
    has_other = bool(current_user.university or current_user.skills or current_user.cv_filename)
    current_user.profile_completed = has_full_name and has_other
    
    db.commit()
    return {"status": "success", "message": "Profile updated"}

@app.delete("/api/profile/cv")
async def delete_cv(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.cv_filepath and os.path.exists(current_user.cv_filepath):
        try:
            os.remove(current_user.cv_filepath)
        except OSError:
            pass
    
    current_user.cv_filename = None
    current_user.cv_filepath = None
    db.commit()

    user_id_str = f"user_{current_user.id}"
    results = vector_store.collection.get(where={"user_id": user_id_str})
    if results and results.get('ids'):
        vector_store.collection.delete(ids=results['ids'])

    return {"status": "success", "message": "CV deleted"}

import uuid

@app.get("/api/chat-sessions", response_model=list[ChatSessionResponse])
def get_sessions(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(models.ChatSession).filter(models.ChatSession.user_id == current_user.id).order_by(models.ChatSession.created_at.desc()).all()
    return [{"session_id": s.session_id, "title": s.title, "created_at": str(s.created_at)} for s in sessions]

@app.post("/api/chat-sessions")
def create_session(req: NewSessionRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    session_id = str(uuid.uuid4())
    new_session = models.ChatSession(user_id=current_user.id, session_id=session_id, title=req.title)
    db.add(new_session)
    db.commit()
    return {"session_id": session_id, "title": req.title}

@app.put("/api/chat-sessions/{session_id}")
def rename_session(session_id: str, req: NewSessionRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(models.ChatSession).filter(models.ChatSession.session_id == session_id, models.ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.title = req.title
    db.commit()
    return {"status": "success"}

@app.delete("/api/chat-sessions/{session_id}")
def delete_session(session_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(models.ChatSession).filter(models.ChatSession.session_id == session_id, models.ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"status": "success"}

@app.get("/api/chat-sessions/{session_id}/history")
def get_session_history(session_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # verify ownership
    session = db.query(models.ChatSession).filter(models.ChatSession.session_id == session_id, models.ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    config = {"configurable": {"thread_id": session_id}}
    state_snapshot = langgraph_app.get_state(config)
    values = state_snapshot.values if state_snapshot else {}
    messages = values.get("messages", [])
    
    # Format messages for frontend
    history = []
    for msg in messages:
        # Check type
        msg_type = getattr(msg, "type", "")
        if msg_type in ["human", "ai"]:
            # If there are tool calls in AIMessage, skip returning tool_calls in content? 
            # We just return the text content.
            if msg.content:
                text_content = ""
                if isinstance(msg.content, list):
                    for item in msg.content:
                        if isinstance(item, dict) and "text" in item:
                            text_content += item["text"] + "\n"
                        elif isinstance(item, str):
                            text_content += item + "\n"
                else:
                    text_content = str(msg.content)
                if text_content.strip():
                    history.append({"role": "user" if msg_type == "human" else "assistant", "content": text_content.strip()})
        elif isinstance(msg, tuple):
             if len(msg) >= 2 and msg[0] in ["human", "ai", "user", "assistant"]:
                 # Map user->human, assistant->ai if needed
                 role = "user" if msg[0] in ["human", "user"] else "assistant"
                 if msg[1]:
                     history.append({"role": role, "content": str(msg[1])})
             
    # Return current pipeline status if paused
    status = "idle"
    if state_snapshot and state_snapshot.next:
        if "job_selection_node" in state_snapshot.next:
            status = "paused_for_selection"
        elif "human_approval_node" in state_snapshot.next:
            status = "paused_for_review"
            
    # Format raw assets
    raw_assets = values.get("tailored_assets", {}).get("top_job_assets", "No assets generated.")
    if isinstance(raw_assets, list):
        if len(raw_assets) > 0 and isinstance(raw_assets[0], dict) and "text" in raw_assets[0]:
            assets = raw_assets[0]["text"]
        else:
            assets = json.dumps(raw_assets)
    elif isinstance(raw_assets, dict):
        assets = raw_assets.get("text", json.dumps(raw_assets))
    else:
        assets = str(raw_assets)
            
    return {
        "history": history,
        "status": status,
        "raw_jobs": values.get("raw_jobs", []),
        "scored_jobs": values.get("scored_jobs", []),
        "tailored_assets": assets
    }