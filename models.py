from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # NEW: Store the actual filename instead of a True/False flag
    cv_filename = Column(String, nullable=True) 
    cv_filepath = Column(String, nullable=True)

    full_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    university = Column(String, nullable=True)
    degree = Column(String, nullable=True)
    gpa = Column(Float, nullable=True)
    graduation_year = Column(Integer, nullable=True)
    skills = Column(Text, nullable=True)
    work_experience = Column(Text, nullable=True)
    linkedin_url = Column(String, nullable=True)
    github_url = Column(String, nullable=True)
    preferred_job_titles = Column(Text, nullable=True)
    preferred_locations = Column(Text, nullable=True)
    profile_completed = Column(Boolean, default=False)

    applications = relationship("Application", back_populates="owner")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    job_title = Column(String, nullable=True)
    company = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    status = Column(String, default="Applied")
    assets_preview = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    owner = relationship("User", back_populates="applications")

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    owner = relationship("User")