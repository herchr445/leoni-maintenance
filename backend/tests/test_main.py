# test_main.py — Tests unitaires pour l'API principale
# Objectif : vérifier automatiquement que les endpoints répondent
# correctement, sans avoir besoin de lancer manuellement le serveur
# ni de tester à la main dans un navigateur.

from fastapi.testclient import TestClient  # Permet de simuler des requêtes HTTP
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
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


def test_ready_when_database_ok():
    """
    Cas normal : la base répond au SELECT 1 → /ready renvoie 200 "ready".
    """
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_503_when_database_unreachable(tmp_path):
    """
    Cas d'erreur : base injoignable → /ready doit renvoyer 503 (pas planter en 500).
    Panne RÉELLE, sans mock : un fichier SQLite dans un dossier qui n'existe pas
    ne peut pas être ouvert → SQLAlchemy lève une OperationalError.
    """
    missing_db = (tmp_path / "dossier_inexistant" / "leoni.db").as_posix()
    broken_engine = create_engine(f"sqlite:///{missing_db}")
    BrokenSession = sessionmaker(bind=broken_engine)

    def broken_get_db():
        # Même forme que get_db(), mais sur la base injoignable
        db = BrokenSession()
        try:
            yield db
        finally:
            db.close()

    # Remplace la base de test de conftest.py pour CE test uniquement
    # (la fixture isolated_db vide dependency_overrides après chaque test)
    app.dependency_overrides[get_db] = broken_get_db

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "Database not ready"
    broken_engine.dispose()
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
    Vérifie que GET /api/tickets retourne bien une liste
    contenant le ticket créé dans CE test (la base est vide au départ,
    chaque test étant isolé par la fixture de conftest.py).
    """
    client.post("/api/tickets", json={
        "machine_name": "Machine Liste",
        "description": "Ticket pour le test de liste",
        "priority": "Low"
    })

    response = client.get("/api/tickets")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)  # la réponse doit être une liste
    assert len(data) == 1  # exactement le ticket créé ci-dessus
    assert data[0]["machine_name"] == "Machine Liste"


def test_list_tickets_with_status_filter():
    """
    Vérifie que le filtre par statut fonctionne :
    seuls les tickets ayant le statut demandé sont retournés, et tous le sont.
    """
    # Prépare 3 tickets (tous "Open" à la création), puis en passe
    # un en "InProgress" et un en "Closed" → statuts différents.
    ids = []
    for name in ("Machine Open", "Machine InProgress", "Machine Closed"):
        created = client.post("/api/tickets", json={
            "machine_name": name,
            "description": "Test filtre statut",
            "priority": "Medium"
        })
        ids.append(created.json()["id"])
    client.patch(f"/api/tickets/{ids[1]}", json={"status": "InProgress"})
    client.patch(f"/api/tickets/{ids[2]}", json={"status": "Closed"})

    response = client.get("/api/tickets?status=Open")

    assert response.status_code == 200
    data = response.json()
    # Exactement 1 ticket : celui resté "Open" (les 2 autres sont exclus)
    assert len(data) == 1
    assert data[0]["id"] == ids[0]
    assert data[0]["status"] == "Open"
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
    Cas d'erreur : filtrer par un statut qui n'existe pas dans l'Enum
    (ex : "Foo") doit être rejeté avec 422 par la validation FastAPI,
    avant toute requête SQL — même comportement sur SQLite et PostgreSQL.
    """
    response = client.get("/api/tickets?status=Foo")

    assert response.status_code == 422


def test_list_tickets_with_valid_status_no_match():
    """
    Cas limite : un statut VALIDE mais porté par aucun ticket doit
    retourner une liste vide (200), pas une erreur.
    On crée d'abord un ticket "Open" pour que la base ne soit pas vide :
    la liste vide prouve alors que le filtre exclut bien ce ticket.
    """
    client.post("/api/tickets", json={
        "machine_name": "Machine Ouverte",
        "description": "Ticket resté Open",
        "priority": "Medium"
    })

    response = client.get("/api/tickets?status=Closed")

    assert response.status_code == 200
    assert response.json() == []


def test_list_tickets_with_invalid_priority_filter():
    """
    Cas d'erreur : même règle pour le filtre priority — une valeur hors
    de Low/Medium/High doit être rejetée avec 422.
    """
    response = client.get("/api/tickets?priority=Urgentissime")

    assert response.status_code == 422


def test_list_tickets_with_priority_filter():
    """
    Vérifie spécifiquement que le filtre priority fonctionne
    (pas seulement status, qu'on avait déjà testé) : seuls les tickets
    de la priorité demandée sont retournés, et tous le sont.
    """
    # Prépare 4 tickets de priorités différentes, dont 2 en "High"
    high_ids = set()
    for name, priority in (
        ("Machine High 1", "High"),
        ("Machine High 2", "High"),
        ("Machine Low", "Low"),
        ("Machine Medium", "Medium"),
    ):
        created = client.post("/api/tickets", json={
            "machine_name": name,
            "description": "Test filtre priorité",
            "priority": priority
        })
        if priority == "High":
            high_ids.add(created.json()["id"])

    response = client.get("/api/tickets?priority=High")

    assert response.status_code == 200
    data = response.json()
    # Exactement les 2 tickets "High", ni plus ni moins (Low et Medium exclus)
    assert len(data) == 2
    assert {ticket["id"] for ticket in data} == high_ids
    assert all(ticket["priority"] == "High" for ticket in data)
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
def test_get_stats_empty_or_with_data():
    """
    Vérifie que /api/stats retourne une réponse cohérente et bien formée,
    peu importe l'état actuel de la base (vide ou avec des tickets).
    """
    response = client.get("/api/stats")

    assert response.status_code == 200
    data = response.json()
    assert "total_tickets" in data
    assert "open_tickets" in data
    assert "in_progress_tickets" in data
    assert "high_priority_tickets" in data
    assert "avg_resolution_time_hours" in data
    assert isinstance(data["total_tickets"], int)
    assert data["total_tickets"] >= 0


def test_get_stats_reflects_created_ticket():
    """
    Vérifie que créer un ticket fait bien évoluer les statistiques
    (le total augmente, le ticket est compté dans "open" par défaut).
    """
    before = client.get("/api/stats").json()

    client.post("/api/tickets", json={
        "machine_name": "Machine Stats Test",
        "description": "Test pour vérifier les stats",
        "priority": "High"
    })

    after = client.get("/api/stats").json()

    assert after["total_tickets"] == before["total_tickets"] + 1
    assert after["open_tickets"] == before["open_tickets"] + 1
    assert after["high_priority_tickets"] == before["high_priority_tickets"] + 1


def test_get_stats_high_priority_excludes_closed():
    """
    Vérifie qu'un ticket High mais déjà Closed n'est PAS compté
    dans high_priority_tickets (ce n'est plus une urgence active).
    """
    create_response = client.post("/api/tickets", json={
        "machine_name": "Machine High Closed",
        "description": "Ticket High mais fermé",
        "priority": "High"
    })
    ticket_id = create_response.json()["id"]

    before = client.get("/api/stats").json()["high_priority_tickets"]

    client.patch(f"/api/tickets/{ticket_id}", json={"status": "Closed"})

    after = client.get("/api/stats").json()["high_priority_tickets"]

    assert after == before - 1
    