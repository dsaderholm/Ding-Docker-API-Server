FROM python:3.10.11

# Fix Debian 12 (Bookworm) to include non-free repositories
RUN sed -i 's/Components: main/Components: main contrib non-free non-free-firmware/' /etc/apt/sources.list.d/debian.sources

# Install system dependencies and Intel Arc drivers
RUN apt-get update && apt-get install -y \
    wget curl gnupg \
    intel-media-va-driver-non-free \
    vainfo intel-gpu-tools ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and ding sound
COPY main.py .
COPY ding.mp3 /app/ding.mp3

# Set Intel Arc environment variables
ENV LIBVA_DRIVER_NAME=iHD \
    LIBVA_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri \
    INTEL_MEDIA_RUNTIME=/usr/lib/x86_64-linux-gnu/dri

EXPOSE 8080

CMD ["python", "main.py"]
