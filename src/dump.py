import glob
import gzip
import logging
import os
from datetime import datetime

import boto3
from clickhouse_driver import Client as ClickhouseClient
from glacier_upload import upload

from slack import send_slack_message, sizeof_fmt

logger = logging.getLogger("ddgscheduler")


def remove_older_dumps(env, dump_path):
    logger.info(f"{datetime.now()}: Remove older dumps")

    filename_template = os.path.join(
        "/tmp",
        f'{env.get("DATABASE_TYPE")}_{env.get("DATABASE_NAME")}_*.sql.gz',
    )
    for filename_ in glob.glob(filename_template):
        logger.info(f"{datetime.now()}: {filename_=}")
        try:
            if filename_ != dump_path:
                # Trying to remove a current file
                os.remove(filename_)
        except EnvironmentError as error:
            logger.error(f"Error while trying to remove older dumps. {error=}")


def dump_general(template):
    def wrapper(environment, output_path):
        dump_command = template.format(
            host=environment.get("DATABASE_HOST"),
            user=environment.get("DATABASE_USER"),
            password=environment.get("DATABASE_PASSWORD"),
            database=environment.get("DATABASE_NAME"),
            port=environment.get("DATABASE_PORT"),
            dump_path=output_path,
        )

        wait_exit_status = os.system(dump_command)
        exit_status = os.waitstatus_to_exitcode(wait_exit_status)

        if wait_exit_status != 0 or exit_status != 0:
            logger.error(
                "RETURN CODE OF DUMP PROCESS != 0. CHECK OUTPUT ABOVE FOR ERRORS!"
            )
            send_slack_message(
                environment,
                "Failed to create DB dump. Please check the error in the container logs.",
                "FAIL",
            )
            raise Exception("Failed to create dump of database")

    return wrapper


def dump_clickhouse(environment, output_path):
    def stringify_row(row):
        new_row = []

        for v in row:
            if type(v) == datetime:
                v: datetime
                new_row.append(v.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                new_row.append(str(v))

        return new_row

    client = ClickhouseClient(
        host=environment.get("DATABASE_HOST"),
        user=environment.get("DATABASE_USER"),
        password=environment.get("DATABASE_PASSWORD"),
        database=environment.get("DATABASE_NAME"),
        port=environment.get("DATABASE_PORT"),
    )

    available_tables = list(
        map(
            lambda x: x[0],
            client.execute(
                f'SHOW TABLES IN `{environment.get("DATABASE_NAME")}`'
            ),
        )
    )

    dump_output = ""

    for table in available_tables:
        create_query = client.execute(f"SHOW CREATE TABLE `{table}`")[0][0]
        dump_output += create_query + ";\n"

    dump_output += "\n\n"

    for table in available_tables:
        insert_query = client.execute(f"SELECT * FROM {table}")

        dump_output += f"INSERT INTO `{table}` FORMAT TSV"

        for row in insert_query:
            dump_output += "\n" + "\t".join(stringify_row(row))

        dump_output += ";\n\n"

    with gzip.GzipFile(output_path, "w+") as f:
        f.write(dump_output.encode())

    return output_path


def dump_database(environment):
    logger.info(f"{datetime.now()}: Creating backup")

    filename = f'{environment.get("DATABASE_TYPE")}_{environment.get("DATABASE_NAME")}_{datetime.now().strftime("%d_%m_%Y")}.sql.gz'
    dump_path = os.path.join("/tmp", filename)

    dump_database_methods = {
        "mysql": dump_general(
            '/bin/bash -c \'set -o pipefail; mysqldump -h "{host}" -u "{user}" -p"{password}" --databases "{database}" -P {port} --protocol tcp | gzip -9 > {dump_path}\''
        ),
        "postgresql": dump_general(
            'PGPASSWORD="{password}" pg_dump -h "{host}" -U "{user}" -d "{database}" -p {port} -Fp -Z9 > {dump_path}'
        ),
        "clickhouse": dump_clickhouse,
    }

    database_type = environment.get("DATABASE_TYPE").lower()
    dump_database_method = dump_database_methods.get(database_type)

    if dump_database_method:
        dump_database_method(environment, dump_path)

        file_size = 0
        try:
            file_size = os.path.getsize(dump_path)
        except Exception as e:
            logger.error("Failed to get size of file.")
            logger.exception(e)

        logger.info(f"{datetime.now()}: Backup created. Uploading to glacier")
        try:
            glacier = boto3.client("glacier")
            glacier.create_vault(
                vaultName=environment.get("GLACIER_VAULT_NAME")
            )

            upload.upload_archive(
                vault_name=environment.get("GLACIER_VAULT_NAME"),
                file_name=[dump_path],
                arc_desc=filename,
                part_size_mb=128,
                num_threads=1,
                upload_id=None,
            )
            logger.info("Glacier upload done.")

            remove_older_dumps(env=environment, dump_path=dump_path)

            send_slack_message(
                environment,
                f"Successfully created and uploaded DB dump ({sizeof_fmt(file_size)}).",
            )
        except Exception as e:
            logger.exception(e)
            send_slack_message(
                environment,
                f"Failed to upload DB dump ({sizeof_fmt(file_size)}) to AWS Glacier. Please check the error in the container logs.",
                "FAIL",
            )
    else:
        logger.error(
            f"Database of type {database_type} is not supported. Supported types are: {dump_database_methods.keys()}"
        )
