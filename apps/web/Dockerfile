# syntax=docker/dockerfile:1.7
FROM node:22-slim

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@11.3.0 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,id=rsswise-pnpm-store,target=/pnpm/store \
    pnpm install --frozen-lockfile --trust-lockfile --ignore-scripts --store-dir /pnpm/store --reporter append-only --config.fetch-timeout=600000 --config.fetch-retries=5

COPY . .
