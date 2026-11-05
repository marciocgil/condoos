FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS build
WORKDIR /app
# Rewrites (/api/* -> API) are resolved at build time.
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S condoos && adduser -S condoos -G condoos
COPY --from=build --chown=condoos:condoos /app/.next/standalone ./
COPY --from=build --chown=condoos:condoos /app/.next/static ./.next/static
USER condoos
EXPOSE 3000
CMD ["node", "server.js"]
