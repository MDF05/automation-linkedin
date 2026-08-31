FROM python:3.11-slim

# Install system dependencies: ADB, OpenGL, GLib (required by EasyOCR)
RUN apt-get update && apt-get install -y \
    android-tools-adb \
    libgl1 \
    libglib2.0-0 \
    libglib2.0-dev \
    tesseract-ocr \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create screenshots directory
RUN mkdir -p /app/static/screenshots

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
