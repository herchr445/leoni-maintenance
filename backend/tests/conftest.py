# conftest.py — Configuration partagée des tests (chargée automatiquement par pytest)
# Objectif : chaque test tourne sur une base SQLite EN MÉMOIRE, vide au départ,
# au lieu du fichier de dev backend/leoni_maintenance.db. Plus aucune donnée
# ne "fuit" d'un test à l'autre ni d'une exécution à l'autre.

import os

# IMPORTANT : à définir AVANT d'importer l'application.
# main.py exécute Base.metadata.create_all() dès son import : sans cette ligne,
# le simple import de l'app recréerait le fichier leoni_maintenance.db.
# ":memory:" donne aussi au moteur de l'app une base en mémoire → aucun fichier.
# On écrase volontairement toute valeur existante : les tests ne doivent
# jamais toucher une vraie base, même si DATABASE_PATH est défini dans le shell.
os.environ["DATABASE_PATH"] = ":memory:"
# Même logique pour PostgreSQL : si DATABASE_URL était définie dans le shell,
# l'app s'y connecterait. On la retire pour garantir SQLite en mémoire.
os.environ.pop("DATABASE_URL", None)

# Les imports ci-dessous sont volontairement placés APRÈS la variable d'env.
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app  # importe aussi models → la table "tickets" est connue de Base

# Moteur dédié aux tests :
# - "sqlite://" (sans chemin) = base en mémoire, rien sur le disque.
# - StaticPool : une base en mémoire n'existe QUE dans la connexion qui l'a créée.
#   StaticPool force toutes les sessions à réutiliser cette même connexion,
#   sinon chaque nouvelle session verrait une base vide, sans tables.
# - check_same_thread=False : TestClient exécute l'app dans un autre thread,
#   ce que SQLite interdit par défaut.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Fabrique de sessions liée au moteur de test (mêmes options que database.py)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """
    Remplaçant de get_db() pendant les tests : même logique (ouvrir une session,
    la fournir à la route, la fermer quoi qu'il arrive), mais sur la base de test.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def isolated_db():
    """
    Fixture exécutée automatiquement autour de CHAQUE test (autouse=True) :
    1. crée les tables dans la base de test (vide) ;
    2. redirige la dépendance get_db de FastAPI vers la base de test ;
    3. laisse le test s'exécuter (yield) ;
    4. nettoie : retire la redirection et supprime les tables,
       pour que le test suivant reparte d'une base vide.
    """
    Base.metadata.create_all(bind=test_engine)
    # dependency_overrides : mécanisme officiel FastAPI pour remplacer une
    # dépendance sans modifier le code de l'application.
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
