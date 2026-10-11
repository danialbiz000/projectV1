# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 — compile better-sqlite3 native addon
# ──────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
RUN apk add --no-cache python3 make g++
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 — runtime image (slim, no build tools)
# ──────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine
RUN apk add --no-cache tini
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY public      ./public
COPY server.js   package.json ./

# Persistent data directory — mount a volume here in production
VOLUME /data

ENV NEXUS_DATA_DIR=/data \
    NODE_ENV=production \
    PORT=3000

EXPOSE 3000

# tini reaps zombies and forwards signals correctly
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "server.js"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health',r=>process.exit(r.statusCode===200?0:1))"
