FROM python:3.10.11

# Fix Debian 12 (Bookworm) to include non-free repositories
RUN sed -i 's/Components: main/Components: main contrib non-free non-free-firmware/' /etc/apt/sources.list.d/debian.sources

# Install system dependencies and Intel Arc support
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    # Intel Arc GPU support
    vainfo intel-gpu-tools \
    intel-media-va-driver-non-free \
    onevpl-tools libvpl2 libvpl-dev \
    # FFmpeg with proper Intel support
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and ding sound
COPY main.py .
COPY intel_gpu_init.py .
COPY ding.mp3 /app/ding.mp3

# Set Intel Arc environment variables for FFmpeg hardware acceleration
ENV LIBVA_DRIVER_NAME=iHD \
    LIBVA_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri \
    INTEL_MEDIA_RUNTIME=/usr/lib/x86_64-linux-gnu/dri \
    INTEL_GPU_MIN_FREQ=0 \
    INTEL_GPU_MAX_FREQ=2100 \
    MFX_IMPL_BASEDIR=/usr/lib/x86_64-linux-gnu

EXPOSE 8080

CMD ["python", "main.py"]
