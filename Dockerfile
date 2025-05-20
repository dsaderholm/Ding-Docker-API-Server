FROM python:3.10.11

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    ffmpeg \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Intel GPU drivers and runtime requirements
RUN wget -qO - https://repositories.intel.com/graphics/intel-graphics.key | gpg --dearmor --output /usr/share/keyrings/intel-graphics.gpg
RUN echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/graphics/ubuntu jammy arc" | tee /etc/apt/sources.list.d/intel-gpu-jammy.list
RUN apt-get update && apt-get install -y \
    intel-media-va-driver-non-free \
    intel-opencl-icd \
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

EXPOSE 8080

CMD ["python", "main.py"]