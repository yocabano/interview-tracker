import os
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
import scraper
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Interview Tracker")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ApplicationCreate(BaseModel):
    url: Optional[str] = None
    company: str
    position: str
    job_description: Optional[str] = None
    required_skills: Optional[str] = None
    visa_sponsorship: Optional[str] = "unknown"
    location: Optional[str] = None
    remote_type: Optional[str] = None
    salary_range: Optional[str] = None
    applied_date: Optional[date] = None
    status: Optional[str] = "interested"
    interview_received: Optional[bool] = False
    notes: Optional[str] = None
    follow_up_date: Optional[date] = None


class ApplicationUpdate(ApplicationCreate):
    company: Optional[str] = None
    position: Optional[str] = None


def app_to_dict(a: models.Application) -> dict:
    return {
        "id": a.id,
        "url": a.url,
        "company": a.company,
        "position": a.position,
        "job_description": a.job_description,
        "required_skills": a.required_skills,
        "visa_sponsorship": a.visa_sponsorship,
        "location": a.location,
        "remote_type": a.remote_type,
        "salary_range": a.salary_range,
        "applied_date": str(a.applied_date) if a.applied_date else None,
        "status": a.status,
        "interview_received": a.interview_received,
        "notes": a.notes,
        "follow_up_date": str(a.follow_up_date) if a.follow_up_date else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html") as f:
        return f.read()


@app.post("/api/scrape")
async def scrape_url(request: Request):
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(400, "url is required")
    try:
        data = scraper.scrape_job_url(url)
        return JSONResponse(data)
    except Exception as e:
        raise HTTPException(422, f"Could not scrape URL: {e}")


@app.get("/api/applications")
def list_applications(
    status: Optional[str] = None,
    interview_received: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Application)
    if status:
        q = q.filter(models.Application.status == status)
    if interview_received is not None:
        q = q.filter(models.Application.interview_received == interview_received)
    apps = q.order_by(models.Application.created_at.desc()).all()
    return [app_to_dict(a) for a in apps]


@app.post("/api/applications", status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db)):
    app_obj = models.Application(**payload.model_dump())
    db.add(app_obj)
    db.commit()
    db.refresh(app_obj)
    return app_to_dict(app_obj)


@app.get("/api/applications/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db)):
    app_obj = db.query(models.Application).filter(models.Application.id == app_id).first()
    if not app_obj:
        raise HTTPException(404, "Not found")
    return app_to_dict(app_obj)


@app.put("/api/applications/{app_id}")
def update_application(app_id: int, payload: ApplicationUpdate, db: Session = Depends(get_db)):
    app_obj = db.query(models.Application).filter(models.Application.id == app_id).first()
    if not app_obj:
        raise HTTPException(404, "Not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(app_obj, field, value)
    db.commit()
    db.refresh(app_obj)
    return app_to_dict(app_obj)


@app.delete("/api/applications/{app_id}", status_code=204)
def delete_application(app_id: int, db: Session = Depends(get_db)):
    app_obj = db.query(models.Application).filter(models.Application.id == app_id).first()
    if not app_obj:
        raise HTTPException(404, "Not found")
    db.delete(app_obj)
    db.commit()
