FROM python:3.9.0

RUN apt update && apt install gnupg wget lsb-release gcc build-essential -y
RUN sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

RUN apt update
RUN apt install postgresql-client mariadb-client -y
RUN python -m pip install apscheduler boto3 slack_sdk clickhouse_driver

ENV PYTHONUNBUFFERED=TRUE

ENV PYTHONPATH=/scheduler/
WORKDIR /scheduler/

COPY . .

ENTRYPOINT [ "python", "scheduler.py" ]