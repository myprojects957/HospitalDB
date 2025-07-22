# Use an official Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy files to container
COPY . /app

# Install system dependencies (for MySQL connector)
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev gcc \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Expose port
EXPOSE 5000

# Run the app
CMD ["python", "app.py"]
