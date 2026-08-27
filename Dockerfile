FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
ARG MEDIAFETCH_API_URL=http://backend:8000
ENV MEDIAFETCH_API_URL=$MEDIAFETCH_API_URL
RUN pnpm build
EXPOSE 3000
CMD ["pnpm", "start"]
