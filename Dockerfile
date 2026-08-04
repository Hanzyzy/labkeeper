FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PORT=5000
ENV PYTHONUNBUFFERED=1

EXPOSE 5000

# Start production Gunicorn server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "app:create_app()"]
