"""
MustCompliance - FastAPI Backend
REST API for CGP cabinet compliance management
"""
import os
import json
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from .database import (
    init_db, Cabinet, Document, REQUIRED_DOCS,
    check_missing_documents, calculate_completude,
    SessionLocal, get_db
)
from .evalandgo import create_client, DEFAULT_JWT
from .onboarding import (
    create_onboarding_for_cabinet,
    get_onboarding_status,
    update_step_status,
    ONBOARDING_TEMPLATE
)


# Initialize
app = FastAPI(
    title="MustCompliance API",
    description="CGP Cabinet Compliance Dashboard API",
    version="1.0.0"
)

# CORS
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
    immatriculation: Optional[str] = None


class CabinetResponse(CabinetBase):
    id: int
    statut: str
    completude: int
    respondent_id: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


class CabinetDetail(BaseModel):
    id: int
    nom: Optional[str]
    identifiant: Optional[str]
    email: Optional[str]
    telephone: Optional[str]
    immatriculation: Optional[str]
    numero_tva: Optional[str]
    informations: Optional[str]
    rgpd: Optional[str]
    lien_capitalistique: Optional[str]
    activites: Optional[list]
    assurance: Optional[str]
    association: Optional[str]
    reclamations: Optional[str]
    communications: Optional[str]
    remunerations_incitations: Optional[str]
    representant_legaux: Optional[list]
    conseillers: Optional[list]
    clients: Optional[list]
    styles: Optional[list]
    produits: Optional[list]
    statut: str
    completude: int
    documents_manquants: list
    created_at: datetime
    
    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: int
    cabinet_id: int
    type: str
    sous_type: Optional[str]
    filename: Optional[str]
    valide: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class ScanResponse(BaseModel):
    scanned: int
    created: int
    updated: int


# ============== API Routes ==============

@app.on_event("startup")
async def startup():
    init_db()


@app.get("/")
def root():
    return {"message": "MustCompliance API", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ============== API Routes ==============

# Scan EvalAndGo - Forms
@app.get("/api/scan-forms", response_model=ScanResponse)
def scan_forms(questionnaire_id: int = 303354):
    """Scrape form responses from EvalAndGo questionnaire"""
    client = create_client()
    
    # Get respondents
    respondents = client.list_respondents(questionnaire_id)
    
    db = SessionLocal()
    created_count = 0
    updated_count = 0
    
    for respondent in respondents:
        rid = respondent.get("id")
        email = respondent.get("email")
        
        # Check if exists
        existing = db.query(Cabinet).filter(
            Cabinet.respondent_id == rid
        ).first()
        
        if existing:
            existing.email = email
            existing.data_raw = respondent
            existing.updated_at = datetime.utcnow()
            updated_count += 1
        else:
            # Create
            cabinet = Cabinet(
                nom=f"Cabinet {rid}",
                identifiant=f"CAB{rid}",
                email=email,
                respondent_id=rid,
                questionnaire_id=questionnaire_id,
                data_raw=respondent,
                statut="nouveau"
            )
            db.add(cabinet)
            created_count += 1
        
        db.commit()
    
    db.close()
    
    return ScanResponse(
        scanned=len(respondents),
        created=created_count,
        updated=updated_count
    )


# Scan EvalAndGo - Documents
@app.get("/api/scan-documents", response_model=ScanResponse)
def scan_documents(questionnaire_id: int = 349199):
    """Scrape document uploads from EvalAndGo questionnaire"""
    client = create_client()
    
    # Get respondents
    respondents = client.list_respondents(questionnaire_id)
    
    db = SessionLocal()
    created_count = 0
    updated_count = 0
    
    for respondent in respondents:
        rid = respondent.get("id")
        
        # Get full respondent data with responses
        full_respondent = client.get_respondent(respondent.get("id"))
        
        if not full_respondent:
            continue
        
        # Find cabinet
        cabinet = db.query(Cabinet).filter(
            Cabinet.respondent_id == rid
        ).first()
        
        if not cabinet:
            # Create cabinet if not exists
            cabinet = Cabinet(
                nom=f"Cabinet {rid}",
                identifiant=f"CAB{rid}",
                respondent_id=rid,
                questionnaire_id=questionnaire_id,
                data_raw=full_respondent,
                statut="nouveau"
            )
            db.add(cabinet)
            db.flush()
            created_count += 1
        
        # Process responses looking for uploads
        for resp_ref in full_respondent.get("responses", []):
            resp_id = resp_ref.get("@id", "").split("/")[-1]
            resp_type = resp_ref.get("@type", "")
            
            # Check for upload response
            if "upload" in resp_type.lower():
                # Get upload details
                upload_data = client.get(f"/responses/{resp_id}")
                
                if upload_data:
                    filename = upload_data.get("text", f"document_{resp_id}")
                    question_ref = resp_ref.get("question", "")
                    question_id = question_ref.split("/")[-1] if question_ref else None
                    
                    # Check if document already exists
                    existing = db.query(Document).filter(
                        Document.cabinet_id == cabinet.id,
                        Document.response_id == resp_id
                    ).first()
                    
                    if not existing:
                        doc = Document(
                            cabinet_id=cabinet.id,
                            type="upload",
                            response_id=resp_id,
                            filename=filename,
                            source="evalandgo"
                        )
                        db.add(doc)
                        updated_count += 1
        
        db.commit()
    
    db.close()
    
    return ScanResponse(
        scanned=len(respondents),
        created=created_count,
        updated=updated_count
    )


# Download document from EvalAndGo
@app.get("/api/document/{doc_id}/download")
def download_document(doc_id: int):
    """Download document from EvalAndGo"""
    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    
    if not doc:
        raise HTTPException(404, "Document not found")
    
    if not doc.response_id:
        raise HTTPException(400, "No response ID for this document")
    
    client = create_client()
    content = client.download_upload(doc.response_id)
    
    db.close()
    
    if content:
        return Response(
            content=content,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={doc.filename}"}
        )
    
    raise HTTPException(404, "Could not download document")


# Download all documents for a cabinet
@app.get("/api/cabinet/{cabinet_id}/downloads")
def download_cabinet_documents(cabinet_id: int):
    """Download all documents for a cabinet as ZIP"""
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    
    if not cabinet:
        raise HTTPException(404, "Cabinet not found")
    
    docs = db.query(Document).filter(Document.cabinet_id == cabinet_id).all()
    
    if not docs:
        raise HTTPException(404, "No documents for this cabinet")
    
    # Download all documents
    import io
    import zipfile
    
    client = create_client()
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            if doc.response_id:
                content = client.download_upload(doc.response_id)
                if content:
                    zf.writestr(doc.filename or f"doc_{doc.id}", content)
    
    zip_buffer.seek(0)
    
    db.close()
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={cabinet.nom}_documents.zip"}
    )


# Legacy scan endpoint
@app.get("/api/scan-evalandgo", response_model=ScanResponse)
def scan_evalandgo(questionnaire_id: int = 303354):
    """Scrape all respondents from EvalAndGo (legacy)"""
    return scan_forms(questionnaire_id)


# List cabinets
@app.get("/api/cabinets", response_model=List[CabinetResponse])
def list_cabinets(
    skip: int = 0,
    limit: int = 100,
    search: str = None,
    min_completude: int = 0
):
    """List all cabinets"""
    db = SessionLocal()
    
    query = db.query(Cabinet)
    
    if search:
        search = f"%{search}%"
        query = query.filter(
            (Cabinet.nom.like(search)) |
            (Cabinet.email.like(search)) |
            (Cabinet.identifiant.like(search))
        )
    
    if min_completude > 0:
        query = query.filter(Cabinet.completude >= min_completude)
    
    cabinets = query.offset(skip).limit(limit).all()
    
    # Calculate completude
    result = []
    for cabinet in cabinets:
        comp = calculate_completude(cabinet)
        cabinet.completude = comp
        result.append(CabinetResponse(
            id=cabinet.id,
            nom=cabinet.nom,
            identifiant=cabinet.identifiant,
            email=cabinet.email,
            immatriculation=cabinet.immatriculation,
            statut=cabinet.statut,
            completude=comp,
            respondent_id=cabinet.respondent_id,
            created_at=cabinet.created_at
        ))
    
    db.close()
    return result


# Cabinet detail
@app.get("/api/cabinet/{cabinet_id}", response_model=CabinetDetail)
def get_cabinet(cabinet_id: int):
    """Get cabinet details"""
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    
    if not cabinet:
        raise HTTPException(404, "Cabinet not found")
    
    # Get missing docs
    missing = check_missing_documents(cabinet)
    
    # Get documents
    docs = db.query(Document).filter(Document.cabinet_id == cabinet_id).all()
    
    # Get documents for this cabinet
    cabinet_docs = [d for d in cabinet.documents]
    
    db.close()
    
    return CabinetDetail(
        id=cabinet.id,
        nom=cabinet.nom,
        identifiant=cabinet.identifiant,
        email=cabinet.email,
        telephone=cabinet.telephone,
        immatriculation=cabinet.immatriculation,
        numero_tva=cabinet.numero_tva,
        informations=cabinet.informations,
        rgpd=cabinet.rgpd,
        lien_capitalistique=cabinet.lien_capitalistique,
        activites=cabinet.activites,
        assurance=cabinet.assurance,
        association=cabinet.association,
        reclamations=cabinet.reclamations,
        communications=cabinet.communications,
        remunerations_incitations=cabinet.remunerations_incitations,
        representant_legaux=cabinet.representant_legaux,
        conseillers=cabinet.conseillers,
        clients=cabinet.clients,
        styles=cabinet.styles,
        produits=cabinet.produits,
        statut=cabinet.statut,
        completude=cabinet.completude,
        documents_manquants=missing["missing"],
        created_at=cabinet.created_at
    )


# Upload document
@app.post("/api/cabinet/{cabinet_id}/upload")
def upload_document(
    cabinet_id: int,
    doc_type: str,
    sous_type: str = None,
    file: UploadFile = None
):
    """Upload document for cabinet"""
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    
    if not cabinet:
        raise HTTPException(404, "Cabinet not found")
    
    # Save file
    filename = None
    filepath = None
    content = None
    
    if file:
        content = await file.read()
        filename = file.filename
        
        # Save to storage
        storage_dir = f"/tmp/documents/{cabinet_id}"
        os.makedirs(storage_dir, exist_ok=True)
        filepath = f"{storage_dir}/{filename}"
        
        with open(filepath, "wb") as f:
            f.write(content)
    
    # Create document record
    doc = Document(
        cabinet_id=cabinet_id,
        type=doc_type,
        sous_type=sous_type,
        filename=filename,
        filepath=filepath,
        file_size=len(content) if content else 0,
        mime_type=file.content_type if file else None,
        source="upload",
        valide=True,
        date_validation=datetime.utcnow()
    )
    db.add(doc)
    
    # Update completude
    cabinet.completude = calculate_completude(cabinet)
    
    db.commit()
    db.close()
    
    return {"message": "Document uploaded", "id": doc.id}


# Get all documents for matrix
@app.get("/api/matrix")
def get_matrix():
    """Get completion matrix for all cabinets"""
    db = SessionLocal()
    cabinets = db.query(Cabinet).all()
    
    matrix = []
    for cabinet in cabinets:
        missing = check_missing_documents(cabinet)
        matrix.append({
            "id": cabinet.id,
            "nom": cabinet.nom,
            "identifiant": cabinet.identifiant,
            "completude": missing["completude"],
            "missing": missing["missing"],
            "present": missing["present"]
        })
    
    db.close()
    return matrix


# Stats
@app.get("/api/stats")
def get_stats():
    """Get global statistics"""
    db = SessionLocal()
    total = db.query(Cabinet).count()
    documents = db.query(Document).count()
    
    # By status
    complet = db.query(Cabinet).filter(Cabinet.completude >= 80).count()
    incomplete = db.query(Cabinet).filter(
        Cabinet.completude > 0,
        Cabinet.completude < 80
    ).count()
    pending = db.query(Cabinet).filter(Cabinet.completude == 0).count()
    
    db.close()
    
    return {
        "total_cabinets": total,
        "total_documents": documents,
        "complet": complet,
        "incomplete": incomplete,
        "pending": pending
    }


# Export Excel endpoint
@app.get("/api/export")
def export_excel():
    """Export all cabinets to CSV"""
    db = SessionLocal()
    cabinets = db.query(Cabinet).all()
    
    rows = []
    for cabinet in cabinets:
        missing = check_missing_documents(cabinet)
        
        # Build row
        row = {
            "ID": cabinet.id,
            "Nom": cabinet.nom,
            "Identifiant": cabinet.identifiant,
            "Email": cabinet.email,
            "ORIAS": cabinet.immatriculation,
            "TVA": cabinet.numero_tva,
            "Complétude": f"{missing['completude']}%",
        }
        
        # Add required docs status
        for doc_code in REQUIRED_DOCS.keys():
            row[doc_code] = "✅" if doc_code in missing["present"] else "❌"
        
        rows.append(row)
    
    db.close()
    return rows


# ============== Onboarding Endpoints ==============

@app.post("/api/onboarding/{cabinet_id}/create")
def create_onboarding(cabinet_id: int):
    """Create onboarding workflow for cabinet"""
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    if not cabinet:
        db.close()
        raise HTTPException(404, "Cabinet not found")
    db.close()
    
    result = create_onboarding_for_cabinet(cabinet_id)
    return result


@app.get("/api/onboarding/{cabinet_id}")
def get_onboarding(cabinet_id: int):
    """Get onboarding status for cabinet"""
    return get_onboarding_status(cabinet_id)


@app.patch("/api/onboarding/{cabinet_id}/step/{step_key}")
def update_step(cabinet_id: int, step_key: str, status: str, progress: int = None, notes: str = None):
    """Update step status"""
    return update_step_status(cabinet_id, step_key, status, progress, notes)


@app.get("/api/onboarding/templates")
def get_templates():
    """Get onboarding templates"""
    return ONBOARDING_TEMPLATE


# ============== Compliance Check ==============

@app.get("/api/compliance/{cabinet_id}")
def check_compliance(cabinet_id: int):
    """Check if all required documents are ready"""
    db = SessionLocal()
    cabinet = db.query(Cabinet).filter(Cabinet.id == cabinet_id).first()
    
    if not cabinet:
        raise HTTPException(404, "Cabinet not found")
    
    # Check documents
    missing = check_missing_documents(cabinet)
    
    # Get onboarding
    onboarding = get_onboarding_status(cabinet_id)
    
    # Get documents
    docs = db.query(Document).filter(Document.cabinet_id == cabinet_id).all()
    
    db.close()
    
    return {
        "cabinet_id": cabinet_id,
        "nom": cabinet.nom,
        "documents": {
            "completude": missing["completude"],
            "missing": missing["missing"],
            "present": missing["present"],
            "total_required": len(REQUIRED_DOCS)
        },
        "onboarding": {
            "progress": onboarding["total_progress"],
            "phases": onboarding["phases"]
        },
        "documents_uploaded": len(docs),
        "is_ready": missing["completude"] >= 100 and onboarding["total_progress"] >= 100
    }


@app.get("/api/compliance")
def check_all_compliance():
    """Check compliance for all cabinets"""
    db = SessionLocal()
    cabinets = db.query(Cabinet).all()
    
    results = []
    for cabinet in cabinets:
        missing = check_missing_documents(cabinet)
        onboarding = get_onboarding_status(cabinet.id)
        
        results.append({
            "cabinet_id": cabinet.id,
            "nom": cabinet.nom,
            "email": cabinet.email,
            "documents_progress": missing["completude"],
            "onboarding_progress": onboarding["total_progress"],
            "is_ready": missing["completude"] >= 100 and onboarding["total_progress"] >= 100
        })
    
    db.close()
    
    ready = sum(1 for r in results if r["is_ready"])
    return {
        "total": len(results),
        "ready": ready,
        "in_progress": len(results) - ready,
        "cabinets": results
    }


def handler(request, context):
    """Vercel serverless handler"""
    return app(request, context)