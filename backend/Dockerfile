# Dockerfile — Image Docker du backend FastAPI
# Objectif : empaqueter l'API dans un conteneur autonome, reproductible
# sur n'importe quelle machine (ton PC, un serveur Leoni, Azure...).

# Image de base légère : Python 3.13 sans les outils inutiles
# (moins de taille = moins de surface d'attaque pour les scans de sécurité)
FROM python:3.13-slim

# Utilisateur système NON-ROOT avec un UID/GID FIXE (10001) :
# - si l'app était compromise, l'attaquant n'aurait pas les droits root ;
# - un numéro fixe permet de faire correspondre exactement le securityContext
#   Kubernetes (runAsUser: 10001) et le propriétaire du volume de données.
# --no-create-home / nologin : compte de service, pas de dossier perso ni de shell.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid 10001 --no-create-home \
       --shell /usr/sbin/nologin app

# Dossier de travail à l'intérieur du conteneur
WORKDIR /app

# On copie D'ABORD requirements.txt seul (pas tout le code).
# Astuce de cache Docker : tant que ce fichier ne change pas,
# Docker réutilise la couche d'installation des dépendances
# au lieu de tout réinstaller à chaque build.
COPY requirements.txt .

# Installe les dépendances Python (encore en root : elles vont dans le système)
# --no-cache-dir : évite de stocker le cache pip dans l'image (taille réduite)
# --only-binary :all: : n'accepte QUE des wheels précompilées, jamais de
#   compilation depuis les sources (pas d'exécution de setup.py au build).
# --require-hashes : chaque fichier téléchargé doit correspondre à une empreinte
#   SHA-256 de requirements.txt (généré par pip-compile depuis requirements.in) ;
#   un paquet altéré ou substitué sur le dépôt est refusé.
# pip uninstall -y pip : pip ne sert qu'à cette installation, pas à l'exécution de
#   l'application. On le retire dans le MÊME RUN : ses fichiers ne sont alors
#   enregistrés dans aucune couche de l'image (un RUN séparé les masquerait
#   seulement). Cela supprime aussi les paquets qu'il embarque (pip/_vendor :
#   urllib3, msgpack, pkg_resources...), signalés par Trivy.
#   C'est la dernière étape qui utilise pip : aucune instruction suivante n'en a besoin.
RUN pip install --no-cache-dir --only-binary :all: --require-hashes -r requirements.txt \
    && pip uninstall -y pip

# Copie maintenant tout le reste du code de l'application.
# Le code reste propriété de root, en lecture seule pour l'utilisateur app :
# l'application ne peut pas modifier son propre code.
COPY app/ ./app/

# /data : SEUL dossier inscriptible par l'app (base SQLite du déploiement Docker Desktop).
# Quand un volume nommé NEUF est monté sur /data, Docker reprend ce propriétaire (10001).
# (Un volume DÉJÀ existant garde son propriétaire actuel → chown unique nécessaire.)
RUN mkdir -p /data && chown 10001:10001 /data

# Chemin SQLite par défaut dans /data : sans cela, l'app tenterait d'écrire
# ./leoni_maintenance.db dans /app, non inscriptible → plantage au démarrage.
# (Le pipeline passe déjà exactement cette valeur avec -e : aucun changement pour lui.)
ENV DATABASE_PATH=/data/leoni_maintenance.db

# À partir d'ici, tout s'exécute avec l'utilisateur non-root (UID:GID numériques,
# vérifiables par Kubernetes avec runAsNonRoot)
USER 10001:10001

# Documente que le conteneur écoute sur le port 8000
# (n'ouvre pas réellement le port, c'est juste une info/convention)
EXPOSE 8000

# Commande de démarrage : lance le serveur en mode production
# --host 0.0.0.0 : nécessaire pour que le conteneur accepte les connexions
# venant de l'extérieur (pas juste "localhost" à l'intérieur du conteneur)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]