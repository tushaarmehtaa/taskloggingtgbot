from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class Task(Base):
    __tablename__ = 'tasks'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    due_date = Column(DateTime)
    priority = Column(String(20), default='medium')  # low, medium, high, urgent
    status = Column(String(20), default='pending')  # pending, in_progress, completed
    estimated_duration = Column(Float)  # in hours
    reminder_at = Column(DateTime, nullable=True)  # Time for the reminder
    reminder_sent = Column(Boolean, default=False)  # To track if the reminder was sent
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}', priority='{self.priority}')>"

class Conversation(Base):
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    message = Column(Text, nullable=False)
    response = Column(Text)
    message_type = Column(String(20), default='text')  # text, voice, command
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id})>"

class UserProfile(Base):
    __tablename__ = 'user_profiles'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    timezone = Column(String(50), default='UTC')
    preferences = Column(Text)  # JSON string for user preferences
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<UserProfile(user_id={self.user_id}, username='{self.username}')>"

# Database setup
DATABASE_URL = "sqlite:///ai_assistant.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
