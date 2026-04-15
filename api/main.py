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
from pydantic import BaseModel

from .database import (
    init_db, Cabinet, Document, REQUIRED_DOCS,
    check_missing_documents, calculate_completude,
    SessionLocal, get_db
)
from .evalandgo import create_client, DEFAULT_JWT


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


# Scan EvalAndGo
@app.get("/api/scan-evalandgo", response_model=ScanResponse)
def scan_evalandgo(questionnaire_id: int = 303354):
    """Scrape all respondents from EvalAndGo"""
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
            # Update
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


def handler(request, context):
    """Vercel serverless handler"""
    return app(request, context)