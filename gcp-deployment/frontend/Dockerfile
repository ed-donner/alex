FROM node:20-alpine AS builder
WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

    # Build NextJS app
    # Build arguments for Next.js public env vars
    ARG NEXT_PUBLIC_API_URL
    ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
    ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
    ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=${NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}
    RUN npm run build

# Production stage
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=8080

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 8080

CMD ["node", "server.js"]

