# docker-database-glacierizer

Docker image for automatic database backups to AWS S3 Glacier with cron-syntax scheduler. [Docker Hub](https://hub.docker.com/r/ivanborshchov/docker-database-glacierizer)

## Hints on usage
To use this image you need to setup all of it's environment values. If one of it's values are missing, empty or of a wrong type, it will print out a message to log to let you know.

Environment values meaning:
- TEST: defaults to False, if set to True doesn't start the scheduler instead waits 30 seconds and runs database dump
- CRON: crontab syntax that is used to determine when to backup database, if you're new to crontab or unsure you can use [crontab.guru](crontab.guru) website;
- DATABASE_TYPE: type of database you want to backup, available values [MySQL, PostgreSQL]
- DATABASE_HOST: hostname or ip address to database
- DATABASE_NAME: scheme name to backup
- DATABASE_USER: username of database user 
- DATABASE_PASSWORD: password of database user
- GLACIER_VAULT_NAME: name of Glacier vault that will be created
- AWS_DEFAULT_REGION: AWS region where Glacier vault will be created
- AWS_ACCESS_KEY_ID: access key for your AWS account
- AWS_SECRET_ACCESS_KEY: secret key for your AWS account

## Notes
Currently only supports one database per docker container for either PostgreSQL or MySQL databases. 

Was only tested on MySQL 5.6 and PostgreSQL 10.11, but should work just fine with other versions as well.