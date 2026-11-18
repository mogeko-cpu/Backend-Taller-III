FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5001
# 4 procesos x 4 hilos; ajustable con GUNICORN_CMD_ARGS
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--threads", "4", "--worker-class", "gthread", "--timeout", "60", "app:app"]
