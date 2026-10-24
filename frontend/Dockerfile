# Dockerfile — Image Docker du frontend React
# Build multi-étapes : compile React avec Node.js, puis sert les fichiers
# statiques générés via nginx — l'image finale ne contient pas Node.js.

# ===== ÉTAPE 1 : Build de l'application React =====
FROM node:20-slim AS build

WORKDIR /app

# Copie d'abord package.json seul (astuce de cache Docker,
# même logique que requirements.txt pour le backend)
COPY package*.json ./
RUN npm install

# URL de l'API, figée dans le JavaScript par Vite pendant "npm run build".
# - Valeur par défaut = celle du déploiement Azure (frontend :8081 → backend :8000),
#   donc le pipeline (docker build sans argument) produit exactement l'image d'avant.
# - Image Kubernetes : docker build --build-arg VITE_API_URL="" → URLs relatives (/api/...).
# ARG n'existe que pendant le build ; ENV la rend visible au processus "npm run build"
# (et une variable d'environnement est prioritaire sur les fichiers .env de Vite).
ARG VITE_API_URL=http://127.0.0.1:8000
ENV VITE_API_URL=$VITE_API_URL

# Copie le reste du code et lance le build
COPY . .
RUN npm run build

# ===== ÉTAPE 2 : Servir les fichiers statiques via nginx =====
FROM nginx:alpine

# Copie UNIQUEMENT le résultat du build (dossier dist/) depuis l'étape "build"
COPY --from=build /app/dist /usr/share/nginx/html

# nginx écoute par défaut sur le port 80
EXPOSE 80

# Lance nginx au premier plan (nécessaire pour Docker)
CMD ["nginx", "-g", "daemon off;"]