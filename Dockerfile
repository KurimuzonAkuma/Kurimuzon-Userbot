FROM python:3.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Moscow

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libcairo2 \
        git \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /app

COPY . /app
WORKDIR /app

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-warn-script-location --no-cache-dir -U uvloop -r requirements.txt

CMD ["python", "main.py"]
