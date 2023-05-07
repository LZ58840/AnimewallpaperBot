FROM hdgigante/python-opencv:4.7.0-alpine

RUN apk add gcc musl-dev mariadb-connector-c-dev
ENV PYTHONBUFFERED 1
ENV RUN_DOCKER 1

COPY acr_worker acr_worker
COPY utils.py utils.py
COPY .env .env

RUN pip install -r acr_worker/requirements.txt

ENTRYPOINT celery -A acr_worker worker --loglevel=info
