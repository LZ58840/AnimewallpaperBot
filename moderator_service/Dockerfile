# syntax=docker/dockerfile:1

FROM python:3.10-slim-buster

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY moderator_service moderator_service
COPY utils.py utils.py
COPY .env .env

CMD [ "python", "-m", "moderator_service", "-d" ]
