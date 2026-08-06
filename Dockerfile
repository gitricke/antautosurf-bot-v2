FROM python:3.11-bookworm

# Installa dipendenze di sistema per Playwright (Debian Bookworm)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libnspr4 \
    libnss3 \
    libx11-6 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libxss1 \
    libxrandr2 \
    libasound2 \
    libatk1.0-0 \
    libgtk-3-0 \
    libgdk-pixbuf-2.0-0 \
    libjpeg62-turbo \
    libicu72 \
    libwebp7 \
    libvpx7 \
    libenchant-2-2 \
    && rm -rf /var/lib/apt/lists/*

# Installa dipendenze Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Installa Playwright (senza install-deps, le abbiamo già installate)
RUN playwright install chromium

WORKDIR /app
COPY bot_worker.py .
COPY proxy_manager.py .
COPY accounts.json .
COPY proxy_pool.json .
COPY hash_phash_db.json .

CMD ["python", "-u", "bot_worker.py"]
