# Leoni Maintenance Ticketing System

Application de gestion de tickets de maintenance industrielle, développée durant un stage chez **Leoni** (site de Sousse, Tunisie), accompagnée d'un **pipeline CI/CD complet** sur Azure DevOps : tests automatisés, contrôles qualité et sécurité, conteneurisation Docker, et déploiement continu avec redémarrage automatique.

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Stack technique](#stack-technique)
- [Architecture](#architecture)
- [Pipeline CI/CD](#pipeline-cicd)
- [Lancer le projet en local](#lancer-le-projet-en-local)
- [Tests](#tests)
- [Qualité et sécurité](#qualité-et-sécurité)

## Fonctionnalités

- Création, consultation, mise à jour et suppression de tickets de maintenance (CRUD complet)
- Suivi du statut (Open / InProgress / Resolved / Closed) et de la priorité (Low / Medium / High)
- Filtrage des tickets par statut et par priorité
- Tableau de bord statistique en temps réel (tickets ouverts, en cours, priorité haute, délai moyen de résolution)
- Interface visuelle sur mesure, inspirée des cartouches de plans techniques industriels

## Stack technique

| Composant | Technologies |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy, SQLite, Pydantic |
| Frontend | React, Vite, Tailwind CSS |
| Tests | pytest, pytest-cov |
| Conteneurisation | Docker (build multi-étapes pour le frontend) |
| CI/CD | Azure DevOps Pipelines, agent self-hosted |
| Qualité & Sécurité | Ruff · Bandit · Gitleaks · Trivy · SonarCloud |

## Architecture

\`\`\`
┌─────────────┐      HTTP/REST      ┌──────────────┐      SQLAlchemy      ┌──────────┐
│   React     │ ──────────────────▶ │   FastAPI    │ ───────────────────▶ │  SQLite  │
│  (nginx)    │                     │   (Python)   │                      │          │
└─────────────┘                     └──────────────┘                      └──────────┘
   Conteneur                           Conteneur                       Volume Docker
   Docker                              Docker                          (persistant)
\`\`\`

Les deux services sont conteneurisés indépendamment et communiquent via une API REST. La base de données est isolée dans un volume Docker dédié, séparé du code applicatif, garantissant la persistance des données entre chaque déploiement.

## Pipeline CI/CD

Le pipeline (\`azure-pipelines.yml\`) se déclenche automatiquement à chaque push et se déroule en deux phases :

**Intégration Continue (CI)**
1. Préparation de l'analyse SonarCloud
2. Installation des dépendances
3. Exécution des tests (couverture de code)
4. Analyse de qualité — Ruff
5. Scan de sécurité du code — Bandit
6. Détection de secrets — Gitleaks
7. Construction des images Docker (backend + frontend)
8. Scan des images — Trivy
9. Analyse et publication — SonarCloud

**Déploiement Continu (CD)** — déclenché uniquement si la CI réussit intégralement
1. Redéploiement du conteneur backend (avec vérification de santé)
2. Redéploiement du conteneur frontend (avec vérification de santé)

L'exécution s'effectue sur un **agent self-hosted**, configuré pour redémarrer automatiquement avec la machine, garantissant que l'application redevient opérationnelle sans intervention manuelle après un redémarrage du poste.

## Lancer le projet en local

### Prérequis
Python 3.13, Node.js 20+, Docker Desktop

### Backend
\`\`\`bash
cd backend
python -m venv venv
venv\\Scripts\\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
\`\`\`
L'API est accessible sur \`http://127.0.0.1:8000\`, documentation interactive sur \`/docs\`.

### Frontend
\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`
L'interface est accessible sur \`http://localhost:5173\`.

### Avec Docker
\`\`\`bash
docker build -t leoni-maintenance-backend ./backend
docker build -t leoni-maintenance-frontend ./frontend
docker run -d -p 8000:8000 leoni-maintenance-backend
docker run -d -p 8081:80 leoni-maintenance-frontend
\`\`\`

## Tests

\`\`\`bash
cd backend
pytest -v --cov=app --cov-report=term-missing
\`\`\`

20 tests automatisés (unitaires et d'intégration), 100% de couverture du code applicatif.

## Qualité et sécurité

| Outil | Rôle |
|---|---|
| **Ruff** | Analyse statique du code Python (style, conventions) |
| **Bandit** | Détection de failles de sécurité dans le code source |
| **Gitleaks** | Détection de secrets dans l'historique Git |
| **Trivy** | Scan des vulnérabilités connues (CVE) dans les images Docker |
| **SonarCloud** | Analyse de qualité globale et calcul du Quality Gate |

---

*Projet réalisé dans le cadre d'un stage — EPI Digital School, 4ème année Cloud & DevOps.*