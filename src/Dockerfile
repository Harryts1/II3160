# Gunakan base image Python 3.9-slim
FROM python:3.9-slim

# Tentukan working directory di dalam container
WORKDIR /II3160

# Install dependencies sistem yang diperlukan
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libssl-dev \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Salin file requirements.txt dari folder src
COPY ./src/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Salin semua file ke dalam container
COPY . .

# Expose port untuk aplikasi
EXPOSE 8000

# Perintah untuk menjalankan aplikasi
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
