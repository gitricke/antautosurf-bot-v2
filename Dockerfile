FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgomp1 libnspr4 libnss3 libx11-6 libxcomposite1 \
    libxcursor1 libxdamage1 libxi6 libxtst6 libxss1 \
    libxrandr2 libasound2 libatk1.0-0 libgtk-3-0 \
    libgdk-pixbuf-2.0-0 libjpeg62-turbo libicu72 \
    libwebp7 libvpx7 libenchant-2-2 libgbm1 \
    libxkbcommon0 libpango-1.0-0 libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium

WORKDIR /app
COPY bot_worker.py .
COPY accounts.json .

CMD ["python", "-u", "bot_worker.py"]
