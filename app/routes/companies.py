from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Company
from pydantic import BaseModel

router = APIRouter()

class CompanyCreate(BaseModel):
    id: str
    name: str

@router.post("/")
def create(company: CompanyCreate, db: Session = Depends(get_db)):
    db_c = Company(id=company.id, name=company.name)
    db.add(db_c)
    db.commit()
    return db_c

@router.get("/{id}")
def get(id: str, db: Session = Depends(get_db)):
    return db.query(Company).filter(Company.id == id).first()

@router.put("/{id}/instagram")
def connect_ig(id: str, data: dict, db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.id == id).first()
    c.instagram_account_id = data.get('account_id')
    c.instagram_access_token = data.get('access_token')
    db.commit()
    return {"status": "connected"}
