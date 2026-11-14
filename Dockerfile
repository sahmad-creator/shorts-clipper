# Free hosting: Hugging Face Spaces (SDK: Docker) ya koi bhi Docker server
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg nodejs fonts-noto-core && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=user . .
ENV HOST=0.0.0.0 PORT=7860 WHISPER_MODEL=base MAX_MINUTES=30
EXPOSE 7860
CMD ["python", "app.py"]
