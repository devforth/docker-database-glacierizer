# docker-database-glacierizer

Docker image for automatic database backups to AWS S3 Glacier with cron-syntax scheduler. [Docker Hub](https://hub.docker.com/r/devforth/docker-database-glacierizer)

Ready to use simple example how to [backup SQL Database wtih this script](https://hinty.io/vprotasenia/how-to-backup-sql-database-simple-ready-to-use-script/)

## Hints on usage
To use this image you need to setup all of it's environment values. If one of it's values are missing, empty or of a wrong type, it will print out a message to log to let you know.

Environment values meaning:
- TEST: defaults to False, if set to True doesn't start the scheduler or server and instead waits 30 seconds and runs database dump
- CRON: crontab syntax that is used to determine when to backup database, if you're new to crontab or unsure you can use [crontab.guru](crontab.guru) website;
- START_SERVER: defaults to True, if set to True starts a server which you can access to manually start database dumping
- SERVER_PORT: default to 33399
- SERVER_BASIC_AUTH_USER: default to admin; username for server basic auth
- SERVER_BASIC_AUTH_PASSWORD: default to admin; password for server basic auth
- DATABASE_TYPE: type of database you want to backup, available values [MySQL, PostgreSQL]
- DATABASE_HOST: hostname or ip address to database
- DATABASE_NAME: scheme name to backup
- DATABASE_USER: username of database user
- DATABASE_PASSWORD: password of database user
- DATABASE_PORT: port of datatbase, default to 3306 for MySql and 5432 for PostgreSQL
- GLACIER_VAULT_NAME: name of Glacier vault that will be created
- AWS_DEFAULT_REGION: AWS region where Glacier vault will be created
- AWS_ACCESS_KEY_ID: access key for your AWS account
- AWS_SECRET_ACCESS_KEY: secret key for your AWS account
- SLACK_WEBHOOK: incoming [webhook url](https://my.slack.com/services/new/incoming-webhook) for posting messages to a channel
- PROJECT_NAME: project name that will be send in slack message

## Notes
Currently only supports one database per docker container for either PostgreSQL or MySQL databases.

Was only tested on MySQL 5.6 and PostgreSQL 10.11, but should work just fine with other versions as well.
