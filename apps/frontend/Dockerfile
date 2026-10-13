FROM node:20-alpine AS builder

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
COPY packages/ ./packages/
COPY apps/frontend/package.json ./apps/frontend/

# npm install (not ci) so newly-added deps resolve without a pre-updated lockfile
RUN npm install

COPY apps/frontend/ ./apps/frontend/

WORKDIR /app/apps/frontend
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules/ ./node_modules/
COPY --from=builder /app/apps/frontend/ ./apps/frontend/

WORKDIR /app/apps/frontend

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD wget -q --spider http://localhost:3000 || exit 1

CMD ["npm", "run", "start"]
