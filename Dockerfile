FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE 1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update
RUN apt-get install -y libcairo2 git build-essential
RUN rm -rf /var/lib/apt/lists /var/cache/apt/archives /tmp/*

RUN mkdir /app

WORKDIR /app/Userbot
COPY . /app/Userbot

RUN pip3 install --upgrade pip setuptools
RUN pip3 install --no-warn-script-location --no-cache-dir -U -r requirements.txt

RUN rm /etc/localtime
RUN ln -s /usr/share/zoneinfo/Europe/Moscow /etc/localtime

EXPOSE 8080

CMD ["python3", "main.py"]
