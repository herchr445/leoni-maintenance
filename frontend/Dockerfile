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

# ===== ÉTAPE 2 : Servir les fichiers statiques via nginx (NON-ROOT) =====
# nginx-unprivileged : variante officielle de nginx qui tourne avec l'utilisateur
# "nginx" (UID 101) au lieu de root. Conséquence : il écoute sur 8080, car un
# processus non-root ne peut pas ouvrir un port < 1024 (comme 80).
# Version ÉPINGLÉE (nginx 1.31.7, Alpine 3.24) et non le tag flottant "alpine",
# qui change d'image dans le temps : un même Dockerfile donnait des bases différentes.
FROM nginxinc/nginx-unprivileged:1.31.7-alpine3.24

# Correctif de sécurité : CVE-2026-111497 (CRITICAL) dans brotli-libs 1.2.0-r1,
# corrigée en 1.2.1-r0. L'image de base la plus récente contient encore 1.2.0-r1 ;
# le correctif est disponible dans les dépôts Alpine 3.24.
# root UNIQUEMENT le temps de ce RUN (apk doit écrire dans le système), puis retour
# à l'utilisateur non-root nginx (UID 101). On ne met à jour QUE le paquet vulnérable.
# À retirer quand une image de base nginx-unprivileged inclura brotli-libs >= 1.2.1-r0.
USER root
RUN apk upgrade --no-cache brotli-libs
USER 101

# Configuration du site : port 8080 + repli SPA (voir nginx.conf)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copie UNIQUEMENT le résultat du build (dossier dist/) depuis l'étape "build"
COPY --from=build /app/dist /usr/share/nginx/html

# nginx non-root écoute sur 8080 (le pipeline publie donc -p 8081:8080)
EXPOSE 8080

# Lance nginx au premier plan (nécessaire pour Docker)
CMD ["nginx", "-g", "daemon off;"]