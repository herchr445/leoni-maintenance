# Dockerfile — Image Docker du backend FastAPI
# Objectif : empaqueter l'API dans un conteneur autonome, reproductible
# sur n'importe quelle machine (ton PC, un serveur Leoni, Azure...).

# Image de base légère : Python 3.13 sans les outils inutiles
# (moins de taille = moins de surface d'attaque pour les scans de sécurité)
FROM python:3.13-slim

# Dossier de travail à l'intérieur du conteneur
WORKDIR /app

# On copie D'ABORD requirements.txt seul (pas tout le code).
# Astuce de cache Docker : tant que ce fichier ne change pas,
# Docker réutilise la couche d'installation des dépendances
# au lieu de tout réinstaller à chaque build.
COPY requirements.txt .

# Installe les dépendances Python
# --no-cache-dir : évite de stocker le cache pip dans l'image (taille réduite)
RUN pip install --no-cache-dir -r requirements.txt

# Copie maintenant tout le reste du code de l'application
COPY app/ ./app/

# Documente que le conteneur écoute sur le port 8000
# (n'ouvre pas réellement le port, c'est juste une info/convention)
EXPOSE 8000

# Commande de démarrage : lance le serveur en mode production
# --host 0.0.0.0 : nécessaire pour que le conteneur accepte les connexions
# venant de l'extérieur (pas juste "localhost" à l'intérieur du conteneur)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]