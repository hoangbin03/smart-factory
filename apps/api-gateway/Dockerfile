FROM node:20-alpine AS builder

WORKDIR /app

# Copy workspace config
COPY package.json ./
COPY packages/ ./packages/

COPY packages/shared-types/tsconfig.json ./packages/shared-types/
COPY packages/shared-events/tsconfig.json ./packages/shared-events/

# Copy service files
COPY apps/api-gateway/package.json ./apps/api-gateway/
COPY apps/api-gateway/tsconfig.json ./apps/api-gateway/
COPY apps/api-gateway/nest-cli.json ./apps/api-gateway/
COPY apps/api-gateway/src/ ./apps/api-gateway/src/

# Install dependencies
RUN apk add --no-cache python3 make g++
RUN npm install
RUN npm run build -w packages/shared-types --if-present
RUN npm run build -w packages/shared-events --if-present

# Build
WORKDIR /app/apps/api-gateway
RUN npm run build

# ─────────────────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules/ ./node_modules/
COPY --from=builder /app/packages/ ./packages/
COPY --from=builder /app/apps/api-gateway/package.json ./apps/api-gateway/
COPY --from=builder /app/apps/api-gateway/dist/ ./apps/api-gateway/dist/
WORKDIR /app/apps/api-gateway

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD wget -q --spider http://127.0.0.1:3000/api/health || exit 1

CMD ["node", "dist/main"]
