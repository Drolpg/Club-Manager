# Compila o site e o entrega por um proxy leve, que também repassa /api para a API.
FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine

# Roda sem privilégios: usuário próprio e porta alta.
RUN adduser -D -u 10001 web && chown -R web /config /data
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
USER web
EXPOSE 8080
