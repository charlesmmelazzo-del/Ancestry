# Multi-stage build:
#   1) Use Python 3 to run the static-site build script
#   2) Serve the resulting /public/ directory with nginx
#
# This keeps the image tiny (~25 MB) and makes redeploys instant
# whenever you edit data/people.json.

# ---- Stage 1: build static site ----
FROM python:3.12-slim AS builder
WORKDIR /app
COPY . .
RUN python3 build.py

# ---- Stage 2: serve with nginx ----
FROM nginx:1.27-alpine
COPY --from=builder /app/public /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Railway injects PORT — make nginx listen on it
ENV PORT=8080
EXPOSE 8080

# Substitute $PORT into the nginx config at start time
CMD ["sh", "-c", "envsubst '$PORT' < /etc/nginx/conf.d/default.conf > /tmp/default.conf && mv /tmp/default.conf /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
