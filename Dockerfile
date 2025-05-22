FROM python:3.10.11

# Install system dependencies including Intel Arc GPU support
RUN apt-get update && apt-get install -y \
    # Essential tools
    wget \
    curl \
    gnupg \
    # Intel GPU and media packages for hardware acceleration
    intel-media-va-driver-non-free \
    intel-gpu-tools \
    libva-utils \
    vainfo \
    # FFmpeg and media libraries
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Add Intel APT repository for OneAPI runtime
RUN wget -qO - https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | apt-key add - && \
    echo "deb https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list

# Install Intel OneAPI components for optimal Arc support
RUN apt-get update && apt-get install -y \
    intel-oneapi-runtime-libs \
    intel-level-zero-gpu \
    level-zero \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and ding sound
COPY main.py .
COPY ding.mp3 /app/ding.mp3

# Set Intel Arc optimization environment variables
ENV LIBVA_DRIVER_NAME=iHD \
    LIBVA_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri \
    INTEL_MEDIA_RUNTIME=/usr/lib/x86_64-linux-gnu/dri \
    INTEL_GPU_MIN_FREQ=0 \
    INTEL_GPU_MAX_FREQ=2100

EXPOSE 8080

CMD ["python", "main.py"]
