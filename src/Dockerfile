FROM python:3.9.0-alpine3.12

RUN apk add --no-cache postgresql-client mysql-client

RUN python -m pip install apscheduler boto3 slack_sdk

COPY scheduler.py /scheduler/scheduler.py
COPY logging.ini /scheduler/logging.ini

ENV PYTHONUNBUFFERED=TRUE

ENV PYTHONPATH=/scheduler/
WORKDIR /scheduler/

CMD python scheduler.py