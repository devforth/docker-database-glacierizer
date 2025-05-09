# docker-database-glacierizer

Docker image for automatic database backups to AWS S3 Glacier with cron-syntax scheduler. [Docker Hub](https://hub.docker.com/r/devforth/docker-database-glacierizer)

Ready to use simple example how to [backup SQL Database with this script](https://hinty.io/vprotasenia/how-to-backup-sql-database-simple-ready-to-use-script/)

## Hints on usage
To use this image you need to set up all of its environment values. If one of its values are missing, empty or of a wrong type, it will print out a message to log to let you know.

| Environment                    | Description                                                                                                                                     | Required | Default            |
|--------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|----------|--------------------|
| CRON                           | Crontab syntax used to determine when to do a backup. You can use [crontab.guru](https://crontab.guru) website to get help with cron syntax     | ✓        |                    |
| START_MANUAL_MANAGEMENT_SERVER | When set to true, starts a server on specified port to which you can send a http request to manually trigger backup process                     |          | `true`             |
| MANUAL_MANAGEMENT_PORT         | Prot for manual management server                                                                                                               |          | 33399              |
| DATABASE_TYPE                  | Type of the database you want to backup. Available values [MySQL, PostgreSQL, ClickHouse, MongoDB]                                              | ✓        |                    |
| DATABASE_HOST                  | Hostname or IP address to access database                                                                                                       | ✓        |                    |
| DATABASE_PORT                  | Port to access database. If set to 0 selects a default port for a specified type (3306 for MySQL, 5432 for PostgreSQL).                         |          | 0                  |
| DATABASE_USER                  | Username to access database                                                                                                                     | ✓        |                    |
| DATABASE_PASSWORD              | Password to access database                                                                                                                     | ✓        |                    |
| AUTH_DATABASE_NAME             | Name of the authentication database. Only used for MongoDB                                                                                      |          | admin              |
| GLACIER_BUCKET_NAME            | Name of the S3 bucket where dumps will be stored. If bucket does not exists it will be created                                                  | ✓        |                    |
| GLACIER_STORAGE_CLASS          | Glacier storage class that will be used to store uploaded dumps in S3. Available values [instant, flexible, deep]                               |          | flexible           |
| GLACIER_EXPIRE_AFTER           | If set to a value greater than 0 creates a lifecycle rule on whole S3 bucket that will delete an object after set amount of day it was uploaded |          | 0                  |
| AWS_DEFAULT_REGION             | Region where S3 bucket will be created                                                                                                          | ✓        |                    |
| AWS_ACCESS_KEY_ID              | Access key for AWS account                                                                                                                      | ✓        |                    |
| AWS_SECRET_ACCESS_KEY          | Secret key for AWS account                                                                                                                      | ✓        |                    |
| SLACK_WEBHOOK                  | If set it will be sending a message to Slack every time it finishes (successfully or not) dumping database and uploading dump                   |          |                    |
| PROJECT_NAME                   | Used as a "header" for slack message. If not set default to machine hostname                                                                    |          | <machine hostname> |
| CLEAR_ALL_DUMPS                | If set to true, all dump files will be removed after backup. If false, only old dumps will be removed, keeping the latest one                   |          | false              |
| CLICKHOUSE_TIMEOUT             | Timeout in seconds for ClickHouse backup operations                                                                                             |          | 300                |

## Notes
Currently only supports one database per docker container for either PostgreSQL or MySQL databases.

Was only tested on MySQL 5.6 and PostgreSQL 10.11, but should work just fine with other versions as well.

If you enabled server for manual dumping it's better to close the port from outside and use `ssh -L` option
for port forwarding due to lack of security measures for said server.