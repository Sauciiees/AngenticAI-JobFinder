from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey , Boolean
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

    applications = relationship("Application", back_populates="owner")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="Approved & Applied")
    assets_preview = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Back-reference to the User model
    owner = relationship("User", back_populates="applications")