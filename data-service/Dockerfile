# syntax=docker/dockerfile:1

FROM python:3.10-slim-buster

RUN apt-get update
RUN apt-get install ffmpeg libsm6 libxext6  -y

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY data-service data-service
COPY utils.py utils.py
COPY configs.env configs.env

CMD [ "python", "-m", "data-service", "300" ]
