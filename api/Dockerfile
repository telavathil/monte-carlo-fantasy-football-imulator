FROM python:3.12-slim

WORKDIR /app

# System deps for scipy wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir \
      $(python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; print(' '.join(d))")

COPY app/ ./app/
COPY alembic.ini .
COPY alembic/ ./alembic/

ENV PORT=8080
ENV PYTHONPATH=/app
RUN mkdir -p /data
EXPOSE 8080

CMD sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
