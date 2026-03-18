from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AnalyticsLog, Automation

router = APIRouter()

@router.get("/overview")
def overview(company_id: str, db: Session = Depends(get_db)):
    count = db.query(AnalyticsLog).join(Automation).filter(Automation.company_id == company_id).count()
    return {"total_executions": count}

@router.get("/automations/{id}")
def stats(id: int, db: Session = Depends(get_db)):
    return {"executions": db.query(AnalyticsLog).filter(AnalyticsLog.automation_id == id).count()}
