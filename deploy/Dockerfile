FROM node:22-bookworm-slim AS frontend-build

WORKDIR /site
RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
ARG MEDIAFETCH_API_URL=http://127.0.0.1:8000
ENV MEDIAFETCH_API_URL=$MEDIAFETCH_API_URL
RUN pnpm build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MEDIAFETCH_API_URL=http://127.0.0.1:8000 \
    PORT=10000

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Reuse the official Node distribution from the build image so the final
# container can run the website and the Python downloader together.
COPY --from=node:22-bookworm-slim /usr/local /usr/local

WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app

WORKDIR /app/site
COPY --from=frontend-build /site/package.json ./package.json
COPY --from=frontend-build /site/pnpm-lock.yaml ./pnpm-lock.yaml
COPY --from=frontend-build /site/pnpm-workspace.yaml ./pnpm-workspace.yaml
COPY --from=frontend-build /site/node_modules ./node_modules
COPY --from=frontend-build /site/dist ./dist

EXPOSE 10000

CMD ["sh", "-c", "(cd /app/backend && uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers) & exec node ./node_modules/vinext/dist/cli.js start"]
