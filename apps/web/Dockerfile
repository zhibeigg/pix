FROM node:22-alpine AS build

WORKDIR /app
ARG VITE_PIX_API_BASE=/api
ENV VITE_PIX_API_BASE=${VITE_PIX_API_BASE}

COPY package.json package-lock.json ./
RUN npm ci

COPY index.html tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts ./
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
