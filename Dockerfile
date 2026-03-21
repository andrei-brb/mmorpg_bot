# ── World of Discord — Docker Image ──────────────────────────────────────────
# Stage 1: build Discord Activity (Vite). Set build-arg VITE_DISCORD_CLIENT_ID (Application ID).
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-bookworm-slim AS activity-build
WORKDIR /app/activity
COPY activity/package.json activity/package-lock.json ./
RUN npm ci
COPY activity/ ./
ARG VITE_DISCORD_CLIENT_ID=""
ARG VITE_API_BASE_URL=""
ENV VITE_DISCORD_CLIENT_ID=$VITE_DISCORD_CLIENT_ID
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN if [ -z "$VITE_DISCORD_CLIENT_ID" ]; then \
      mkdir -p dist && \
      printf '%s\n' '<!doctype html><meta charset="utf-8"><title>World of Discord</title><p>Rebuild with Docker build-arg VITE_DISCORD_CLIENT_ID to bundle the Activity.</p>' > dist/index.html; \
    else \
      npm run build; \
    fi

# ── Stage 2: Python bot + optional static Activity dist ──────────────────────
FROM python:3.11-slim

# System deps for Pillow image generation and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6-dev libjpeg62-turbo-dev libpng-dev \
    gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Overlay built Activity from stage 1
COPY --from=activity-build /app/activity/dist ./activity/dist

# Create fonts directory if it doesn't exist
RUN mkdir -p assets/fonts

# Railway / platforms set PORT for HTTP; bot also uses it for Activity API + static files.
ENV ACTIVITY_SERVE_STATIC=1

# Run the bot
CMD ["python", "main.py"]
