FROM python:3.12-alpine
RUN apk add --no-cache docker-cli docker-cli-compose && pip install --no-cache-dir pyyaml yt-dlp
WORKDIR /app
COPY app/ /app/
COPY presets/ /app/presets/
EXPOSE 7979
CMD ["python", "-u", "server.py"]
