# ── World of Discord — Docker Image ──────────────────────────────────────────
FROM python:3.13-slim

# System deps for Pillow image generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6-dev libjpeg62-turbo-dev libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create fonts directory if it doesn't exist
RUN mkdir -p assets/fonts

# Run the bot
CMD ["python", "main.py"]
