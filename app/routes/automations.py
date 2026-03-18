from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Automation
from pydantic import BaseModel

router = APIRouter()

class AutomationCreate(BaseModel):
    company_id: str
    name: str
    platform: str = "instagram"
    triggers: dict
    actions: list
    is_active: bool = True

@router.post("/")
def create(auto: AutomationCreate, db: Session = Depends(get_db)):
    db_auto = Automation(**auto.dict())
    db.add(db_auto)
    db.commit()
    return db_auto

@router.get("/")
def list_all(company_id: str = None, db: Session = Depends(get_db)):
    q = db.query(Automation)
    if company_id: q = q.filter(Automation.company_id == company_id)
    return q.all()

@router.get("/{id}")
def get(id: int, db: Session = Depends(get_db)):
    return db.query(Automation).filter(Automation.id == id).first()

@router.put("/{id}")
def update(id: int, data: dict, db: Session = Depends(get_db)):
    db_auto = db.query(Automation).filter(Automation.id == id).first()
    for k, v in data.items(): setattr(db_auto, k, v)
    db.commit()
    return db_auto

@router.delete("/{id}")
def delete(id: int, db: Session = Depends(get_db)):
    db.query(Automation).filter(Automation.id == id).delete()
    db.commit()
    return {"status": "deleted"}

@router.post("/{id}/toggle")
def toggle(id: int, db: Session = Depends(get_db)):
    auto = db.query(Automation).filter(Automation.id == id).first()
    auto.is_active = not auto.is_active
    db.commit()
    return {"is_active": auto.is_active}
