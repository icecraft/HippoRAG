# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies with Taobao registry
RUN npm install --silent --registry=https://registry.npmmirror.com

# Copy source code
COPY . .

# Build the app (REACT_APP_API_URL intentionally unset so client uses /api proxy)
RUN npm run build

# Production stage
FROM node:20-alpine

WORKDIR /app

# Environment variables (can be overridden at runtime with -e)
# REACT_APP_API_URL is used by server.js for proxy target, not baked into client bundle
ENV REACT_APP_API_URL=http://host.docker.internal:8000
ENV PORT=80

# Copy built files
COPY --from=builder /app/build ./build

# Install production dependencies with Taobao registry
RUN npm install --registry=https://registry.npmmirror.com express http-proxy-middleware

# Copy server file
COPY server.js ./

# Expose port
EXPOSE 80

# Start Node server
CMD ["node", "server.js"]
