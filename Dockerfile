FROM python:3.10.11

# Install system dependencies including latest ffmpeg
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    apt-add-repository -y ppa:jonathonf/ffmpeg-4 && \
    apt-get update && \
    apt-get install -y \
    ffmpeg \
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