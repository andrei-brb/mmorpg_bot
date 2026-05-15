# syntax=docker/dockerfile:1
# ── World of Discord — Docker Image ──────────────────────────────────────────
# Stage 1: build Discord Activity (Vite). Set build-arg VITE_DISCORD_CLIENT_ID (Application ID).
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-bookworm-slim AS activity-build
WORKDIR /app/activity
COPY activity/package.json activity/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY activity/ ./
# Must be passed at docker build time (same as Discord Application ID).
# Railway: add variable VITE_DISCORD_CLIENT_ID and enable it for **Build**,
# or set Docker Build Arg in the service settings.
ARG VITE_DISCORD_CLIENT_ID
ARG VITE_API_BASE_URL=
ENV VITE_DISCORD_CLIENT_ID=$VITE_DISCORD_CLIENT_ID
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
# Rollup ships platform-specific optional deps; `npm ci` in Linux sometimes skips the right
# binary when the lockfile was generated on another OS (npm/cli#4828). Install explicitly.
RUN --mount=type=cache,target=/root/.npm \
    ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then npm install @rollup/rollup-linux-arm64-gnu --no-save; \
    else npm install @rollup/rollup-linux-x64-gnu --no-save; fi
RUN --mount=type=cache,target=/root/.npm \
    if [ -z "$VITE_DISCORD_CLIENT_ID" ]; then \
      echo "ERROR: Docker build-arg VITE_DISCORD_CLIENT_ID is required (your Discord Application ID)." >&2; \
      echo "Railway: Service → Variables → add VITE_DISCORD_CLIENT_ID → enable for **Build**, redeploy." >&2; \
      exit 1; \
    fi \
    && npm run build

# ── Stage 2: Python bot + optional static Activity dist ──────────────────────
FROM python:3.11-slim

# System deps for Pillow image generation and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6-dev libjpeg62-turbo-dev libpng-dev \
    gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (BuildKit cache speeds rebuilds; does not bloat final layers)
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

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
