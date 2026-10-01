FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10000 lab \
    && useradd --uid 10000 --gid lab --no-create-home lab \
    && mkdir -p /app/instance/uploads \
    && chown lab:lab /app/instance/uploads

COPY app.py internal_service.py reference_assets.json reference_data.json ./
COPY templates ./templates
COPY static ./static
USER 10000:10000
EXPOSE 8000
CMD ["sh", "-c", "python app.py --init-db && exec gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 30 --no-control-socket --access-logfile - --error-logfile - app:app"]
