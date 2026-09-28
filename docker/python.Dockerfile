FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
COPY requirements/base.txt /app/requirements/base.txt
RUN pip install --no-cache-dir -r /app/requirements/base.txt
COPY src /app/src
COPY dashboard /app/dashboard
COPY tests /app/tests
COPY pytest.ini /app/pytest.ini
