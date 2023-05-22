# syntax=docker/dockerfile:1

FROM python:3.10-slim-buster

RUN apt-get update && apt-get install -y libmariadb-dev gcc

COPY moderator_worker moderator_worker
COPY utils.py utils.py
COPY .env .env

RUN pip install -r moderator_worker/requirements.txt

CMD [ "python", "-m", "moderator_worker", "-d" ]
