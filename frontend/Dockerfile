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