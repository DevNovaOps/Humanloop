FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies for Pillow and MySQL
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY humanloop_backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Django project
COPY humanloop_backend/ .

# Collect static files
RUN python manage.py collectstatic --no-input 2>/dev/null || true

# Expose port
EXPOSE $PORT

# Start command
CMD python manage.py migrate --no-input && gunicorn humanloop_backend.wsgi --bind 0.0.0.0:${PORT:-8000}
