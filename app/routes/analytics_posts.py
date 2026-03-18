"""
analytics_posts.py
Analytics e monitoramento de posts.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional

from ..database import get_db
from ..models import MediaPost, PostResult, InstagramAccount
from ..security import verify_api_key

router = APIRouter()


@router.get("/posts-by-status")
def get_posts_by_status(
    company_id: str,
    days: Optional[int] = 30,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Retorna contagem de posts por status nos últimos N dias.
    Estatísticas:
    - draft, scheduled, publishing, done, error
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    posts = db.query(MediaPost).filter(
        MediaPost.company_id == company_id,
        MediaPost.created_at >= cutoff_date,
    ).all()

    status_count = {}
    for status in ["draft", "scheduled", "publishing", "done", "error"]:
        count = len([p for p in posts if p.status == status])
        status_count[status] = count

    return {
        "company_id": company_id,
        "period_days": days,
        "total_posts": len(posts),
        "by_status": status_count,
        "success_rate": (
            status_count.get("done", 0) / len(posts) * 100
            if posts else 0
        ),
    }


@router.get("/posts-by-account")
def get_posts_by_account(
    company_id: str,
    days: Optional[int] = 30,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Retorna posts publicados por conta nos últimos N dias.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    results = db.query(
        InstagramAccount.username,
        InstagramAccount.id,
        func.count(PostResult.id).label("total_posts"),
        func.sum(
            func.cast(PostResult.status == "success", func.Integer)
        ).label("successful"),
    ).join(
        PostResult, PostResult.account_id == InstagramAccount.id
    ).join(
        MediaPost, MediaPost.id == PostResult.post_id
    ).filter(
        MediaPost.company_id == company_id,
        PostResult.published_at >= cutoff_date,
    ).group_by(
        InstagramAccount.id, InstagramAccount.username
    ).all()

    accounts_stats = []
    for username, account_id, total, successful in results:
        accounts_stats.append({
            "account_id": account_id,
            "username": username,
            "total_posts": total or 0,
            "successful": successful or 0,
            "failed": (total or 0) - (successful or 0),
            "success_rate": (
                (successful or 0) / (total or 1) * 100
            ),
        })

    return {
        "company_id": company_id,
        "period_days": days,
        "total_accounts": len(accounts_stats),
        "accounts": accounts_stats,
    }


@router.get("/errors")
def get_errors(
    company_id: str,
    days: Optional[int] = 7,
    limit: Optional[int] = 50,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Retorna erros de publicação dos últimos N dias.
    Útil para debugging e monitoramento.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    errors = db.query(
        PostResult.id,
        PostResult.post_id,
        PostResult.account_id,
        PostResult.error_message,
        PostResult.created_at,
        InstagramAccount.username,
        MediaPost.caption,
    ).join(
        InstagramAccount, PostResult.account_id == InstagramAccount.id
    ).join(
        MediaPost, PostResult.post_id == MediaPost.id
    ).filter(
        PostResult.status == "error",
        MediaPost.company_id == company_id,
        PostResult.created_at >= cutoff_date,
    ).order_by(
        PostResult.created_at.desc()
    ).limit(limit).all()

    error_list = [
        {
            "result_id": e.id,
            "post_id": e.post_id,
            "account": e.username,
            "error": e.error_message,
            "timestamp": e.created_at.isoformat() if e.created_at else None,
            "post_caption": (e.caption[:100] + "...") if e.caption else None,
        }
        for e in errors
    ]

    return {
        "company_id": company_id,
        "period_days": days,
        "total_errors": len(error_list),
        "errors": error_list,
    }


@router.get("/summary")
def get_summary(
    company_id: str,
    days: Optional[int] = 30,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Retorna resumo geral de performance.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Posts
    all_posts = db.query(MediaPost).filter(
        MediaPost.company_id == company_id,
        MediaPost.created_at >= cutoff_date,
    ).all()

    # Resultados
    all_results = db.query(PostResult).join(
        MediaPost, MediaPost.id == PostResult.post_id
    ).filter(
        MediaPost.company_id == company_id,
        PostResult.created_at >= cutoff_date,
    ).all()

    success = len([r for r in all_results if r.status == "success"])
    errors = len([r for r in all_results if r.status == "error"])
    total = len(all_results)

    # Contas
    accounts = db.query(InstagramAccount).filter(
        InstagramAccount.company_id == company_id
    ).all()

    active_accounts = len([a for a in accounts if a.is_active])
    expiring_soon = len([
        a for a in accounts
        if a.token_expires_at and
        a.token_expires_at <= datetime.utcnow() + timedelta(days=7)
    ])

    return {
        "company_id": company_id,
        "period_days": days,
        "posts": {
            "total": len(all_posts),
            "draft": len([p for p in all_posts if p.status == "draft"]),
            "scheduled": len([p for p in all_posts if p.status == "scheduled"]),
            "published": len([p for p in all_posts if p.status == "done"]),
            "failed": len([p for p in all_posts if p.status == "error"]),
        },
        "publishing": {
            "total_attempts": total,
            "successful": success,
            "failed": errors,
            "success_rate": (success / total * 100) if total > 0 else 0,
        },
        "accounts": {
            "total": len(accounts),
            "active": active_accounts,
            "token_expiring_soon": expiring_soon,
        },
    }
