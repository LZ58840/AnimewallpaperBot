# syntax=docker/dockerfile:1

FROM python:3.10-slim-buster

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY data_worker data_worker
COPY utils.py utils.py
COPY .env .env

CMD [ "python", "-m", "data_worker", "-d" ]
