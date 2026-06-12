FROM python:3.10.19-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    PYTHONPATH=/app/APP

# Set work directory
WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY APP /app/APP

# Set non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Command to run the application using Gunicorn
CMD ["gunicorn", "-c", "APP/gunicorn_conf.py", "APP.app:app"]
