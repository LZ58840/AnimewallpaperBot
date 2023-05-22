# syntax=docker/dockerfile:1

FROM hdgigante/python-opencv:4.7.0-alpine

RUN apk add gcc g++ musl-dev mariadb-connector-c-dev

COPY data_worker data_worker
COPY utils.py utils.py
COPY .env .env

RUN pip install -r data_worker/requirements.txt

CMD [ "python", "-m", "data_worker", "-d" ]
