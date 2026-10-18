FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
COPY glasses/package.json ./glasses/package.json
COPY web/package.json ./web/package.json
RUN npm ci --workspace web --include-workspace-root

COPY glasses/config.mjs ./glasses/config.mjs
COPY glasses/src/api.ts glasses/src/mock.ts glasses/src/env.d.ts ./glasses/src/
COPY web ./web
ARG BACKEND_URL
RUN BACKEND_URL="$BACKEND_URL" MOCK_MODE=false npm run build -w web

FROM nginx:stable-alpine
COPY --from=build /app/web/dist /usr/share/nginx/html
EXPOSE 80
