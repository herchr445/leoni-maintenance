# database.py — Configuration de la connexion à la base de données
# Objectif : centraliser la config SQLite pour que tout le reste de l'app
# (models.py, futurs endpoints) puisse s'y connecter de façon cohérente.

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# En local (développement), la base reste dans le dossier backend/.
# En conteneur Docker, la variable DATABASE_PATH pointe vers /data/,
# un dossier séparé du code, pour que le volume Docker ne l'écrase pas.
DATABASE_PATH = os.getenv("DATABASE_PATH", "./leoni_maintenance.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Le "moteur" (engine) : gère la connexion technique à la base.
# check_same_thread=False est nécessaire spécifiquement pour SQLite
# avec FastAPI, car FastAPI peut gérer plusieurs requêtes dans des
# threads différents, ce que SQLite interdit par défaut.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# Fabrique de sessions : chaque requête API va créer sa propre
# session via SessionLocal(), l'utiliser, puis la fermer.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe de base dont tous nos modèles (Ticket, etc.) vont hériter.
Base = declarative_base()


def get_db():
    """
    Fonction utilitaire ("dependency" dans FastAPI) qui fournit
    une session de base de données à chaque requête, et s'assure
    qu'elle est bien fermée après usage, même en cas d'erreur.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()