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
def get_stats(db: Session):
    """
    Calcule les statistiques globales des tickets pour le dashboard.

    Retourne :
    - total_tickets : nombre total de tickets, tous statuts confondus
    - open_tickets : tickets encore au statut "Open"
    - in_progress_tickets : tickets au statut "InProgress"
    - high_priority_tickets : tickets de priorité "High", non fermés
      (un ticket High déjà Closed n'est plus une urgence active)
    - avg_resolution_time_hours : temps moyen entre création et clôture,
      calculé uniquement sur les tickets déjà "Closed"
    """
    all_tickets = db.query(models.Ticket).all()

    total = len(all_tickets)
    open_count = sum(1 for t in all_tickets if t.status == models.TicketStatus.OPEN)
    in_progress_count = sum(1 for t in all_tickets if t.status == models.TicketStatus.IN_PROGRESS)
    high_priority_active = sum(
        1 for t in all_tickets
        if t.priority == models.TicketPriority.HIGH
        and t.status != models.TicketStatus.CLOSED
    )

    closed_tickets = [t for t in all_tickets if t.status == models.TicketStatus.CLOSED]
    if closed_tickets:
        durations = [
            (t.updated_at - t.created_at).total_seconds() / 3600
            for t in closed_tickets
        ]
        avg_resolution_hours = round(sum(durations) / len(durations), 1)
    else:
        avg_resolution_hours = None

    return {
        "total_tickets": total,
        "open_tickets": open_count,
        "in_progress_tickets": in_progress_count,
        "high_priority_tickets": high_priority_active,
        "avg_resolution_time_hours": avg_resolution_hours,
    }