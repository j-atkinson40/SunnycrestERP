FROM python:3.13-slim

WORKDIR /app

# Install system deps for psycopg2 and WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 libffi-dev shared-mime-info \
    libcairo2 libharfbuzz0b && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make start script executable
RUN chmod +x railway-start.sh

EXPOSE 8000

CMD ["bash", "railway-start.sh"]
