# schemas.py — Schémas Pydantic pour la validation des données API
# Objectif : définir précisément ce qu'un client peut envoyer (entrée)
# et ce que l'API retourne (sortie), avec validation automatique par FastAPI.

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models import TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    """
    Données attendues pour CRÉER un nouveau ticket.
    Le client ne fournit que les infos "métier" — le serveur se charge
    du reste (id, status par défaut, timestamps).
    """
    machine_name: str
    description: str
    priority: TicketPriority = TicketPriority.MEDIUM  # valeur par défaut si non précisé
    assigned_to: Optional[str] = None  # optionnel : peut être laissé vide à la création


class TicketUpdate(BaseModel):
    """
    Données attendues pour MODIFIER un ticket existant.
    Tous les champs sont optionnels : le client n'envoie que ce qu'il veut changer.
    """
    machine_name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TicketPriority] = None
    status: Optional[TicketStatus] = None
    assigned_to: Optional[str] = None


class TicketResponse(BaseModel):
    """
    Structure complète renvoyée par l'API après une requête
    (création, lecture, mise à jour). Inclut tous les champs,
    y compris ceux gérés automatiquement par le serveur.
    """
    id: int
    machine_name: str
    description: str
    priority: TicketPriority
    status: TicketStatus
    assigned_to: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Permet à Pydantic de lire directement un objet SQLAlchemy
    # (model_config, syntaxe Pydantic v2) au lieu d'un simple dict.
    model_config = ConfigDict(from_attributes=True) 