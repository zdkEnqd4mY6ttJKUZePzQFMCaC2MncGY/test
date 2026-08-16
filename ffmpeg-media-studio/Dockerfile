FROM ubuntu:22.04

# Prevent interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PORT=7860
ENV HOST=0.0.0.0

# Install system dependencies, FFmpeg, and Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3 \
    python3-pip \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements and latest yt-dlp
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt && \
    pip3 install --no-cache-dir --upgrade yt-dlp

# Copy application files
COPY . .

# Create data directories
RUN mkdir -p data/uploads data/outputs data/temp

EXPOSE 7860

VOLUME ["/app/data"]

CMD ["python3", "app.py"]
