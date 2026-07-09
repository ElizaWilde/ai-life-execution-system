# ==============================
# Stage 1: Install dependencies
# ==============================
FROM node:22-alpine AS deps

WORKDIR /app

# Enable pnpm through Corepack
RUN corepack enable

# Copy dependency files first for Docker cache
COPY package.json pnpm-lock.yaml ./
COPY pnpm-workspace.yaml ./

# Install exact dependency versions from the lockfile
RUN pnpm install --frozen-lockfile


# ==============================
# Stage 2: Build Next.js
# ==============================
FROM node:22-alpine AS builder

WORKDIR /app

RUN corepack enable

# Public frontend environment variable
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

# Reuse dependencies installed in the deps stage
COPY --from=deps /app/node_modules ./node_modules

# Copy application source code
COPY . .

# Generate the production Next.js build
RUN pnpm build


# ==============================
# Stage 3: Run production server
# ==============================
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

# Create a non-root runtime user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy only files required at runtime
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Stop running as root
USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]