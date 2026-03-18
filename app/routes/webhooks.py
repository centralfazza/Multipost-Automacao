from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
import os
from ..database import get_db
from ..automation_engine import AutomationEngine
from ..models import Company

router = APIRouter()
VERIFY_TOKEN = os.getenv("INSTAGRAM_VERIFY_TOKEN", "fazza_token")

@router.get("/instagram")
def verify(request: Request):
    if request.query_params.get("hub.verify_token") == VERIFY_TOKEN:
        return int(request.query_params.get("hub.challenge"))
    raise HTTPException(status_code=403)

@router.post("/instagram")
async def instagram_webhook(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    engine = AutomationEngine(db)
    if data.get('object') == 'instagram':
        for entry in data.get('entry', []):
            company = db.query(Company).filter(Company.instagram_account_id == entry.get('id')).first()
            if not company: continue
            for change in entry.get('changes', []):
                if change.get('field') == 'comments':
                    engine.process_instagram_comment(company.id, change.get('value'))
    return {"ok": True}

@router.post("/whatsapp")
def whatsapp_webhook():
    return {"ok": True}
