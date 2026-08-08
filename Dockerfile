FROM python:3.11-bookworm

# ============================================================
# INSTALLA TUTTE LE DIPENDENZE DI SISTEMA PER PLAYWRIGHT
# ============================================================
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
    libgbm1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libcairo2 \
    libjpeg62-turbo \
    libicu72 \
    libwebp7 \
    libvpx7 \
    libenchant-2-2 \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# INSTALLA LE DIPENDENZE PYTHON
# ============================================================
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================
# INSTALLA PLAYWRIGHT E IL BROWSER CHROMIUM
# ============================================================
RUN playwright install chromium

# ============================================================
# COPIA I FILE DEL BOT
# ============================================================
WORKDIR /app
COPY bot_worker.py .
COPY accounts.json .
COPY hash_phash_db.json .

# ============================================================
# COMANDO DI AVVIO
# ============================================================
CMD ["python", "-u", "bot_worker.py"]
