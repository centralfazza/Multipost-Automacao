from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Conversation, Message

router = APIRouter()

@router.get("/")
def list_convs(company_id: str, db: Session = Depends(get_db)):
    return db.query(Conversation).filter(Conversation.company_id == company_id).all()

@router.get("/{id}/messages")
def get_msgs(id: int, db: Session = Depends(get_db)):
    return db.query(Message).filter(Message.conversation_id == id).all()

@router.post("/send")
def send(data: dict):
    return {"status": "sent"}
