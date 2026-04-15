"""
MustCompliance CGP Scraper - Database Models
SQLAlchemy models for CGP cabinet compliance tracking
"""
import os
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean, 
    DateTime, JSON, Float
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./db.sqlite3")


class Cabinet(Base):
    """CGP Cabinet / Advisory Firm"""
    __tablename__ = "cabinets"
    
    id = Column(Integer, primary_key=True)
    
    # Identity
    nom = Column(String(255))
    identifiant = Column(String(100), unique=True)
    email = Column(String(255))
    telephone = Column(String(50))
    
    # ACL & Access
    aclCabinet = Column(JSON)  # Access control list
    
    # Regulatory
    immatriculation = Column(String(100))  # ORIAS number
    numero_tva = Column(String(50))
    
    # Information & RGPD
    informations = Column(Text)
    rgpd = Column(Text)
    lien_capitalistique = Column(Text)
    
    # Activities
    activites = Column(JSON)  # List of activities: CIF, IAS, IOBSP, IMMO
    assurance = Column(Text)
    association = Column(Text)
    
    # Other
    reclamations = Column(Text)
    communications = Column(Text)
    remunerations_incitations = Column(Text)
    representant_legaux = Column(JSON)
    
    # Persons
    conseillers = Column(JSON)
    clients = Column(JSON)
    
    # Products
    styles = Column(JSON)  # Product styles
    produits = Column(JSON)
    
    # Status
    statut = Column(String(50), default="en_attente")
    completude = Column(Integer, default=0)
    
    # EvalAndGo
    respondent_id = Column(Integer)
    questionnaire_id = Column(Integer)
    
    # Raw data
    data_raw = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = relationship("Document", back_populates="cabinet")
    
    def __repr__(self):
        return f"<Cabinet {self.nom or self.id}>"


class Document(Base):
    """Regulatory Document"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer)
    
    # Type
    type = Column(String(100), nullable=False)  # DER, LM, RCDA, RIC, LCB-FT, ORIAS, RCP, RGF
    sous_type = Column(String(100))
    
    # File
    filename = Column(String(255))
    filepath = Column(String(500))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    
    # Content
    contenu = Column(Text)
    resume = Column(Text)
    
    # Validation
    valide = Column(Boolean, default=False)
    date_validation = Column(DateTime)
    date_expiration = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source = Column(String(50))  # evalandgo, upload, generated
    
    # Relationships
    cabinet = relationship("Cabinet", back_populates="documents")
    
    def __repr__(self):
        return f"<Document {self.type} cabinet={self.cabinet_id}>"


# Required documents registry
REQUIRED_DOCS = {
    "ORIAS": {"label": "Immatriculation ORIAS", "field": "immatriculation"},
    "RGPD": {"label": "Politique RGPD", "field": "rgpd"},
    "RCP": {"label": "Responsabilité Civile Professionnelle", "field": "assurance"},
    "Réclamations": {"label": "Procédure réclamations", "field": "reclamations"},
    "RCDA": {"label": "Rapport Conseil Déclaration d'Adéquation", "field": "informations"},
    "DER": {"label": "Document Entrée en Relation", "field": "informations"},
    "LM": {"label": "Lettre de Mission", "field": "informations"},
    "LCB-FT": {"label": "Fiche Vigilance AML", "field": "representant_legaux"},
}


def check_missing_documents(cabinet: Cabinet) -> dict:
    """Check which documents are missing for a cabinet"""
    missing = []
    present = []
    
    for doc_code, doc_info in REQUIRED_DOCS.items():
        field = doc_info["field"]
        
        # Check if field has value
        has_value = hasattr(cabinet, field) and getattr(cabinet, field)
        
        if has_value:
            # Also check if uploaded document exists
            doc_exists = any(
                d.type == doc_code and d.valide 
                for d in cabinet.documents
            )
            if doc_exists:
                present.append(doc_code)
            else:
                missing.append(doc_code)
        else:
            missing.append(doc_code)
    
    return {
        "missing": missing,
        "present": present,
        "total": len(REQUIRED_DOCS),
        "completude": int((len(present) / len(REQUIRED_DOCS)) * 100) if REQUIRED_DOCS else 0
    }


def calculate_completude(cabinet: Cabinet) -> int:
    """Calculate completion percentage"""
    result = check_missing_documents(cabinet)
    return result["completude"]


# Database engine
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()