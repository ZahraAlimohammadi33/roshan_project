FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip --timeout 300 --retries 15 && \
    pip install --index-url https://download.pytorch.org/whl/cpu \
      torch==2.10.0 --timeout 300 --retries 15 && \
    pip install --timeout 300 --retries 15 -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/chroma_db /app/media

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --timeout 300"]
