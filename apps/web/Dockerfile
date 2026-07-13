FROM node:26-slim AS deps

WORKDIR /app/apps/web

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

FROM node:26-slim AS builder

WORKDIR /app/apps/web

ARG NEXT_PUBLIC_CONTRACT_AI_SYSTEM_URL
ARG NEXT_PUBLIC_CORE_API_URL
ARG NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_GA_MEASUREMENT_ID
ARG NEXT_PUBLIC_YM_COUNTER_ID

ENV NODE_ENV=production
ENV NEXT_PUBLIC_CONTRACT_AI_SYSTEM_URL=${NEXT_PUBLIC_CONTRACT_AI_SYSTEM_URL}
ENV NEXT_PUBLIC_CORE_API_URL=${NEXT_PUBLIC_CORE_API_URL}
ENV NEXT_PUBLIC_SITE_URL=${NEXT_PUBLIC_SITE_URL}
ENV NEXT_PUBLIC_GA_MEASUREMENT_ID=${NEXT_PUBLIC_GA_MEASUREMENT_ID}
ENV NEXT_PUBLIC_YM_COUNTER_ID=${NEXT_PUBLIC_YM_COUNTER_ID}

COPY --from=deps /app/apps/web/node_modules ./node_modules
COPY apps/web ./

RUN npm run build

FROM node:26-slim AS runner

WORKDIR /app/apps/web

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN mkdir -p /app/data && chown -R node:node /app

COPY --from=builder --chown=node:node /app/apps/web/.next ./.next
COPY --from=builder --chown=node:node /app/apps/web/public ./public
COPY --from=builder --chown=node:node /app/apps/web/package.json ./package.json
COPY --from=builder --chown=node:node /app/apps/web/package-lock.json ./package-lock.json
COPY --from=builder --chown=node:node /app/apps/web/node_modules ./node_modules
COPY --from=builder --chown=node:node /app/apps/web/next.config.js ./next.config.js

USER node

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
