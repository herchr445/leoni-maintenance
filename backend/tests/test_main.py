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
def test_create_ticket():
    """
    Vérifie que POST /api/tickets crée bien un ticket avec :
    - le bon code HTTP (201 Created)
    - les données envoyées correctement reflétées dans la réponse
    - un statut "Open" appliqué automatiquement par défaut
    - un id généré automatiquement
    """
    response = client.post("/api/tickets", json={
        "machine_name": "Machine A",
        "description": "Panne moteur",
        "priority": "High"
    })

    assert response.status_code == 201
    data = response.json()
    assert data["machine_name"] == "Machine A"
    assert data["description"] == "Panne moteur"
    assert data["priority"] == "High"
    assert data["status"] == "Open"  # valeur par défaut
    assert "id" in data
    assert "created_at" in data   
def test_list_tickets():
    """
    Vérifie que GET /api/tickets retourne bien une liste,
    contenant au moins le ticket créé dans le test précédent.
    """
    response = client.get("/api/tickets")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)  # la réponse doit être une liste
    assert len(data) >= 1  # au moins 1 ticket (celui créé avant)


def test_list_tickets_with_status_filter():
    """
    Vérifie que le filtre par statut fonctionne :
    tous les tickets retournés doivent avoir le statut demandé.
    """
    response = client.get("/api/tickets?status=Open")

    assert response.status_code == 200
    data = response.json()
    for ticket in data:
        assert ticket["status"] == "Open"    
def test_create_ticket_missing_required_field():
    """
    Cas d'erreur : machine_name est obligatoire mais absent.
    FastAPI/Pydantic doit rejeter automatiquement avec 422.
    """
    response = client.post("/api/tickets", json={
        "description": "Panne sans machine"
        # machine_name manquant volontairement
    })
    assert response.status_code == 422


def test_create_ticket_invalid_priority():
    """
    Cas d'erreur : priority doit être Low/Medium/High uniquement.
    Une valeur hors de cette liste doit être rejetée.
    """
    response = client.post("/api/tickets", json={
        "machine_name": "Machine B",
        "description": "Test priorité invalide",
        "priority": "Urgentissime"  # n'existe pas dans l'Enum
    })
    assert response.status_code == 422


def test_create_ticket_default_priority():
    """
    Cas limite : si priority n'est pas fourni, la valeur par défaut
    (Medium) doit être appliquée automatiquement.
    """
    response = client.post("/api/tickets", json={
        "machine_name": "Machine C",
        "description": "Sans priorité précisée"
        # priority absent volontairement
    })
    assert response.status_code == 201
    assert response.json()["priority"] == "Medium"


def test_list_tickets_with_nonexistent_status_filter():
    """
    Cas limite : filtrer par un statut qui n'existe dans aucun ticket
    doit retourner une liste vide, pas une erreur.
    """
    response = client.get("/api/tickets?status=Closed")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Tous les tickets créés dans nos tests précédents sont "Open",
    # donc filtrer par "Closed" doit retourner une liste vide
    assert len(data) == 0


def test_list_tickets_with_priority_filter():
    """
    Vérifie spécifiquement que le filtre priority fonctionne
    (pas seulement status, qu'on avait déjà testé).
    """
    response = client.get("/api/tickets?priority=High")

    assert response.status_code == 200
    data = response.json()
    for ticket in data:
        assert ticket["priority"] == "High"        
def test_get_ticket_found():
    """
    Cas normal : récupérer un ticket existant par son ID.
    """
    # On crée d'abord un ticket pour être sûr qu'il existe
    create_response = client.post("/api/tickets", json={
        "machine_name": "Machine D",
        "description": "Test get by id",
        "priority": "Low"
    })
    ticket_id = create_response.json()["id"]

    response = client.get(f"/api/tickets/{ticket_id}")

    assert response.status_code == 200
    assert response.json()["id"] == ticket_id
    assert response.json()["machine_name"] == "Machine D"


def test_get_ticket_not_found():
    """
    Cas d'erreur : demander un ticket avec un ID qui n'existe pas
    doit retourner 404, pas planter ni retourner une réponse vide.
    """
    response = client.get("/api/tickets/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"        
def test_update_ticket_success():
    """
    Cas normal : modifier partiellement un ticket existant.
    Vérifie que les champs modifiés changent, et que les autres
    champs non envoyés restent inchangés (exclude_unset).
    """
    create_response = client.post("/api/tickets", json={
        "machine_name": "Machine E",
        "description": "Description originale",
        "priority": "Low"
    })
    ticket_id = create_response.json()["id"]

    response = client.patch(f"/api/tickets/{ticket_id}", json={
        "status": "InProgress",
        "assigned_to": "Karim"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "InProgress"
    assert data["assigned_to"] == "Karim"
    # Vérifie que les champs NON envoyés sont restés inchangés
    assert data["machine_name"] == "Machine E"
    assert data["description"] == "Description originale"


def test_update_ticket_not_found():
    """
    Cas d'erreur : modifier un ticket qui n'existe pas doit
    retourner 404, pas planter.
    """
    response = client.patch("/api/tickets/999999", json={
        "status": "Closed"
    })

    assert response.status_code == 404


def test_update_ticket_partial_single_field():
    """
    Cas limite : modifier UN SEUL champ (ex: juste le statut)
    ne doit affecter que ce champ, rien d'autre.
    """
    create_response = client.post("/api/tickets", json={
        "machine_name": "Machine F",
        "description": "Test single field update",
        "priority": "High",
        "assigned_to": "Sami"
    })
    ticket_id = create_response.json()["id"]

    response = client.patch(f"/api/tickets/{ticket_id}", json={
        "status": "Resolved"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Resolved"
    assert data["assigned_to"] == "Sami"  # doit rester inchangé
    assert data["priority"] == "High"  # doit rester inchangé    

def test_delete_ticket_success():
    """
    Cas normal : supprimer un ticket existant.
    Vérifie le code 204, puis vérifie que le ticket
    n'est vraiment plus récupérable ensuite (double vérification).
    """
    create_response = client.post("/api/tickets", json={
        "machine_name": "Machine G",
        "description": "À supprimer",
        "priority": "Low"
    })
    ticket_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/tickets/{ticket_id}")
    assert delete_response.status_code == 204

    # Double vérification : le ticket ne doit plus exister
    get_response = client.get(f"/api/tickets/{ticket_id}")
    assert get_response.status_code == 404


def test_delete_ticket_not_found():
    """
    Cas d'erreur : supprimer un ticket qui n'existe pas
    doit retourner 404, pas planter.
    """
    response = client.delete("/api/tickets/999999")

    assert response.status_code == 404    