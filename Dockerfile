FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PIP_NO_CACHE_DIR=1
ENV TZ=Europe/Moscow

RUN apt update
RUN apt install -y --no-install-recommends libcairo2 git build-essential
RUN rm -rf /var/lib/apt/lists /var/cache/apt/archives /tmp/*

RUN mkdir /app

COPY . /app
WORKDIR /app

RUN pip3 install --upgrade pip setuptools wheel
RUN pip3 install --no-warn-script-location --no-cache-dir -U uvloop -r requirements.txt

EXPOSE 8080

CMD ["python3", "main.py"]
