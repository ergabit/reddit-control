# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Install deps first (layer caching)
COPY package.json ./
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

# Install curl for healthcheck
RUN apk add --no-cache curl

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built files
COPY --from=build /app/build /usr/share/nginx/html

# Default nginx config is fine for SPA
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
