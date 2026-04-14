# Use the official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

# Install system dependencies (gcc for psycopg2 and other tools)
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Install Playwright browsers (chromium)
RUN playwright install chromium

# Make scripts executable
RUN chmod +x build.sh start.sh

# Expose port (Render uses $PORT)
EXPOSE 8000

# Default command
CMD ["./start.sh"]
