FROM node:22-alpine AS build

WORKDIR /workspace/apps/web

ARG VITE_PIX_API_BASE=/api
ENV VITE_PIX_API_BASE=${VITE_PIX_API_BASE}

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY index.html tsconfig.json vite.config.ts ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM nginx:stable-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/dist/web /usr/share/nginx/html

EXPOSE 80
