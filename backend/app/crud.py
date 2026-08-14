# crud.py — Opérations de base de données (Create, Read, Update, Delete)
# Objectif : centraliser toute la logique d'accès aux données,
# séparée de la logique HTTP (qui vit dans main.py).

from sqlalchemy.orm import Session

from app import models, schemas


def create_ticket(db: Session, ticket: schemas.TicketCreate) -> models.Ticket:
    """
    Crée un nouveau ticket en base de données.

    1. Convertit le schéma Pydantic (TicketCreate) en objet SQLAlchemy (Ticket)
    2. L'ajoute à la session, commit (sauvegarde réelle), puis refresh
       (récupère les valeurs générées par la base : id, created_at...)
    """
    db_ticket = models.Ticket(**ticket.model_dump())  # model_dump() = convertit en dict
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

def get_tickets(db: Session, status: str | None = None, priority: str | None = None):
    """
    Récupère la liste des tickets, avec filtres optionnels.

    - Si aucun filtre n'est fourni, retourne tous les tickets
    - Si "status" est fourni, ne retourne que les tickets ayant ce statut
    - Si "priority" est fourni, ne retourne que les tickets ayant cette priorité
    - Les deux filtres peuvent être combinés
    """
    query = db.query(models.Ticket)

    if status:
        query = query.filter(models.Ticket.status == status)
    if priority:
        query = query.filter(models.Ticket.priority == priority)

    return query.order_by(models.Ticket.created_at.desc()).all()
def get_ticket(db: Session, ticket_id: int):
    """
    Récupère un ticket précis par son ID.
    Retourne None si aucun ticket avec cet ID n'existe
    (c'est à l'endpoint de décider quoi faire dans ce cas : 404).
    """
    return db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
def update_ticket(db: Session, ticket_id: int, ticket_update: schemas.TicketUpdate):
    """
    Met à jour un ticket existant avec les champs fournis.

    - Ne modifie que les champs réellement envoyés (grâce à TicketUpdate
      où tout est optionnel) — les champs non fournis restent inchangés
    - Retourne None si le ticket n'existe pas (l'endpoint gère le 404)
    """
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if db_ticket is None:
        return None

    # exclude_unset=True : ne récupère QUE les champs explicitement envoyés
    # par le client, pas ceux qui gardent leur valeur par défaut (None)
    update_data = ticket_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_ticket, field, value)

    db.commit()
    db.refresh(db_ticket)
    return db_ticket
def delete_ticket(db: Session, ticket_id: int) -> bool:
    """
    Supprime un ticket par son ID.
    Retourne True si supprimé avec succès, False si le ticket n'existait pas.
    """
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if db_ticket is None:
        return False

    db.delete(db_ticket)
    db.commit()
    return True