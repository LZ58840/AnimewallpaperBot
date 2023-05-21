# syntax=docker/dockerfile:1

FROM python:3.10-slim-buster

COPY moderator_service moderator_service
COPY utils.py utils.py
COPY .env .env

RUN pip install -r moderator_service/requirements.txt

CMD [ "python", "-m", "moderator_service", "-d" ]
