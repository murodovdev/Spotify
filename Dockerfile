FROM python:3.12-slim

# FFmpeg is required for audio transcoding.
# Deno is required by yt-dlp ≥2026.07 for YouTube signature/n-challenge solving.
# bgutil-ytdlp-pot-provider server generates PO tokens so YouTube does not
# bot-detect the datacenter IP (paired with the pip plugin of the same name).
ARG BGUTIL_VERSION=1.3.1
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg aria2 curl unzip \
    && curl -fsSL https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip -o /tmp/deno.zip \
    && unzip /tmp/deno.zip -d /usr/local/bin/ \
    && rm /tmp/deno.zip \
    && chmod +x /usr/local/bin/deno \
    && curl -fsSL https://github.com/Brainicism/bgutil-ytdlp-pot-provider/archive/refs/tags/${BGUTIL_VERSION}.tar.gz -o /tmp/bgutil.tar.gz \
    && mkdir -p /opt/bgutil \
    && tar xzf /tmp/bgutil.tar.gz -C /opt/bgutil --strip-components=1 \
    && rm /tmp/bgutil.tar.gz \
    && cd /opt/bgutil/server \
    && deno install --allow-scripts=npm:canvas --frozen \
    && apt-get purge -y curl unzip && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so the layer is cached across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    MAX_DOWNLOADS=8 \
    PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"8080\")}/health').status==200 else 1)"

CMD ["python", "-m", "bot.main"]
