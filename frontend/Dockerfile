# ==============================================================================
# NovaEnterprise Frontend Containerfile (Built from frontend/ directory context)
# Multi-stage Next.js standalone production build
# ==============================================================================

# Stage 1: Install dependencies
FROM node:22-alpine AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

# Stage 2: Rebuild source code
FROM node:22-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

# Ensure public folder exists
RUN mkdir -p public

RUN npm run build

# Stage 3: Production runner
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3001 \
    HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy static assets and standalone server output
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:3001/ || exit 1

CMD ["node", "server.js"]
