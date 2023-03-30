FROM python:3.10-slim AS bot

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update
RUN apt-get install -y python3 python3-pip python-dev build-essential python3-venv git
RUN rm -rf /var/lib/apt/lists /var/cache/apt/archives /tmp/*

RUN mkdir /app

COPY . /app
WORKDIR /app

RUN pip3 install --upgrade pip setuptools
RUN pip3 install --no-warn-script-location --no-cache-dir -U -r requirements.txt

EXPOSE 8080

CMD python3 main.py
