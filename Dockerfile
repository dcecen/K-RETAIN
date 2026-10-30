# K-Retain — image de déploiement interne (interface compilée + serveur de calcul).
# Construction : docker build -t retainwall .
# Lancement    : voir docs/INSTALLATION.md

# 1) Interface
FROM node:20.18.0-slim AS interface
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Serveur de calcul
FROM python:3.12.7-slim
WORKDIR /app
COPY backend/pyproject.toml backend/requirements.lock.txt backend/
# Mêmes versions que le poste de développement (backend/requirements.lock.txt, généré par pip freeze) :
# les résultats d'un logiciel de calcul ne doivent pas dépendre de la version de numpy ou scipy installée.
RUN pip install --no-cache-dir -c backend/requirements.lock.txt numpy scipy pydantic fastapi \
    "uvicorn[standard]" ruamel.yaml openpyxl python-multipart
COPY backend/sout backend/sout
COPY docs docs
COPY exemples exemples
COPY --from=interface /app/frontend/dist frontend/dist
ENV RETAINWALL_AUTH=1 \
    RETAINWALL_UTILISATEURS=/donnees/utilisateurs.json \
    PYTHONUNBUFFERED=1
VOLUME ["/donnees"]
WORKDIR /app/backend
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "sout.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
