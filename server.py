import os
import traceback
from typing import Dict, Any
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

class ResumeSessionRequest(BaseModel):
    session_id: str
    feedback: str = "approve"


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
        raise HTTPException(status_code=500, detail=str(e))


# 2. Update start route to inject user_id into the LangGraph state
@app.post("/api/job-finder/start")
async def start_job_search(
    req: SearchRequest,
    current_user: models.User = Depends(get_current_user)
):
    """Protected: Only logged-in users can trigger the AI agents."""
    try:
        config = {"configurable": {"thread_id": req.session_id}}
        
        # Securely inject the verified user ID into the LangGraph state
        user_id_str = f"user_{current_user.id}"
        
        initial_state = {
            "user_id": user_id_str,  
            "messages": [("user", req.query)],
            "user_profile": {},  # Leave empty! Matching Agent uses Vector DB dynamically
            "raw_jobs": [],
            "scored_jobs": [],
            "tailored_assets": {},
        }

        # Run until the first interrupt (Stage 4 HITL)
        for event in langgraph_app.stream(initial_state, config, stream_mode="values"):
            pass

        # Check graph state to see if it hit the interrupt
        state_snapshot = langgraph_app.get_state(config)
        
        if state_snapshot.next:
            values = state_snapshot.values
            assets = values.get("tailored_assets", {}).get("top_job_assets", "No assets generated.")
            
            return {
                "status": "paused_for_review",
                "next_node": state_snapshot.next,
                "tailored_assets": assets
            }
        
        return {"status": "completed", "values": state_snapshot.values}

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("SERVER ERROR:\n", error_detail)
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
        
        # 3. Save the application to the database securely!
        new_app = models.Application(
            user_id=current_user.id,
            status="Approved",
            assets_preview=assets_str[:500] + "..." if len(assets_str) > 500 else assets_str
        )
        
        db.add(new_app)
        db.commit()
        
        return {"status": "completed", "message": "Application logged successfully!"}

    except Exception as e:
        db.rollback()  # Protect the database if something crashes
        import traceback
        print("RESUME ERROR:\n", traceback.format_exc())
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
        "cv_filename": db_user.cv_filename  
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

@app.get("/api/applications")
async def get_user_applications(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetch all logged job applications for the authenticated user."""
    try:
        apps = db.query(models.Application).filter(models.Application.user_id == current_user.id).all()
        
        # Serialize the database objects into a clean list of dictionaries
        results = []
        for app in apps:
            results.append({
                "id": app.id,
                "timestamp": app.timestamp.strftime("%Y-%m-%d %H:%M:%S") if app.timestamp else "",
                "status": app.status,
                "assets_preview": app.assets_preview
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))