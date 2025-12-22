FROM python:3.11-slim

# Playwright ve build dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python paketlerini yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# CRITICAL: Verify imapclient is installed
RUN python -c "import imapclient; print('✅ imapclient installed:', imapclient.__version__)" || \
    (echo "❌ imapclient NOT found! Installing manually..." && pip install --no-cache-dir imapclient==2.3.1)

# Playwright chromium'u kur (--with-deps ile)
RUN playwright install --with-deps chromium

# Uygulama kodunu kopyala
COPY . .

EXPOSE 8000

# Uygulamayı başlat
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
