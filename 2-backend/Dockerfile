# Contexte de build : racine du dépôt
FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/backend:/srv/connecteurs
COPY 2-backend/requirements.txt /srv/backend/requirements.txt
# Certificat d'autorité optionnel (proxy d'entreprise) : docker build --secret id=ca,src=ca.crt
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi; \
    pip install --no-cache-dir -r /srv/backend/requirements.txt
COPY 2-backend/ /srv/backend/
COPY 3-connecteurs-deploiement/connecteurs/ /srv/connecteurs/
WORKDIR /srv/backend
EXPOSE 8000
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-w", "2", "-b", "0.0.0.0:8000", "--timeout", "120"]
