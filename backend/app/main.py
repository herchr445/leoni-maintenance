# main.py — Point d'entrée du backend FastAPI
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import Optional
from app.database import engine, Base, get_db
from app import models, schemas, crud
from fastapi import HTTPException  # ← nouvel import à ajouter en haut


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Leoni Maintenance Ticketing System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """
    Endpoint de vérification de santé ("health check").
    """
    return {"status": "ok"}


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
from typing import Optional

@app.get("/api/tickets", response_model=list[schemas.TicketResponse])
def list_tickets(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Liste tous les tickets, avec filtres optionnels via query params.
    Exemples : /api/tickets?status=Open
               /api/tickets?priority=High
               /api/tickets?status=Open&priority=High
    """
    return crud.get_tickets(db=db, status=status, priority=priority)

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
    return None