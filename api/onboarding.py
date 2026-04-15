"""
MustCompliance - Onboarding Workflow Models
Kanban-style onboarding with training and production stages
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base as Base
from .database import SessionLocal


class OnboardingStep(Base):
    """Individual step in onboarding workflow"""
    __tablename__ = "onboarding_steps"
    
    id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    
    # Step definition
    step_key = Column(String(50))  # training, docs, production, page, user
    step_label = Column(String(100))
    step_category = Column(String(50))  # training, docs, production, setup
    
    # Status
    status = Column(String(20), default="todo")  # todo, in_progress, done, skipped
    progress = Column(Integer, default=0)  # 0-100
    
    # Details
    notes = Column(Text)
    completed_at = Column(DateTime)
    completed_by = Column(String(100))
    
    # Ordering
    sort_order = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<OnboardingStep {self.step_key}={self.status}>"


class OnboardingPhase(Base):
    """Phase in onboarding (groups of steps)"""
    __tablename__ = "onboarding_phases"
    
    id = Column(Integer, primary_key=True)
    cabinet_id = Column(Integer, ForeignKey("cabinets.id"))
    
    # Phase definition
    phase_key = Column(String(50))  # formation, production, mise_en_service
    phase_label = Column(String(100))
    
    # Status
    status = Column(String(20), default="todo")
    progress = Column(Integer, default=0)
    
    # Dates
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Default onboarding workflow templates
ONBOARDING_TEMPLATE = {
    "formation": {
        "label": "Formation",
        "steps": [
            {"key": "training_rgpd", "label": "Formation RGPD", "category": "training"},
            {"key": "training_cias", "label": "Formation IAS/CIF", "category": "training"},
            {"key": "training_tools", "label": "Formation outils", "category": "training"},
            {"key": "training_compliance", "label": "Formation conformité", "category": "training"},
        ]
    },
    "production": {
        "label": "Production",
        "steps": [
            {"key": "docs_orias", "label": "Documents ORIAS", "category": "docs"},
            {"key": "docs_rcp", "label": "RCP Assurance", "category": "docs"},
            {"key": "docs_rgpd", "label": "Policy RGPD", "category": "docs"},
            {"key": "docs_reclamations", "label": "Procédure réclamations", "category": "docs"},
            {"key": "docs_der", "label": "Document ER", "category": "docs"},
            {"key": "docs_lm", "label": "Lettre de mission", "category": "docs"},
        ]
    },
    "mise_en_service": {
        "label": "Mise en service",
        "steps": [
            {"key": "production_creation", "label": "Création production", "category": "production"},
            {"key": "page_creation", "label": "Création page cabinet", "category": "production"},
            {"key": "user_creation", "label": "Création utilisateur", "category": "production"},
            {"key": "email_setup", "label": "Setup email pro", "category": "production"},
            {"key": "calendar_setup", "label": "Setup calendrier", "category": "production"},
        ]
    }
}


def create_onboarding_for_cabinet(cabinet_id: int):
    """Create onboarding workflow for a new cabinet"""
    db = SessionLocal()
    
    try:
        # Check if already exists
        existing = db.query(OnboardingStep).filter(
            OnboardingStep.cabinet_id == cabinet_id
        ).first()
        
        if existing:
            return {"message": "Onboarding already exists"}
        
        # Create phases and steps
        sort_order = 0
        for phase_key, phase_data in ONBOARDING_TEMPLATE.items():
            # Create phase
            phase = OnboardingPhase(
                cabinet_id=cabinet_id,
                phase_key=phase_key,
                phase_label=phase_data["label"]
            )
            db.add(phase)
            db.flush()
            
            # Create steps
            for step_data in phase_data["steps"]:
                step = OnboardingStep(
                    cabinet_id=cabinet_id,
                    step_key=step_data["key"],
                    step_label=step_data["label"],
                    step_category=step_data["category"],
                    sort_order=sort_order
                )
                db.add(step)
                sort_order += 1
        
        db.commit()
        return {"message": "Onboarding created", "cabinet_id": cabinet_id}
    
    finally:
        db.close()


def get_onboarding_status(cabinet_id: int):
    """Get onboarding status for a cabinet"""
    db = SessionLocal()
    
    try:
        # Get phases with steps
        phases = db.query(OnboardingPhase).filter(
            OnboardingPhase.cabinet_id == cabinet_id
        ).order_by(OnboardingPhase.id).all()
        
        result = {
            "cabinet_id": cabinet_id,
            "phases": []
        }
        
        total_steps = 0
        completed_steps = 0
        
        for phase in phases:
            steps = db.query(OnboardingStep).filter(
                OnboardingStep.cabinet_id == cabinet_id,
                OnboardingStep.step_key.in_([s["key"] for s in ONBOARDING_TEMPLATE.get(phase.phase_key, {}).get("steps", [])])
            ).all()
            
            phase_steps = []
            for step in steps:
                phase_steps.append({
                    "id": step.id,
                    "key": step.step_key,
                    "label": step.step_label,
                    "status": step.status,
                    "progress": step.progress,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None
                })
                total_steps += 1
                if step.status == "done":
                    completed_steps += 1
            
            # Calculate phase progress
            if phase_steps:
                phase_progress = sum(s["progress"] for s in phase_steps) // len(phase_steps)
            else:
                phase_progress = 0
            
            result["phases"].append({
                "key": phase.phase_key,
                "label": phase.phase_label,
                "status": phase.status,
                "progress": phase_progress,
                "steps": phase_steps
            })
        
        # Overall progress
        result["total_progress"] = (completed_steps * 100 // total_steps) if total_steps > 0 else 0
        result["completed_steps"] = completed_steps
        result["total_steps"] = total_steps
        
        return result
    
    finally:
        db.close()


def update_step_status(cabinet_id: int, step_key: str, status: str, progress: int = None, notes: str = None):
    """Update step status"""
    db = SessionLocal()
    
    try:
        step = db.query(OnboardingStep).filter(
            OnboardingStep.cabinet_id == cabinet_id,
            OnboardingStep.step_key == step_key
        ).first()
        
        if not step:
            return {"error": "Step not found"}
        
        step.status = status
        if progress is not None:
            step.progress = progress
        if notes:
            step.notes = notes
        
        if status == "done" and not step.completed_at:
            step.completed_at = datetime.utcnow()
        
        db.commit()
        
        # Update phase status
        _update_phase_status(db, cabinet_id, step.step_category)
        
        return {"message": "Step updated", "step_id": step.id}
    
    finally:
        db.close()


def _update_phase_status(db, cabinet_id: int, category: str):
    """Update phase status based on steps"""
    # Map category to phase
    category_to_phase = {
        "training": "formation",
        "docs": "production", 
        "production": "mise_en_service"
    }
    
    phase_key = category_to_phase.get(category)
    if not phase_key:
        return
    
    phase = db.query(OnboardingPhase).filter(
        OnboardingPhase.cabinet_id == cabinet_id,
        OnboardingPhase.phase_key == phase_key
    ).first()
    
    if not phase:
        return
    
    # Get all steps for this phase
    steps = db.query(OnboardingStep).filter(
        OnboardingStep.cabinet_id == cabinet_id,
        OnboardingStep.step_category == category
    ).all()
    
    if not steps:
        return
    
    # Calculate phase progress
    total_progress = sum(s.progress for s in steps) // len(steps)
    phase.progress = total_progress
    
    # Update status
    statuses = [s.status for s in steps]
    if all(s == "done" for s in statuses):
        phase.status = "done"
    elif any(s == "in_progress" for s in statuses):
        phase.status = "in_progress"
    else:
        phase.status = "todo"
    
    db.commit()