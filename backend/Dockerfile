FROM python:3.13-slim

WORKDIR /app

# Install system deps for psycopg2, WeasyPrint, and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 libffi-dev shared-mime-info \
    libcairo2 libharfbuzz0b \
    imagemagick libmagickwand-dev libtiff-tools \
    fonts-liberation \
    libjpeg62-turbo-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

# Allow ImageMagick to process TIF files
RUN sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml 2>/dev/null || true && \
    sed -i 's/rights="none" pattern="TIFF"/rights="read|write" pattern="TIFF"/' /etc/ImageMagick-6/policy.xml 2>/dev/null || true

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make start script executable
RUN chmod +x railway-start.sh

EXPOSE 8000

CMD ["bash", "railway-start.sh"]
