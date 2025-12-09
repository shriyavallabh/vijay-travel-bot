"""
API Router for Admin Panel
Provides REST endpoints for user management and chat functionality
"""
import os
import httpx
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pydantic import BaseModel

from database import get_db, User, Message, SenderType, get_or_create_user, save_message

router = APIRouter(prefix="/api", tags=["admin"])

# WhatsApp API Configuration
WHATSAPP_API_URL = "https://graph.facebook.com/v18.0"
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")


# ============== Pydantic Models ==============

class UserCreate(BaseModel):
    phone: str
    name: Optional[str] = None
    email: Optional[str] = None
    trip_id: Optional[str] = None
    notes: Optional[str] = None


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    trip_id: Optional[str] = None
    trip_status: Optional[str] = None
    bot_paused: Optional[bool] = None
    notes: Optional[str] = None


class MessageCreate(BaseModel):
    user_id: int
    content: str


class AdminMessageSend(BaseModel):
    user_id: int
    content: str
    send_whatsapp: bool = True


class PaginatedResponse(BaseModel):
    data: List[dict]
    total: int
    page: int
    per_page: int
    total_pages: int


# ============== Dashboard Endpoints ==============

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Get dashboard KPI statistics"""
    total_users = db.query(User).count()

    # Active trips (users with trip_status = 'active')
    active_trips = db.query(User).filter(User.trip_status == "active").count()

    # Pending queries (unread messages from users)
    pending_queries = db.query(Message).filter(
        Message.sender_type == SenderType.USER.value,
        Message.is_read == False
    ).count()

    # Bot paused users
    bot_paused_count = db.query(User).filter(User.bot_paused == True).count()

    # Messages today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    messages_today = db.query(Message).filter(Message.timestamp >= today_start).count()

    # Recent activity (last 7 days message count by day)
    from sqlalchemy import cast, Date
    recent_messages = db.query(
        func.date(Message.timestamp).label('date'),
        func.count(Message.id).label('count')
    ).filter(
        Message.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).group_by(func.date(Message.timestamp)).all()

    return {
        "total_users": total_users,
        "active_trips": active_trips,
        "pending_queries": pending_queries,
        "bot_paused_count": bot_paused_count,
        "messages_today": messages_today,
        "recent_activity": [{"date": str(r.date), "count": r.count} for r in recent_messages]
    }


# ============== User Endpoints ==============

@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    sort_by: str = Query("last_message_at", regex="^(id|name|phone|created_at|last_message_at|trip_status)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    search: Optional[str] = None,
    trip_status: Optional[str] = None,
    bot_paused: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List users with pagination, sorting, and filtering"""
    query = db.query(User)

    # Apply filters
    if search:
        query = query.filter(
            (User.name.ilike(f"%{search}%")) |
            (User.phone.ilike(f"%{search}%"))
        )

    if trip_status:
        query = query.filter(User.trip_status == trip_status)

    if bot_paused is not None:
        query = query.filter(User.bot_paused == bot_paused)

    # Get total count
    total = query.count()

    # Apply sorting
    sort_column = getattr(User, sort_by, User.last_message_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    # Apply pagination
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()

    return {
        "data": [u.to_dict() for u in users],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


@router.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a single user by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict()


@router.post("/users")
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    # Check if phone already exists
    existing = db.query(User).filter(User.phone == user_data.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this phone already exists")

    user = User(**user_data.dict())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.to_dict()


@router.patch("/users/{user_id}")
def update_user(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)):
    """Update user details"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user.to_dict()


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


@router.post("/users/{user_id}/toggle-bot")
def toggle_bot_status(user_id: int, db: Session = Depends(get_db)):
    """Toggle bot_paused status for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.bot_paused = not user.bot_paused
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "bot_paused": user.bot_paused,
        "message": f"Bot {'paused' if user.bot_paused else 'resumed'} for user {user.name or user.phone}"
    }


# ============== Message Endpoints ==============

@router.get("/users/{user_id}/messages")
def get_user_messages(
    user_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get chat history for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = db.query(Message).filter(Message.user_id == user_id)
    total = query.count()

    # Get messages ordered by timestamp (newest last for chat display)
    offset = (page - 1) * per_page
    messages = query.order_by(Message.timestamp.asc()).offset(offset).limit(per_page).all()

    return {
        "user": user.to_dict(),
        "messages": [m.to_dict() for m in messages],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


@router.post("/users/{user_id}/messages/mark-read")
def mark_messages_read(user_id: int, db: Session = Depends(get_db)):
    """Mark all messages from a user as read"""
    db.query(Message).filter(
        Message.user_id == user_id,
        Message.sender_type == SenderType.USER.value
    ).update({"is_read": True})
    db.commit()
    return {"message": "Messages marked as read"}


@router.post("/messages/send")
async def send_admin_message(message_data: AdminMessageSend, db: Session = Depends(get_db)):
    """
    Admin sends a message to a user
    - Saves to database
    - Optionally sends via WhatsApp API
    """
    user = db.query(User).filter(User.id == message_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Save message to database
    message = save_message(
        db=db,
        user_id=user.id,
        content=message_data.content,
        sender_type=SenderType.ADMIN.value
    )

    whatsapp_response = None

    # Send via WhatsApp if requested
    if message_data.send_whatsapp and WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN:
        try:
            whatsapp_response = await send_whatsapp_message(user.phone, message_data.content)
            if whatsapp_response.get("messages"):
                message.whatsapp_message_id = whatsapp_response["messages"][0].get("id")
                db.commit()
        except Exception as e:
            print(f"[WhatsApp Error] Failed to send message: {e}")
            whatsapp_response = {"error": str(e)}

    return {
        "message": message.to_dict(),
        "whatsapp_response": whatsapp_response
    }


async def send_whatsapp_message(phone: str, text: str) -> dict:
    """Send a message via WhatsApp Business API"""
    # Clean phone number (remove + and spaces)
    clean_phone = phone.replace("+", "").replace(" ", "").replace("-", "")

    url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "text",
        "text": {"body": text}
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


# ============== Conversation Endpoints ==============

@router.get("/conversations")
def list_conversations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """List all conversations with latest message preview"""
    # Subquery to get the latest message for each user
    from sqlalchemy import and_

    query = db.query(User).filter(User.last_message_at.isnot(None))

    if unread_only:
        # Get users with unread messages
        users_with_unread = db.query(Message.user_id).filter(
            Message.sender_type == SenderType.USER.value,
            Message.is_read == False
        ).distinct().subquery()
        query = query.filter(User.id.in_(users_with_unread))

    total = query.count()

    # Order by last message time
    users = query.order_by(desc(User.last_message_at)).offset((page - 1) * per_page).limit(per_page).all()

    conversations = []
    for user in users:
        # Get latest message
        latest_msg = db.query(Message).filter(
            Message.user_id == user.id
        ).order_by(desc(Message.timestamp)).first()

        # Count unread
        unread_count = db.query(Message).filter(
            Message.user_id == user.id,
            Message.sender_type == SenderType.USER.value,
            Message.is_read == False
        ).count()

        conversations.append({
            "user": user.to_dict(),
            "latest_message": latest_msg.to_dict() if latest_msg else None,
            "unread_count": unread_count
        })

    return {
        "data": conversations,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page
    }


# ============== Sync Endpoints ==============

@router.post("/sync/customers")
def sync_customers_from_kg(db: Session = Depends(get_db)):
    """
    Sync customers from Knowledge Graph to database
    Run this to populate initial users
    """
    try:
        from knowledge_graph import TravelKnowledgeGraph
        from ingest import create_knowledge_graph

        kg = create_knowledge_graph("data")
        customers = kg.get_all_customers()

        synced = 0
        for customer_name in customers:
            customer_data = kg.find_customer(customer_name)
            if customer_data:
                phone = customer_data.get("phone", "")
                if phone:
                    existing = db.query(User).filter(User.phone == phone).first()
                    if not existing:
                        user = User(
                            phone=phone,
                            name=customer_data.get("name"),
                            email=customer_data.get("email"),
                            trip_id=customer_data.get("booking", {}).get("booking_id"),
                            trip_status=customer_data.get("trip_progress", {}).get("status", "upcoming")
                        )
                        db.add(user)
                        synced += 1

        db.commit()
        return {"message": f"Synced {synced} new customers", "total_in_db": db.query(User).count()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
