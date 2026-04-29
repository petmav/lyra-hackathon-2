FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS build
ARG NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_DEV_BEARER
ARG NEXT_PUBLIC_DATA_SOURCE=api
ARG NEXT_PUBLIC_PRAETOR_DATA_MODE=production
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_DEV_BEARER=$NEXT_PUBLIC_DEV_BEARER
ENV NEXT_PUBLIC_DATA_SOURCE=$NEXT_PUBLIC_DATA_SOURCE
ENV NEXT_PUBLIC_PRAETOR_DATA_MODE=$NEXT_PUBLIC_PRAETOR_DATA_MODE
COPY . .
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/package-lock.json ./package-lock.json
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules

EXPOSE 3000
CMD ["npm", "run", "start"]
