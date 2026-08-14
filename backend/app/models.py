# models.py — Modèle SQLAlchemy représentant la table "tickets"
# Objectif : définir la structure exacte de la table en base de données,
# ainsi que les règles de validation au niveau du stockage (types, valeurs autorisées).

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Enum, DateTime
from app.database import Base


class TicketPriority(str, enum.Enum):
    """
    Enum = liste fermée de valeurs autorisées.
    Empêche d'enregistrer une priorité invalide (typo, valeur inventée).
    """
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class TicketStatus(str, enum.Enum):
    """
    Représente le cycle de vie d'un ticket.
    L'ordre logique attendu : OPEN -> IN_PROGRESS -> RESOLVED -> CLOSED
    (cette règle de transition sera appliquée plus tard, au niveau
    des endpoints — pas ici, ce fichier ne fait que définir la structure).
    """
    OPEN = "Open"
    IN_PROGRESS = "InProgress"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class Ticket(Base):
    """
    Représente un ticket de maintenance dans la base de données.
    Chaque instance de cette classe = une ligne dans la table "tickets".
    """
    __tablename__ = "tickets"  # Nom de la table réelle en base

    id = Column(Integer, primary_key=True, index=True)
    machine_name = Column(String, nullable=False)       # nullable=False = champ obligatoire
    description = Column(String, nullable=False)
    priority = Column(Enum(TicketPriority), nullable=False, default=TicketPriority.MEDIUM)
    status = Column(Enum(TicketStatus), nullable=False, default=TicketStatus.OPEN)
    assigned_to = Column(String, nullable=True)          # nullable=True = champ optionnel

    # Rempli automatiquement à la création du ticket
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # Mis à jour automatiquement à chaque modification du ticket
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )