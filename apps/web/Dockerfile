FROM node:22-alpine AS deps
WORKDIR /app
RUN corepack enable
COPY apps/web/package.json apps/web/pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web/ ./
RUN pnpm build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S culpa && adduser -S culpa -G culpa
COPY --from=build --chown=culpa:culpa /app/.next/standalone ./
COPY --from=build --chown=culpa:culpa /app/.next/static ./.next/static
COPY --from=build --chown=culpa:culpa /app/public ./public
USER culpa
EXPOSE 3000
CMD ["node", "server.js"]
