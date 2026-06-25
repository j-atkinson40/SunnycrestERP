FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ARG VITE_APP_DOMAIN=getbridgeable.com
# Railway provides RAILWAY_GIT_COMMIT_SHA in the build env; declaring it as an
# ARG receives it into the Docker build so the vite emit-version-json plugin
# can stamp dist/version.json with the deployed commit (the CI deploy-gate's
# frontend-freshness signal). Absent (e.g. local docker build) → plugin writes
# "unknown" → gate treats as not-matching (fail-closed, never false-green).
ARG RAILWAY_GIT_COMMIT_SHA
RUN echo "VITE_API_URL=${VITE_API_URL}" > .env.production && \
    echo "VITE_APP_DOMAIN=${VITE_APP_DOMAIN}" >> .env.production
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_APP_DOMAIN=$VITE_APP_DOMAIN
ENV RAILWAY_GIT_COMMIT_SHA=$RAILWAY_GIT_COMMIT_SHA
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
