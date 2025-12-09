"""
Database Models and Configuration for Admin Panel
Uses SQLAlchemy with SQLite (local) or PostgreSQL (production)
"""
import os
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from enum import Enum

# Database URL - Use PostgreSQL in production, SQLite locally
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./shri_travels.db")

# Handle Railway's postgres:// vs postgresql:// URL format
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class SenderType(str, Enum):
    """Message sender types"""
    USER = "user"
    BOT = "bot"
    ADMIN = "admin"


class TripStatus(str, Enum):
    """Trip status types"""
    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class User(Base):
    """
    User model - represents WhatsApp users/customers
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    trip_id = Column(String(50), nullable=True)
    trip_status = Column(String(20), default=TripStatus.UPCOMING.value)
    bot_paused = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)

    # Relationship to messages
    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "name": self.name,
            "email": self.email,
            "trip_id": self.trip_id,
            "trip_status": self.trip_status,
            "bot_paused": self.bot_paused,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "message_count": len(self.messages) if self.messages else 0
        }


class Message(Base):
    """
    Message model - stores all chat messages
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    sender_type = Column(String(10), nullable=False)  # user, bot, admin
    whatsapp_message_id = Column(String(100), nullable=True)
    is_read = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationship to user
    user = relationship("User", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "content": self.content,
            "sender_type": self.sender_type,
            "whatsapp_message_id": self.whatsapp_message_id,
            "is_read": self.is_read,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class AdminUser(Base):
    """
    Admin user model for authentication
    """
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=True)
    role = Column(String(20), default="admin")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Create all tables
def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    print("[Database] Tables created successfully")


# Utility functions
def get_or_create_user(db, phone: str, name: Optional[str] = None) -> User:
    """Get existing user or create new one"""
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(phone=phone, name=name)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def save_message(db, user_id: int, content: str, sender_type: str, whatsapp_msg_id: Optional[str] = None) -> Message:
    """Save a message to database"""
    message = Message(
        user_id=user_id,
        content=content,
        sender_type=sender_type,
        whatsapp_message_id=whatsapp_msg_id
    )
    db.add(message)

    # Update user's last_message_at
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.last_message_at = datetime.utcnow()

    db.commit()
    db.refresh(message)
    return message


if __name__ == "__main__":
    # Initialize database when run directly
    init_db()
    print("Database initialized!")
