# test_database.py — Test de la vraie dépendance get_db()
# Pourquoi ce fichier : dans test_main.py, get_db est remplacée par la base de test
# (conftest.py), donc le code réel de get_db() ne s'exécute jamais là-bas.
# Ce test l'appelle directement pour vérifier qu'elle fournit une session
# utilisable ET qu'elle la ferme bien ensuite (bloc finally).

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db


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
