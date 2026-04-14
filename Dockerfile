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

# Make build.sh executable
RUN chmod +x build.sh

# Run the build script (collectstatic, migrations)
# Note: DATABASE_URL must be provided at runtime if migrate is run here, 
# or we can run it in the start command. For now, we'll let build.sh handle it.
# RUN ./build.sh

# Expose port (Render uses $PORT)
EXPOSE 8000

# Default command (can be overridden in render.yaml)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
