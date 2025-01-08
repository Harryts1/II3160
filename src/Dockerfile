FROM python:3.9-slim

# Tentukan working directory
WORKDIR /app

# Install dependencies sistem
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libssl-dev \
    libffi-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Salin file requirements.txt dari src
COPY ./src/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Salin semua file dari folder src ke container
COPY ./src /app/src

# Expose port untuk aplikasi
EXPOSE 8000

# Perintah untuk menjalankan aplikasi
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
