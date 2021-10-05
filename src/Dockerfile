FROM python:3.9.0-alpine3.12

RUN apk add --no-cache postgresql-client mysql-client gcc musl-dev

RUN python -m pip install apscheduler boto3 slack_sdk clickhouse_driver

ENV PYTHONUNBUFFERED=TRUE

ENV PYTHONPATH=/scheduler/
WORKDIR /scheduler/

COPY . .

CMD python scheduler.py