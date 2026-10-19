FROM python:3.12-alpine
RUN apk add --no-cache docker-cli docker-cli-compose tailscale && pip install --no-cache-dir pyyaml yt-dlp
WORKDIR /app
COPY wizard/app/ /app/
COPY wizard/presets/ /app/presets/
COPY docs/ /app/docs/
EXPOSE 7979
CMD ["python", "-u", "server.py"]
