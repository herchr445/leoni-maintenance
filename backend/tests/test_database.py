# test_database.py — Test de la vraie dépendance get_db()
# Pourquoi ce fichier : dans test_main.py, get_db est remplacée par la base de test
# (conftest.py), donc le code réel de get_db() ne s'exécute jamais là-bas.
# Ce test l'appelle directement pour vérifier qu'elle fournit une session
# utilisable ET qu'elle la ferme bien ensuite (bloc finally).

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database import engine_options, get_database_url, get_db


def test_get_db_yields_working_session_and_closes_it():
    """
    get_db() est un générateur : next() exécute le code jusqu'au yield
    et renvoie la session ; close() reprend l'exécution et déclenche le finally.
    (DATABASE_PATH=":memory:" est fixé par conftest.py → aucun fichier créé.)
    """
    gen = get_db()
    db = next(gen)

    # La session est bien une session SQLAlchemy, capable d'exécuter une requête
    assert isinstance(db, Session)
    assert db.execute(text("SELECT 1")).scalar() == 1

    # Ferme le générateur → exécute le bloc finally de get_db() → db.close()
    gen.close()


# --- Choix de l'URL de connexion (get_database_url) ---
# monkeypatch modifie les variables d'environnement pour le test seulement,
# puis les restaure automatiquement.

def test_database_url_takes_priority_when_set(monkeypatch):
    """DATABASE_URL définie → utilisée telle quelle (cas Kubernetes / compose)."""
    # URL volontairement SANS utilisateur ni mot de passe : le test ne vérifie
    # que le choix de l'URL, aucun identifiant n'a sa place dans le code.
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://db:5432/leoni")
    monkeypatch.setenv("DATABASE_PATH", "/data/ignored.db")  # doit être ignorée

    assert get_database_url() == "postgresql+psycopg://db:5432/leoni"


def test_database_url_falls_back_to_sqlite_database_path(monkeypatch):
    """Pas de DATABASE_URL → SQLite sur DATABASE_PATH (cas déploiement Docker Desktop)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_PATH", "/data/leoni_maintenance.db")

    assert get_database_url() == "sqlite:////data/leoni_maintenance.db"


def test_database_url_default_is_local_sqlite_file(monkeypatch):
    """Aucune variable → fichier SQLite local par défaut (cas développement)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_PATH", raising=False)

    assert get_database_url() == "sqlite:///./leoni_maintenance.db"


# --- Options du moteur selon le type de base (engine_options) ---

def test_engine_options_sqlite_disables_same_thread_check():
    """SQLite → check_same_thread=False, et rien de spécifique à PostgreSQL."""
    assert engine_options("sqlite:///./leoni_maintenance.db") == {
        "connect_args": {"check_same_thread": False}
    }


def test_engine_options_postgresql_uses_pre_ping_and_psycopg_driver():
    """
    PostgreSQL → pool_pre_ping=True et SURTOUT pas check_same_thread.
    create_engine() ne se connecte pas encore : on vérifie seulement que le
    driver psycopg est bien installé (sinon ImportError ici → CI en échec
    si psycopg manquait dans requirements.txt).
    """
    url = "postgresql+psycopg://localhost:5432/leoni"  # sans identifiants (aucune connexion)
    options = engine_options(url)

    assert options == {"pool_pre_ping": True}
    pg_engine = create_engine(url, **options)
    assert pg_engine.dialect.driver == "psycopg"
    pg_engine.dispose()
