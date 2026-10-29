# database.py — Configuration de la connexion à la base de données
# Objectif : centraliser la config de la base pour que tout le reste de l'app
# (models.py, endpoints) puisse s'y connecter de façon cohérente.
# Deux bases possibles :
# - PostgreSQL si la variable DATABASE_URL est définie (Kubernetes, docker compose) ;
# - SQLite sinon (comportement historique : tests, pipeline Azure, Docker Desktop).

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker


def get_database_url() -> str:
    """
    Choisit l'URL de connexion à partir des variables d'environnement.

    - DATABASE_URL définie → utilisée telle quelle. Format attendu :
      schéma "postgresql+psycopg", puis utilisateur, mot de passe, hôte, port
      et nom de la base. Le mot de passe n'est JAMAIS écrit dans le code : la
      variable est fournie par l'environnement (fichier .env local ignoré par
      Git pour docker compose, Secret Kubernetes dans le cluster).
    - Sinon → SQLite sur le fichier DATABASE_PATH :
      en local, la base reste dans backend/ (./leoni_maintenance.db) ;
      en conteneur Docker, DATABASE_PATH pointe vers /data/, un dossier
      séparé du code, pour que le volume Docker ne l'écrase pas.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    database_path = os.getenv("DATABASE_PATH", "./leoni_maintenance.db")
    return f"sqlite:///{database_path}"


def engine_options(database_url: str) -> dict:
    """
    Options du moteur SQLAlchemy adaptées au type de base.

    - SQLite : check_same_thread=False est nécessaire car FastAPI peut traiter
      les requêtes dans des threads différents, ce que SQLite interdit par défaut.
      (Cet argument est propre à SQLite : psycopg le refuse et planterait.)
    - PostgreSQL : pool_pre_ping=True teste chaque connexion du pool avant de
      l'utiliser → l'app survit à un redémarrage de PostgreSQL au lieu de
      renvoyer des erreurs sur des connexions mortes.
    """
    # make_url().get_backend_name() lit le type de base dans l'URL ("sqlite", "postgresql"...)
    if make_url(database_url).get_backend_name() == "sqlite":
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


SQLALCHEMY_DATABASE_URL = get_database_url()

# Le "moteur" (engine) : gère la connexion technique à la base.
engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_options(SQLALCHEMY_DATABASE_URL))

# Fabrique de sessions : chaque requête API va créer sa propre
# session via SessionLocal(), l'utiliser, puis la fermer.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Classe de base dont tous nos modèles (Ticket, etc.) vont hériter.
Base = declarative_base()

# Identifiant du verrou consultatif ("advisory lock") PostgreSQL qui protège la
# création du schéma. Valeur arbitraire mais FIXE : toutes les répliques du backend
# doivent demander le même verrou pour s'attendre mutuellement.
SCHEMA_LOCK_ID = 7_430_201


def create_schema(target_engine) -> None:
    """
    Crée les tables manquantes (et, sous PostgreSQL, les types ENUM).

    - SQLite (tests, développement local, déploiement Docker Desktop) : simple
      create_all(), comportement inchangé (une seule instance de l'application).
    - PostgreSQL (Kubernetes, plusieurs répliques) : create_all() sous verrou
      consultatif. Sans lui, deux répliques démarrant au même instant sur une base
      vide pouvaient créer les mêmes tables en parallèle ; l'une échouait et
      redémarrait. Ici, la première prend le verrou et crée le schéma dans UNE
      transaction ; les autres attendent, puis constatent que les tables existent
      (create_all vérifie avant de créer) et ne font rien.
      pg_advisory_xact_lock est lié à la transaction : il est libéré
      automatiquement au commit (ou si le processus s'arrête), jamais oublié.
    """
    if target_engine.dialect.name != "postgresql":
        Base.metadata.create_all(bind=target_engine)
        return
    # begin() : transaction validée (commit) à la sortie du bloc → libère le verrou
    with target_engine.begin() as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": SCHEMA_LOCK_ID}
        )
        # Même connexion, donc même transaction, que le verrou
        Base.metadata.create_all(bind=connection)


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