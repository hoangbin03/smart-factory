FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
COPY packages/ ./packages/
COPY packages/shared-types/tsconfig.json ./packages/shared-types/
COPY packages/shared-events/tsconfig.json ./packages/shared-events/
COPY services/orchestrator-service/package.json ./services/orchestrator-service/
COPY services/orchestrator-service/tsconfig.json ./services/orchestrator-service/
COPY services/orchestrator-service/src/ ./services/orchestrator-service/src/
RUN npm install
RUN npm run build -w packages/shared-types --if-present
RUN npm run build -w packages/shared-events --if-present
WORKDIR /app/services/orchestrator-service
RUN npx tsc -p tsconfig.json

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules/ ./node_modules/
COPY --from=builder /app/packages/ ./packages/
COPY --from=builder /app/services/orchestrator-service/package.json ./services/orchestrator-service/
COPY --from=builder /app/services/orchestrator-service/dist/ ./services/orchestrator-service/dist/
WORKDIR /app/services/orchestrator-service
EXPOSE 4001
HEALTHCHECK --interval=30s --timeout=10s CMD wget -q --spider http://127.0.0.1:4001/api/health || exit 1
CMD ["node", "dist/main"]
