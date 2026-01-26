FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY apps/frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY apps/frontend/ ./

# Pass build arguments
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_MOCK_API
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_MOCK_API=$NEXT_PUBLIC_MOCK_API

# Build for production with standalone output
# Use npx next build to bypass the script which tries to sync .env.local
RUN npx next build

# Production image
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=8080

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built assets
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 8080

CMD ["node", "server.js"]
