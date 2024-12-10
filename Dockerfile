FROM python:3.10

ENV PYTHONUNBUFFERED=TRUE
WORKDIR /scheduler/

RUN pip install pipenv
RUN apt update && apt install gnupg wget lsb-release gcc build-essential -y
RUN sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -

RUN apt update
RUN apt install postgresql-client mariadb-client -y

RUN wget https://fastdl.mongodb.org/tools/db/mongodb-database-tools-debian10-x86_64-100.7.0.deb && \
    apt install ./mongodb-database-tools-*.deb && \
    rm -f mongodb-database-tools-*.deb && \
    echo "/usr/lib/postgresql/17/lib" | sudo tee /etc/ld.so.conf.d/postgresql.conf && \
    ldconfig

COPY Pipfile Pipfile.lock ./
RUN pipenv sync

COPY src .

CMD [ "pipenv", "run", "python", "scheduler.py" ]
