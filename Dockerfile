FROM python:3.9-slim

WORKDIR /app


RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    fonts-noto \
    fonts-noto-cjk \
    fonts-unifont \
    fonts-dejavu \
    fonts-freefont-ttf \
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
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xvfb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


RUN pip uninstall -y cssselect && pip install cssselect==1.1.0


ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
RUN playwright install chromium


COPY . .


ENV PYTHONUNBUFFERED=1
ENV PORT=10000


CMD ["python", "app.py"]
