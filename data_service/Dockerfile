# syntax=docker/dockerfile:1

FROM python:3.10-slim-buster

COPY data_service data_service
COPY utils.py utils.py
COPY .env .env

RUN pip install -r data_service/requirements.txt

CMD [ "python", "-m", "data_service", "-d" ]
