FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UPLOAD_DIR=/app/instance/uploads
WORKDIR /app
COPY web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10000 lab \
    && useradd --uid 10000 --gid lab --no-create-home lab \
    && mkdir -p /app/instance/uploads \
    && chown lab:lab /app/instance/uploads

COPY web/SSLC.py internal_service.py ./
COPY web/app ./app
USER 10000:10000
EXPOSE 8000
CMD ["sh", "-c", "python SSLC.py --init-db && exec gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 30 --no-control-socket --access-logfile - --error-logfile - SSLC:app"]
