# test_main.py — Tests unitaires pour l'API principale
# Objectif : vérifier automatiquement que les endpoints répondent
# correctement, sans avoir besoin de lancer manuellement le serveur
# ni de tester à la main dans un navigateur.

from fastapi.testclient import TestClient  # Permet de simuler des requêtes HTTP
from app.main import app  # Importe l'application FastAPI qu'on veut tester

# Crée un client de test lié à notre app.
# Ce client se comporte comme un navigateur, mais tout se passe
# en mémoire — aucun vrai serveur réseau n'est démarré.
client = TestClient(app)


def test_health_check():
    """
    Vérifie que l'endpoint /health :
    1. Répond avec le code HTTP 200 (succès)
    2. Retourne bien le JSON {"status": "ok"}
    """
    response = client.get("/health")

    # assert = vérification. Si la condition est fausse, le test échoue.
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root():
    """
    Vérifie que la route racine "/" répond correctement.
    """
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "Leoni Maintenance API is running"}