"""
MustCompliance - Complete API
All endpoints for client onboarding, tasks, documents, compliance
"""
from fastapi import FastAPI, HTTPException, Depends, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import os
import json

from .models import (
    Base, engine, SessionLocal,
    Cabinet, Contact, Mandataire, Document, Task, TimelineEvent,
    OnboardingPhase, OnboardingStep, Reminder,
    REQUIRED_DOCS, ONBOARDING_TEMPLATE,
    check_missing_documents, calculate_completude,
    init_db, add_timeline_event, create_task
)
from .evalandgo import create_client, DEFAULT_JWT


# ============== INIT ==============

app = FastAPI(
    title="MustCompliance API",
    description="Client Onboarding & Compliance Management",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Pydantic Models ==============

class CabinetBase(BaseModel):
    nom: Optional[str] = None
    identifiant: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    immatriculation: Optional[str] = None
    numero_tva: Optional[str] = None
    statut: Optional[str] = "onboarding"

class CabinetCreate(CabinetBase):
    pass

class CabinetResponse(CabinetBase):
    id: int
    niveau: int
    respondent_id: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ContactCreate(BaseModel):
    nom: str
    prenom: str
    email: Optional[str] = None
    telephone: Optional[str] = None
    role: str
    is_mandataire: bool = False


class TaskCreate(BaseModel):
    titre: str
    description: Optional[str] = None
    type: str = "general"
    assigne_a: Optional[str] = None
    date_echeance: Optional[datetime] = None
    priorite: int = 2


class TaskUpdate(BaseModel):
    statut: Optional[str] = None
    progress: Optional[int] = None
    notes: Optional[str] = None


# ============== Startup ==============

@app.on_event("startup")
def startup():
    init_db()


# ============== Root ==============

@app.get("/")
def root():
    return {"message": "MustCompliance API v2.0", "version": "2.0.0"}


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ============== Scan EvalAndGo ==============

@app.get("/api/scan-forms")
def scan_forms(questionnaire_id: int = 303354):
    """Scan form responses from EvalAndGo"""
    client = create_client()
    respondents = client.list_respondents(questionnaire_id)
    
    db = SessionLocal()
    created, updated = 0, 0
    
    for r in respondents:
        rid = r.get("id")
        email = r.get("email")
        
        existing = db.query(Cabinet).filter(Cabinet.respondent_id == rid).first()
        
        if existing:
            existing.email = email
            existing.data_raw = r
            existing.updated_at = datetime.utcnow()
            updated += 1
        else:
            cabinet = Cabinet(
                nom=f"Cabinet {rid}",
                identifiant=f"CAB{rid}",
                email=email,
                respondent_id=rid,
                questionnaire_id=questionnaire_id,
                data_raw=r,
                statut="onboarding"
            )
            db.add(cabinet)
            created += 1
        
        db.commit()
    
    db.close()
    return {"scanned": len(respondents), "created": created, "updated": updated}


@app.get("/api/scan-documents")
def scan_documents(questionnaire_id: int = 349199):
    """Scan document uploads from EvalAndGo"""
    client = create_client()
    respondents = client.list_respondents(questionnaire_id)
    
    db = SessionLocal()
    docs_found = 0
    
    for r in respondents:
        rid = r.get("id")
        full = client.get_respondent(rid)
        
        if not full:
            continue
        
        cabinet = db.query(Cabinet).filter(Cabinet.respondent_id == rid).first()
        if not cabinet:
            cabinet = Cabinet(nom=f"Cabinet {rid}", identifiant=f"CAB{rid}", respondent_id=rid, questionnaire_id=questionnaire_id)
            db.add(cabinet)
            db.flush()
        
        for resp_ref in full.get("responses", []):
            resp_id = resp_ref.get("@id", "").split("/")[-1]
            rtype = resp_ref.get("@type", "")
            
            if "upload" in rtype.lower():
                upload_data = client.get(f"/responses/{resp_id}")
                if upload_data:
                    filename = upload_data.get("text", f"doc_{resp_id}")
                    
                    existing = db.query(Document).filter(Document.cabinet_id == cabinet.id, Document.response_id == resp_id).first()
                    if not existing:
                        doc = Document(
                            cabinet_id=cabinet.id,
                            type="upload",
                            filename=filename,
                            response_id=resp_id,
                            source="evalandgo",
                            statut="a_completer"
                        )
                        db.add(doc)
                        docs_found += 1
        
        db.commit()
    
    db.close()
    return {"scanned": len(respondents), "documents_found": docs_found}


# ============== Cabinets CRUD ==============

@app.get("/api/cabinets")
def list_cabinets(
    search: str = None,
    statut: str = None,
    min_completude: int = 0,
    skip: int = 0,
    limit: int = 100
):
    """List all cabinets with filters"""
    db = SessionLocal()
    
    query = db.query(Cabinet)
    
    if search:
        search = f"%{search}%"
        query = query.filter(
            (Cabinet.nom.like(search)) |
            (Cabinet.email.like(search)) |
            (Cabinet.identifiant.like(search))
        )
    
    if statut:
        query = query.filter(Cabinet.statut == statut)
    
    cabinets = query.offset(skip).limit(limit).all()
    
    result = []
    for c in cabinets:
        missing = check_missing_documents(c)
        result.append({
            "id": c.id,
            "nom": c.nom,
            "identifiant": c.identifiant,
            "email": c.email,
            "telephone": c.telephone,
            "immatriculation": c.immatriculation,
            "statut": c.statut,
            "niveau": missing["completude"],
            "respondent_id": c.respondent_id,
            "created_at": c.created_at.isoformat() if c.created_at else None
        })
    
    db.close()
    return result


@app.post("/api/cabinets")
def create_cabinet(data: CabinetCreate):
    """Create a new cabinet"""
    db = SessionLocal()
    
    cabinet = Cabinet(
        nom=data.nom,
        identifiant=data.identifiant or f"CAB{datetime.utcnow().timestamp()}",
        email=data.email,
        telephone=data.telephone,
        immatriculation=data.immatriculation,
        numero_tva=data.numero_tva,
        statut=data.statut
    )
    db.add(cabinet)
    db.commit()
    db.refresh(cabinet)
    
    add_timeline_event(db, cabinet.id, "cabinet_created", f"Cabinet créé: {cabinet.nom}")
    
    db.close()
    return {"id": cabinet.id, "nom": cabinet.nom}


@app.get("/api/cabinet/{cabinet_id}")
def get_cabinet(cabinet_id: int):
    """Get cabinet details with all related data"""
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    
    if not cabinet:
        db.close()
        raise HTTPException(404, "Cabinet not found")
    
    docs = db.query(Document).filter(Document.cabinet_id == cabinet_id).all()
    contacts = db.query(Contact).filter(Contact.cabinet_id == cabinet_id).all()
    tasks = db.query(Task).filter(Task.cabinet_id == cabinet_id).all()
    timeline = db.query(TimelineEvent).filter(TimelineEvent.cabinet_id == cabinet_id).order_by(TimelineEvent.created_at.desc()).limit(50).all()
    
    missing = check_missing_documents(cabinet)
    
    result = {
        "id": cabinet.id,
        "nom": cabinet.nom,
        "identifiant": cabinet.identifiant,
        "email": cabinet.email,
        "telephone": cabinet.telephone,
        "immatriculation": cabinet.immatriculation,
        "numero_tva": cabinet.numero_tva,
        "informations": cabinet.informations,
        "rgpd": cabinet.rgpd,
        "assurance": cabinet.assurance,
        "reclamations": cabinet.reclamations,
        "activites": cabinet.activites,
        "produits": cabinet.produits,
        "statut": cabinet.statut,
        "niveau": missing["completude"],
        "documents": {
            "missing": missing["missing"],
            "present": missing["present"],
            "total": missing["total"],
            "completude": missing["completude"]
        },
        "contacts": [{"id": c.id, "nom": c.nom, "prenom": c.prenom, "email": c.email, "role": c.role} for c in contacts],
        "tasks": [{"id": t.id, "titre": t.titre, "statut": t.statut, "priorite": t.priorite, "date_echeance": t.date_echeance.isoformat() if t.date_echeance else None} for t in tasks],
        "timeline": [{"id": t.id, "type": t.type, "titre": t.titre, "utilisateur": t.utilisateur, "created_at": t.created_at.isoformat()} for t in timeline],
        "created_at": cabinet.created_at.isoformat() if cabinet.created_at else None,
        "updated_at": cabinet.updated_at.isoformat() if cabinet.updated_at else None
    }
    
    db.close()
    return result


@app.patch("/api/cabinet/{cabinet_id}")
def update_cabinet(cabinet_id: int, data: CabinetBase):
    """Update cabinet"""
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    
    if not cabinet:
        db.close()
        raise HTTPException(404, "Cabinet not found")
    
    for field, value in data.dict(exclude_unset=True).items():
        setattr(cabinet, field, value)
    
    db.commit()
    add_timeline_event(db, cabinet_id, "cabinet_updated", f"Cabinet mis à jour")
    
    db.close()
    return {"message": "Updated"}


# ============== Contacts ==============

@app.get("/api/cabinet/{cabinet_id}/contacts")
def list_contacts(cabinet_id: int):
    db = SessionLocal()
    contacts = db.query(Contact).filter(Contact.cabinet_id == cabinet_id).all()
    db.close()
    return [{"id": c.id, "nom": c.nom, "prenom": c.prenom, "email": c.email, "telephone": c.telephone, "role": c.role} for c in contacts]


@app.post("/api/cabinet/{cabinet_id}/contacts")
def create_contact(cabinet_id: int, data: ContactCreate):
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    if not cabinet:
        db.close()
        raise HTTPException(404, "Cabinet not found")
    
    contact = Contact(
        cabinet_id=cabinet_id,
        nom=data.nom,
        prenom=data.prenom,
        email=data.email,
        telephone=data.telephone,
        role=data.role,
        is_mandataire=data.is_mandataire
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    
    add_timeline_event(db, cabinet_id, "contact_added", f"Contact ajouté: {data.prenom} {data.nom}")
    
    db.close()
    return {"id": contact.id}


# ============== Tasks ==============

@app.get("/api/cabinet/{cabinet_id}/tasks")
def list_tasks(cabinet_id: int, statut: str = None):
    db = SessionLocal()
    query = db.query(Task).filter(Task.cabinet_id == cabinet_id)
    if statut:
        query = query.filter(Task.statut == statut)
    tasks = query.order_by(Task.date_echeance).all()
    db.close()
    return [{"id": t.id, "titre": t.titre, "description": t.description, "type": t.type, "statut": t.statut, "priorite": t.priorite, "assigne_a": t.assigne_a, "date_echeance": t.date_echeance.isoformat() if t.date_echeance else None} for t in tasks]


@app.post("/api/cabinet/{cabinet_id}/tasks")
def create_task_endpoint(cabinet_id: int, data: TaskCreate):
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    if not cabinet:
        db.close()
        raise HTTPException(404, "Cabinet not found")
    
    task = Task(
        cabinet_id=cabinet_id,
        titre=data.titre,
        description=data.description,
        type=data.type,
        assigne_a=data.assigne_a,
        date_echeance=data.date_echeance,
        priorite=data.priorite
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    add_timeline_event(db, cabinet_id, "task_created", f"Task créée: {data.titre}")
    
    db.close()
    return {"id": task.id}


@app.patch("/api/task/{task_id}")
def update_task(task_id: int, data: TaskUpdate):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        db.close()
        raise HTTPException(404, "Task not found")
    
    if data.statut:
        task.statut = data.statut
        if data.statut == "termine" and not task.terminee_at:
            task.terminee_at = datetime.utcnow()
            add_timeline_event(db, task.cabinet_id, "task_completed", f"Task terminée: {task.titre}")
    
    if data.progress is not None:
        task.progress = data.progress
    
    db.commit()
    db.close()
    return {"message": "Updated"}


@app.get("/api/tasks")
def all_tasks(statut: str = None, assigne_a: str = None, overdue: bool = False):
    db = SessionLocal()
    query = db.query(Task)
    
    if statut:
        query = query.filter(Task.statut == statut)
    if assigne_a:
        query = query.filter(Task.assigne_a == assigne_a)
    if overdue:
        query = query.filter(Task.date_echeance < datetime.utcnow(), Task.statut != "termine")
    
    tasks = query.order_by(Task.date_echeance).all()
    db.close()
    return [{"id": t.id, "cabinet_id": t.cabinet_id, "titre": t.titre, "statut": t.statut, "priorite": t.priorite, "assigne_a": t.assigne_a, "date_echeance": t.date_echeance.isoformat() if t.date_echeance else None} for t in tasks]


# ============== Documents ==============

@app.get("/api/cabinet/{cabinet_id}/documents")
def list_documents(cabinet_id: int, statut: str = None):
    db = SessionLocal()
    query = db.query(Document).filter(Document.cabinet_id == cabinet_id)
    if statut:
        query = query.filter(Document.statut == statut)
    docs = query.all()
    db.close()
    return [{"id": d.id, "type": d.type, "sous_type": d.sous_type, "filename": d.filename, "statut": d.statut, "version": d.version} for d in docs]


@app.post("/api/cabinet/{cabinet_id}/upload")
async def upload_document(cabinet_id: int, doc_type: str, file: UploadFile = None):
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    if not cabinet:
        db.close()
        raise HTTPException(404, "Cabinet not found")
    
    filename = None
    filepath = None
    content = None
    
    if file:
        content = await file.read()
        filename = file.filename
        storage_dir = f"/tmp/documents/{cabinet_id}"
        os.makedirs(storage_dir, exist_ok=True)
        filepath = f"{storage_dir}/{filename}"
        with open(filepath, "wb") as f:
            f.write(content)
    
    doc = Document(
        cabinet_id=cabinet_id,
        type=doc_type,
        filename=filename,
        filepath=filepath,
        file_size=len(content) if content else 0,
        mime_type=file.content_type if file else None,
        source="upload",
        statut="a_signer"
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    
    add_timeline_event(db, cabinet_id, "document_uploaded", f"Document上传: {doc_type}")
    
    db.close()
    return {"id": doc.id, "message": "Document uploaded"}


@app.patch("/api/document/{doc_id}")
def update_document(doc_id: int, statut: str = None):
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        db.close()
        raise HTTPException(404, "Document not found")
    
    if statut:
        doc.statut = statut
        if statut == "signe":
            doc.date_signature = datetime.utcnow()
        add_timeline_event(db, doc.cabinet_id, "document_updated", f"Document mis à jour: {doc.type} -> {statut}")
    
    db.commit()
    db.close()
    return {"message": "Updated"}


# ============== Onboarding ==============

@app.post("/api/onboarding/{cabinet_id}/create")
def create_onboarding(cabinet_id: int):
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    if not cabinet:
        db.close()
        raise HTTPException(404, "Cabinet not found")
    
    existing = db.query(OnboardingPhase).filter(OnboardingPhase.cabinet_id == cabinet_id).first()
    if existing:
        db.close()
        return {"message": "Onboarding already exists"}
    
    sort_order = 0
    for phase_key, phase_data in ONBOARDING_TEMPLATE.items():
        phase = OnboardingPhase(
            cabinet_id=cabinet_id,
            phase_key=phase_key,
            phase_label=phase_data["label"]
        )
        db.add(phase)
        db.flush()
        
        for step_data in phase_data["steps"]:
            step = OnboardingStep(
                cabinet_id=cabinet_id,
                phase_id=phase.id,
                step_key=step_data["key"],
                step_label=step_data["label"],
                step_category=step_data["category"],
                sort_order=sort_order
            )
            db.add(step)
            sort_order += 1
    
    db.commit()
    add_timeline_event(db, cabinet_id, "onboarding_created", "Parcours d'onboarding créé")
    
    db.close()
    return {"message": "Onboarding created"}


@app.get("/api/onboarding/{cabinet_id}")
def get_onboarding(cabinet_id: int):
    db = SessionLocal()
    
    phases = db.query(OnboardingPhase).filter(OnboardingPhase.cabinet_id == cabinet_id).order_by(OnboardingPhase.id).all()
    
    result = {"cabinet_id": cabinet_id, "phases": []}
    total_steps = 0
    completed = 0
    
    for phase in phases:
        steps = db.query(OnboardingStep).filter(OnboardingStep.phase_id == phase.id).order_by(OnboardingStep.sort_order).all()
        
        phase_steps = []
        for step in steps:
            phase_steps.append({
                "id": step.id,
                "key": step.step_key,
                "label": step.step_label,
                "status": step.status,
                "progress": step.progress
            })
            total_steps += 1
            if step.status == "done":
                completed += 1
        
        result["phases"].append({
            "key": phase.phase_key,
            "label": phase.phase_label,
            "status": phase.status,
            "progress": phase.progress,
            "steps": phase_steps
        })
    
    result["total_progress"] = int((completed * 100) / total_steps) if total_steps > 0 else 0
    
    db.close()
    return result


@app.patch("/api/onboarding/{cabinet_id}/step/{step_key}")
def update_step(cabinet_id: int, step_key: str, status: str = None, progress: int = None):
    db = SessionLocal()
    step = db.query(OnboardingStep).filter(OnboardingStep.cabinet_id == cabinet_id, OnboardingStep.step_key == step_key).first()
    if not step:
        db.close()
        raise HTTPException(404, "Step not found")
    
    if status:
        step.status = status
        if status == "done" and not step.completed_at:
            step.completed_at = datetime.utcnow()
            add_timeline_event(db, cabinet_id, "step_completed", f"Étape terminée: {step.step_label}")
    
    if progress is not None:
        step.progress = progress
    
    phase = db.query(OnboardingPhase).filter(OnboardingPhase.id == step.phase_id).first()
    if phase:
        phase_steps = db.query(OnboardingStep).filter(OnboardingStep.phase_id == phase.id).all()
        if phase_steps:
            phase.progress = sum(s.progress for s in phase_steps) // len(phase_steps)
            statuses = [s.status for s in phase_steps]
            if all(s == "done" for s in statuses):
                phase.status = "done"
                phase.completed_at = datetime.utcnow()
            elif any(s == "in_progress" for s in statuses):
                phase.status = "in_progress"
                if not phase.started_at:
                    phase.started_at = datetime.utcnow()
    
    db.commit()
    db.close()
    return {"message": "Updated"}


# ============== Compliance ==============

@app.get("/api/compliance/{cabinet_id}")
def check_compliance(cabinet_id: int):
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    if not cabinet:
        db.close()
        raise HTTPException(404, "Cabinet not found")
    
    missing = check_missing_documents(cabinet)
    onboarding = get_onboarding(cabinet_id)
    docs = db.query(Document).filter(Document.cabinet_id == cabinet_id).all()
    
    doc_stats = {"a_completer": 0, "a_signer": 0, "signe": 0, "envoye": 0, "archive": 0}
    for d in docs:
        if d.statut in doc_stats:
            doc_stats[d.statut] += 1
    
    db.close()
    
    return {
        "cabinet_id": cabinet_id,
        "nom": cabinet.nom,
        "statut": cabinet.statut,
        "documents": {
            "completude": missing["completude"],
            "missing": missing["missing"],
            "present": missing["present"],
            "stats": doc_stats
        },
        "onboarding": {
            "progress": onboarding["total_progress"],
            "phases": onboarding["phases"]
        },
        "is_ready": missing["completude"] >= 100 and onboarding["total_progress"] >= 100
    }


@app.get("/api/compliance")
def check_all_compliance():
    db = SessionLocal()
    cabinets = db.query(Cabinet).all()
    
    results = []
    for cabinet in cabinets:
        missing = check_missing_documents(cabinet)
        onboarding = get_onboarding(cabinet.id)
        
        results.append({
            "cabinet_id": cabinet.id,
            "nom": cabinet.nom,
            "email": cabinet.email,
            "statut": cabinet.statut,
            "documents_progress": missing["completude"],
            "onboarding_progress": onboarding["total_progress"],
            "is_ready": missing["completude"] >= 100 and onboarding["total_progress"] >= 100
        })
    
    db.close()
    ready = sum(1 for r in results if r["is_ready"])
    return {"total": len(results), "ready": ready, "in_progress": len(results) - ready, "cabinets": results}


# ============== Timeline ==============

@app.get("/api/cabinet/{cabinet_id}/timeline")
def get_timeline(cabinet_id: int, limit: int = 50):
    db = SessionLocal()
    events = db.query(TimelineEvent).filter(TimelineEvent.cabinet_id == cabinet_id).order_by(TimelineEvent.created_at.desc()).limit(limit).all()
    db.close()
    return [{"id": e.id, "type": e.type, "titre": e.titre, "description": e.description, "utilisateur": e.utilisateur, "created_at": e.created_at.isoformat()} for e in events]


# ============== Kanban ==============

@app.get("/api/kanban")
def get_kanban():
    db = SessionLocal()
    cabinets = db.query(Cabinet).all()
    
    columns = {"onboarding": [], "onboarding_en_cours": [], "en_attente": [], "onboard": [], "resilié": []}
    
    for c in cabinets:
        missing = check_missing_documents(c)
        onboarding = get_onboarding(c.id)
        
        item = {"id": c.id, "nom": c.nom, "email": c.email, "niveau": missing["completude"], "onboarding_progress": onboarding["total_progress"]}
        
        status = c.statut or "onboarding"
        if status in columns:
            columns[status].append(item)
        else:
            columns["onboarding"].append(item)
    
    db.close()
    return columns


# ============== Reminders ==============

@app.get("/api/reminders")
def get_reminders(overdue: bool = False, upcoming: bool = False):
    db = SessionLocal()
    query = db.query(Reminder)
    now = datetime.utcnow()
    
    if overdue:
        query = query.filter(Reminder.date_echeance < now, Reminder.envoye == False)
    elif upcoming:
        cutoff = now + timedelta(days=7)
        query = query.filter(Reminder.date_echeance <= cutoff, Reminder.envoye == False)
    else:
        query = query.filter(Reminder.envoye == False)
    
    reminders = query.all()
    db.close()
    return [{"id": r.id, "cabinet_id": r.cabinet_id, "type": r.type, "titre": r.description, "date_echeance": r.date_echeance.isoformat()} for r in reminders]


# ============== Search ==============

@app.get("/api/search")
def search(q: str, limit: int = 20):
    db = SessionLocal()
    q = f"%{q}%"
    
    cabinets = db.query(Cabinet).filter((Cabinet.nom.like(q)) | (Cabinet.email.like(q)) | (Cabinet.identifiant.like(q))).limit(limit).all()
    contacts = db.query(Contact).filter((Contact.nom.like(q)) | (Contact.prenom.like(q)) | (Contact.email.like(q))).limit(limit).all()
    
    db.close()
    
    return {"cabinets": [{"id": c.id, "nom": c.nom, "email": c.email} for c in cabinets], "contacts": [{"id": c.id, "nom": c.nom, "prenom": c.prenom, "email": c.email} for c in contacts]}


# ============== Stats ==============

@app.get("/api/stats")
def get_stats():
    db = SessionLocal()
    
    total_cabinets = db.query(Cabinet).count()
    total_docs = db.query(Document).count()
    total_tasks = db.query(Task).count()
    tasks_a_faire = db.query(Task).filter(Task.statut == "a_faire").count()
    tasks_terminees = db.query(Task).filter(Task.statut == "termine").count()
    
    by_status = {}
    for status in ["onboarding", "onboarding_en_cours", "onboard", "resilié"]:
        by_status[status] = db.query(Cabinet).filter(Cabinet.statut == status).count()
    
    db.close()
    
    return {"cabinets": {"total": total_cabinets, "by_status": by_status}, "documents": {"total": total_docs}, "tasks": {"total": total_tasks, "a_faire": tasks_a_faire, "terminees": tasks_terminees}}


def handler(request, context):
    """Vercel serverless handler"""
    return app(request, context)