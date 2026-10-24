# main.py — Point d'entrée du backend FastAPI

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Leoni Maintenance Ticketing System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Frontend en mode développement (npm run dev)
        "http://localhost:8081",  # Frontend conteneurisé (déploiement Docker)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """
    Endpoint de vérification de santé ("health check").
    Liveness pure : ne touche PAS la base. Répond tant que le processus vit
    (utilisé par le health check du pipeline et la livenessProbe Kubernetes).
    """
    return {"status": "ok"}


@app.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """
    Endpoint de disponibilité ("readiness") : l'API est-elle prête à servir ?
    Exécute un SELECT 1 sur la base :
    - succès → 200 {"status": "ready"} ;
    - base injoignable ou en erreur → 503, pour que Kubernetes retire le pod
      du trafic le temps que la base revienne (sans le redémarrer).
    """
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # SQLAlchemyError couvre toutes les erreurs de connexion/requête SQLAlchemy
        raise HTTPException(status_code=503, detail="Database not ready") from exc
    return {"status": "ready"}


@app.get("/")
def root():
    """
    Route racine.
    """
    return {"message": "Leoni Maintenance API is running"}


@app.post("/api/tickets", response_model=schemas.TicketResponse, status_code=201)
def create_ticket(ticket: schemas.TicketCreate, db: Session = Depends(get_db)):
    """
    Crée un nouveau ticket de maintenance.
    """
    return crud.create_ticket(db=db, ticket=ticket)


@app.get("/api/tickets", response_model=list[schemas.TicketResponse])
def list_tickets(
    status: str | None = None,
    priority: str | None = None,
    db: Session = Depends(get_db)
):
    """
    Liste tous les tickets, avec filtres optionnels via query params.
    """
    return crud.get_tickets(db=db, status=status, priority=priority)


@app.get("/api/stats", response_model=schemas.StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """
    Retourne les statistiques globales des tickets pour le dashboard
    (total, ouverts, en cours, priorité haute, temps moyen de résolution).

    IMPORTANT : cette route doit être définie AVANT /api/tickets/{ticket_id},
    sinon FastAPI tenterait d'interpréter "stats" comme une valeur de
    {ticket_id} (qui attend un entier), causant une erreur de validation.
    """
    return crud.get_stats(db=db)


@app.get("/api/tickets/{ticket_id}", response_model=schemas.TicketResponse)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """
    Récupère un ticket précis par son ID.
    Retourne 404 si le ticket n'existe pas.
    """
    db_ticket = crud.get_ticket(db=db, ticket_id=ticket_id)
    if db_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return db_ticket


@app.patch("/api/tickets/{ticket_id}", response_model=schemas.TicketResponse)
def update_ticket(ticket_id: int, ticket_update: schemas.TicketUpdate, db: Session = Depends(get_db)):
    """
    Met à jour un ticket existant (statut, assignation, etc.).
    Retourne 404 si le ticket n'existe pas.
    """
    db_ticket = crud.update_ticket(db=db, ticket_id=ticket_id, ticket_update=ticket_update)
    if db_ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return db_ticket


@app.delete("/api/tickets/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """
    Supprime un ticket par son ID.
    Retourne 204 (No Content) si succès, 404 si le ticket n'existe pas.
    """
    success = crud.delete_ticket(db=db, ticket_id=ticket_id)
    if not success:
        raise HTTPException(status_code=404, detail="Ticket not found")