# Contexte de build : racine du dépôt
FROM node:22-alpine AS construction
WORKDIR /app
COPY 1-frontend/package.json 1-frontend/package-lock.json ./
RUN --mount=type=secret,id=ca,required=false \
    if [ -f /run/secrets/ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/ca; fi; \
    npm ci --no-audit --no-fund
COPY 1-frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=construction /app/dist /usr/share/nginx/html
