FROM python:3.10-trixie

WORKDIR /scheduler/

ARG MONGO_TOOLS_VERSION=100.10.0
# set by buildx: amd64 or arm64. MongoDB has no Debian build of the tools for arm64,
# the Ubuntu 24.04 one works here (Go binary, needs only libgssapi-krb5-2)
ARG TARGETARCH
RUN case "$TARGETARCH" in \
        arm64) MONGO_TOOLS_BUILD=ubuntu2404-arm64 ;; \
        *)     MONGO_TOOLS_BUILD=debian12-x86_64 ;; \
    esac && \
    apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg && \
    install -d /usr/share/keyrings && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
        gpg --dearmor -o /usr/share/keyrings/postgresql-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/postgresql-archive-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client mariadb-client sqlite3 libgssapi-krb5-2 && \
    curl -fsSL https://fastdl.mongodb.org/tools/db/mongodb-database-tools-${MONGO_TOOLS_BUILD}-${MONGO_TOOLS_VERSION}.tgz | \
        tar -xz -C /usr/local/bin --strip-components=2 --wildcards '*/bin/mongodump' && \
    apt-get purge -y --auto-remove curl gnupg && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src .

CMD ["python", "scheduler.py"]
