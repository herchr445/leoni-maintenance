# main.py — Point d'entrée du backend FastAPI
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # Gère les autorisations cross-origin

app = FastAPI(title="Leoni Maintenance Ticketing System")

# Configuration CORS : autorise le frontend React (localhost:5173)
# à envoyer des requêtes vers ce backend (localhost:8000).
# En production, on remplacerait "*" ou cette liste par le vrai domaine autorisé,
# jamais une liste ouverte à tout le monde pour des raisons de sécurité.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Origine autorisée = notre frontend
    allow_credentials=True,
    allow_methods=["*"],  # Autorise GET, POST, PUT, DELETE...
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """
    Endpoint de vérification de santé ("health check").
    """
    return {"status": "ok"}


@app.get("/")
def root():
    """
    Route racine.
    """
    return {"message": "Leoni Maintenance API is running"}