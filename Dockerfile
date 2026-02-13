FROM python:3.10

ENV PYTHONUNBUFFERED=TRUE
WORKDIR /scheduler/

RUN pip install pipenv
RUN apt update && apt install gnupg wget lsb-release gcc build-essential -y
RUN mkdir -p /usr/share/keyrings && \
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
    gpg --dearmor -o /usr/share/keyrings/postgresql-archive-keyring.gpg
RUN echo "deb [signed-by=/usr/share/keyrings/postgresql-archive-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list

RUN apt update
RUN apt install postgresql-client mariadb-client -y

RUN wget https://fastdl.mongodb.org/tools/db/mongodb-database-tools-debian10-x86_64-100.7.0.deb && \
    dpkg -i ./mongodb-database-tools-*.deb && \
    rm -f mongodb-database-tools-*.deb && \
    apt-get install -f

RUN ldconfig

COPY Pipfile Pipfile.lock ./
RUN pipenv sync

COPY src .

CMD [ "pipenv", "run", "python", "scheduler.py" ]
