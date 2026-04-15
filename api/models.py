"""
MustCompliance - Full Data Models
Complete client onboarding, tasks, documents, and compliance
"""
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship, declarative_base
import os

Base = declarative_base()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./db.sqlite3")

from sqlalchemy import create_engine
engine = create_engine(DATABASE_URL, echo=False)
from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(bind=engine)


# ============== CLIENT STATUS ==============
class ClientStatus:
    ONBOARDING = "onboarding"
    ONBOARD = "onboard"
    RESILIED = "resilié"
    IN_PROGRESS = "onboarding_en_cours"
    PAUSE = "en_pause"


# ============== MAIN TABLES ==============

class Cabinet(Base):
    """CGP Cabinet / Client"""
    __tablename__ = "cabinets"
    
    id = Column(Integer, primary_key=True)
    
    # Identity
    nom = Column(String(255))
    identifiant = Column(String(100), unique=True)
    email = Column(String(255))
    telephone = Column(String(50))
    
    # Status
    statut = Column(String(50), default=ClientStatus.ONBOARDING)
    niveau = Column(Integer, default=0)  # 0-100 completion
    
    # Regulatory
    immatriculation = Column(String(100))  # ORIAS
    numero_tva = Column(String(50))
    
    # Info
    informations = Column(Text)
    rgpd = Column(Text)
    lien_capitalistique = Column(Text)
    
    # Activities & Products
    activites = Column(JSON)  # ["CIF", "IAS", "IOBSP", "IMMO"]
    assurance = Column(Text)
    association = Column(Text)
    reclamations = Column(Text)
    communications = Column(Text)
    remunerations_incitations = Column(Text)
    
    # Representatives
    representant_legaux = Column(JSON)
    conseillers = Column(JSON)
    
    # Products
    produits = Column(JSON)  # Products held or planned
    
    # Dates
    date_onboarding = Column(DateTime, default=datetime.utcnow)
    date_renewal = Column(DateTime)  # Annual renewal
    date_review = Column(DateTime)  # Review date
    
    # Raw data
    respondent_id = Column(Integer)
    questionnaire_id = Column(Integer)
    data_raw = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = relationship("Document", back_populates="cabinet", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="cabinet", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="cabinet", cascade="all, delete-orphan")
    timeline = relationship("TimelineEvent", back_populates="cabinet", cascade="all, delete-orphan")
    onboarding_steps = relationship("OnboardingStep", back_populates="cabinet", cascade="all, delete-orphan")
    onboarding_phases = relationship("OnboardingPhase", back_populates="cabinet", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Cabinet {self.nom}>"


class Contact(Base):
    """Contact person for a cabinet"""
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    
    # Contact info
    nom = Column(String(255))
    prenom = Column(String(255))
    email = Column(String(255))
    telephone = Column(String(50))
    role = Column(String(100))  # Responsable, Mandataire, Contact, etc.
    
    # Status
    actif = Column(Boolean, default=True)
    
    # Mandataire link
    is_mandataire = Column(Boolean, default=False)
    mandataire_id = Column(Integer, ForeignKey("mandataires.id"))
    
    # Exchange history
    historique_echanges = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    cabinet = relationship("Cabinet", back_populates="contacts")
    
    def __repr__(self):
        return f"<Contact {self.prenom} {self.nom}>"


class Mandataire(Base):
    """Mandataire / Advisor"""
    __tablename__ = "mandataires"
    
    id = Column(Integer, primary_key=True)
    nom = Column(String(255))
    email = Column(String(255))
    telephone = Column(String(50))
    statut = Column(String(50), default="actif")
    
    # Certification
    certifications = Column(JSON)  # CIF, IAS, etc.
    numero_certificat = Column(String(100))
    
    # Cabinet linked
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Document(Base):
    """Document for a cabinet"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    
    # Document type
    type = Column(String(100))  # ORIAS, RGPD, RCP, DER, LM, RCDA, LCB-FT, etc.
    sous_type = Column(String(100))
    categorie = Column(String(100))  # Réglementaire, Interne, Contractuel
    
    # File info
    filename = Column(String(255))
    filepath = Column(String(500))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    
    # Content
    contenu = Column(Text)
    resume = Column(Text)
    
    # Status: a_completer, a_signer, signe, envoye, archive
    statut = Column(String(50), default="a_completer")
    version = Column(Integer, default=1)
    
    # Dates
    date_expiration = Column(DateTime)
    date_validation = Column(DateTime)
    date_signature = Column(DateTime)
    
    # Source
    source = Column(String(50))  # evalandgo, upload, generated
    
    # EvalAndGo link
    response_id = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    cabinet = relationship("Cabinet", back_populates="documents")
    
    def __repr__(self):
        return f"<Document {self.type} for cabinet={self.cabinet_id}>"


# ============== TASKS ==============

class Task(Base):
    """Task for a cabinet"""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    
    # Task info
    titre = Column(String(255))
    description = Column(Text)
    type = Column(String(100))  # relance, document, signature, review
    
    # Status & Priority
    statut = Column(String(50), default="a_faire")  # a_faire, en_cours, termine, annule
    priorite = Column(Integer, default=2)  # 1=haute, 2=moyenne, 3=basse
    
    # Assignment
    assigne_a = Column(String(100))  # Owner
    cree_par = Column(String(100))
    
    # Dates
    date_echeance = Column(DateTime)
    date_rappel = Column(DateTime)  # Reminder date
    terminee_at = Column(DateTime)
    
    # Linked items
    document_id = Column(Integer, ForeignKey("documents.id"))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    cabinet = relationship("Cabinet", back_populates="tasks")
    
    def __repr__(self):
        return f"<Task {self.titre}>"


# ============== TIMELINE ==============

class TimelineEvent(Base):
    """Activity history for a cabinet"""
    __tablename__ = "timeline_events"
    
    id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    
    # Event
    type = Column(String(100))  # document_uploaded, status_changed, task_completed, etc.
    titre = Column(String(255))
    description = Column(Text)
    
    # Who
    utilisateur = Column(String(100))
    
    # Data
    data = Column(JSON)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    cabinet = relationship("Cabinet", back_populates="timeline")
    
    def __repr__(self):
        return f"<TimelineEvent {self.type}>"


# ============== ONBOARDING ==============

class OnboardingPhase(Base):
    """Phase in onboarding"""
    __tablename__ = "onboarding_phases"
    
    id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    
    phase_key = Column(String(50))
    phase_label = Column(String(100))
    status = Column(String(20), default="todo")
    progress = Column(Integer, default=0)
    
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    cabinet = relationship("Cabinet", back_populates="onboarding_phases")
    steps = relationship("OnboardingStep", back_populates="phase", cascade="all, delete-orphan")


class OnboardingStep(Base):
    """Step in onboarding phase"""
    __tablename__ = "onboarding_steps"
    
    id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    phase_id = Column(Integer, ForeignKey("onboarding_phases.id"))
    
    step_key = Column(String(50))
    step_label = Column(String(100))
    step_category = Column(String(50))
    
    status = Column(String(20), default="todo")
    progress = Column(Integer, default=0)
    
    notes = Column(Text)
    completed_at = Column(DateTime)
    completed_by = Column(String(100))
    
    sort_order = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    phase = relationship("OnboardingPhase", back_populates="steps")
    cabinet = relationship("Cabinet", back_populates="onboarding_steps")
    
    def __repr__(self):
        return f"<OnboardingStep {self.step_key}={self.status}>"


# ============== CHECKLIST TEMPLATES ==============

class ChecklistTemplate(Base):
    """Checklist template by client type"""
    __tablename__ = "checklist_templates"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    type_client = Column(String(100))  # CIF, IAS, IOBSP, etc.
    produits = Column(JSON)  # Applicable products
    
    steps = Column(JSON)  # Template steps
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ============== REMINDERS ==============

class Reminder(Base):
    """Automatic reminders"""
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    
    type = Column(String(100))  # renewal, review, document_missing, etc.
    titre = Column(String(255))
    description = Column(Text)
    
    date_echeance = Column(DateTime)
    envoye = Column(Boolean, default=False)
    envoye_at = Column(DateTime)
    
    cree_par = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.utcnow)


# ============== DOCUMENT TYPES ==============

REQUIRED_DOCS = {
    "ORIAS": {"label": "Immatriculation ORIAS", "field": "immatriculation", "categorie": "reglementaire"},
    "RGPD": {"label": "Politique RGPD", "field": "rgpd", "categorie": "reglementaire"},
    "RCP": {"label": "Responsabilité Civile Professionnelle", "field": "assurance", "categorie": "reglementaire"},
    "Réclamations": {"label": "Procédure réclamations", "field": "reclamations", "categorie": "reglementaire"},
    "RCDA": {"label": "Rapport Conseil Déclaration d'Adéquation", "field": "informations", "categorie": "reglementaire"},
    "DER": {"label": "Document Entrée en Relation", "field": "informations", "categorie": "contractuel"},
    "LM": {"label": "Lettre de Mission", "field": "informations", "categorie": "contractuel"},
    "LCB-FT": {"label": "Fiche Vigilance AML", "field": "representant_legaux", "categorie": "reglementaire"},
}


# ============== ONBOARDING TEMPLATES ==============

ONBOARDING_TEMPLATE = {
    "decouverte": {
        "label": "Découverte",
        "steps": [
            {"key": "contact_initial", "label": "Contact initial", "category": "discovery"},
            {"key": "collecte_info", "label": "Collecte informations", "category": "discovery"},
            {"key": "Analyse_besoins", "label": "Analyse des besoins", "category": "discovery"},
            {"key": "presentation_offre", "label": "Présentation offre", "category": "discovery"},
        ]
    },
    "conseil": {
        "label": "Conseil",
        "steps": [
            {"key": "analyse_financiere", "label": "Analyse financière", "category": "advice"},
            {"key": "diagnostic", "label": "Diagnostic patrimonial", "category": "advice"},
            {"key": "recommandations", "label": "Recommandations", "category": "advice"},
            {"key": "rapport_rcda", "label": "RCDA - Rapport d'adéquation", "category": "advice"},
        ]
    },
    "signature": {
        "label": "Signature",
        "steps": [
            {"key": "der", "label": "Document Entrée en Relation (DER)", "category": "signature"},
            {"key": "lm", "label": "Lettre de Mission", "category": "signature"},
            {"key": "mandat", "label": "Mandat de conseil", "category": "signature"},
            {"key": "documents_compl", "label": "Documents complémentaires", "category": "signature"},
        ]
    },
    "mise_en_service": {
        "label": "Mise en service",
        "steps": [
            {"key": "creation_compte", "label": "Création compte client", "category": "setup"},
            {"key": "parametrage", "label": "Paramétrage", "category": "setup"},
            {"key": "formation_client", "label": "Formation client", "category": "setup"},
            {"key": "premier_rendezvous", "label": "Premier rendez-vous", "category": "setup"},
        ]
    },
    "suivi": {
        "label": "Suivi",
        "steps": [
            {"key": "suivi_annuel", "label": "Suivi annuel", "category": "followup"},
            {"key": "mise_a_jour", "label": "Mise à jour dossier", "category": "followup"},
            {"key": "revue_contrat", "label": "Revue contrat", "category": "followup"},
        ]
    }
}


# ============== HELPERS ==============

def check_missing_documents(cabinet):
    """Check which documents are missing"""
    missing, present = [], []
    for doc_code, doc_info in REQUIRED_DOCS.items():
        field = doc_info["field"]
        has_value = hasattr(cabinet, field) and getattr(cabinet, field)
        if has_value:
            present.append(doc_code)
        else:
            missing.append(doc_code)
    total = len(REQUIRED_DOCS)
    completude = int((len(present) / total) * 100) if total > 0 else 0
    return {"missing": missing, "present": present, "total": total, "completude": completude}


def calculate_completude(cabinet):
    """Calculate overall completion percentage"""
    missing = check_missing_documents(cabinet)
    return missing["completude"]


def init_db():
    """Initialize all database tables"""
    Base.metadata.create_all(engine)


# ============== QUICK HELPERS ==============

def add_timeline_event(db, cabinet_id, event_type, titre, description=None, utilisateur="system", data=None):
    """Add a timeline event"""
    event = TimelineEvent(
        cabinet_id=cabinet_id,
        type=event_type,
        titre=titre,
        description=description,
        utilisateur=utilisateur,
        data=data or {}
    )
    db.add(event)
    db.commit()
    return event


def create_task(db, cabinet_id, titre, description=None, type="general", assigne_a=None, date_echeance=None, priorite=2):
    """Create a task for a cabinet"""
    task = Task(
        cabinet_id=cabinet_id,
        titre=titre,
        description=description,
        type=type,
        assigne_a=assigne_a,
        date_echeance=date_echeance,
        priorite=priorite
    )
    db.add(task)
    db.commit()
    
    # Add timeline
    add_timeline_event(db, cabinet_id, "task_created", f"Task créée: {titre}")
    
    return task


def get_upcoming_reminders(db, days=7):
    """Get reminders due in next N days"""
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() + timedelta(days=days)
    return db.query(Reminder).filter(
        Reminder.date_echeance <= cutoff,
        Reminder.envoye == False
    ).all()