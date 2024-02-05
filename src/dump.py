import os
import gzip
import boto3
import logging

import botocore.exceptions

from datetime import datetime
from slack import send_slack_message, sizeof_fmt
from clickhouse_driver import Client as ClickhouseClient


logger = logging.getLogger('ddgscheduler')

storage_class_map = {
    'instant': 'GLACIER_IR',
    'flexible': 'GLACIER',
    'deep': 'DEEP_ARCHIVE',
}


def __run_command(command: str):
    logger.info(f'{datetime.now()}: Running dm command: {command}')

    wait_exit_status = os.system(command)
    exit_status = os.waitstatus_to_exitcode(wait_exit_status)

    return exit_status


def dump_general(template, file_ext):
    def wrapper(environment, output_path):
        dump_path = output_path + file_ext
        dump_command = template.format(
            host=environment.get('DATABASE_HOST'),
            user=environment.get('DATABASE_USER'),
            password=environment.get('DATABASE_PASSWORD'),
            database=environment.get('DATABASE_NAME'),
            auth_database=environment.get('AUTH_DATABASE_NAME'),
            port=environment.get('DATABASE_PORT'),
            dump_path=dump_path,
        )

        exit_status = __run_command(dump_command)

        if exit_status != 0:
            logger.error("RETURN CODE OF DUMP PROCESS != 0. CHECK OUTPUT ABOVE FOR ERRORS!")
            send_slack_message(environment, "Failed to create DB dump. Please check the error in the container logs.", 'FAIL')
            raise Exception('Failed to create dump of database')

        return dump_path

    return wrapper


def dump_mongodb(environment, output_path):
    template_auth = '/bin/bash -c \'mongodump -h "{host}" --port {port} -u "{user}" -p "{password}" -d "{database}" --authenticationDatabase="{auth_database}" --out "{dump_path}.folder" && tar -czf {dump_path} -C "{dump_path}.folder" . && rm -rf "{dump_path}.folder"\''
    template_noauth = '/bin/bash -c \'mongodump -h "{host}" --port {port} -d "{database}" --out "{dump_path}.folder" && tar -czf {dump_path} -C "{dump_path}.folder" . && rm -rf "{dump_path}.folder"\''

    dump_path = output_path + '.tar.gz'

    if environment.get('DATABASE_USER') == '' and environment.get('DATABASE_PASSWORD') == '':
        template = template_noauth
    else:
        template = template_auth

    dump_command = template.format(
        host=environment.get('DATABASE_HOST'),
        user=environment.get('DATABASE_USER'),
        password=environment.get('DATABASE_PASSWORD'),
        database=environment.get('DATABASE_NAME'),
        auth_database=environment.get('AUTH_DATABASE_NAME'),
        port=environment.get('DATABASE_PORT'),
        dump_path=dump_path,
    )

    exit_status = __run_command(dump_command)
    if exit_status != 0:
        logger.error("RETURN CODE OF DUMP PROCESS != 0. CHECK OUTPUT ABOVE FOR ERRORS!")
        send_slack_message(environment, "Failed to create DB dump. Please check the error in the container logs.",
                           'FAIL')
        raise Exception('Failed to create dump of database')

    return dump_path


def dump_clickhouse(environment, output_path):
    dump_path = output_path + '.sql.gz'
    def stringify_row(row):
        new_row = []

        for v in row:
            if type(v) == datetime:
                v: datetime
                new_row.append(v.strftime('%Y-%m-%d %H:%M:%S'))
            else:
                new_row.append(str(v))

        return new_row

    client = ClickhouseClient(
        host=environment.get('DATABASE_HOST'),
        user=environment.get('DATABASE_USER'),
        password=environment.get('DATABASE_PASSWORD'),
        database=environment.get('DATABASE_NAME'),
        port=environment.get('DATABASE_PORT'),
    )

    available_tables = list(map(lambda x: x[0], client.execute(f'SHOW TABLES IN `{environment.get("DATABASE_NAME")}`')))

    dump_output = ""

    for table in available_tables:
        create_query = client.execute(f'SHOW CREATE TABLE `{table}`')[0][0]
        dump_output += create_query + ';\n'

    dump_output += "\n\n"

    for table in available_tables:
        insert_query = client.execute(f"SELECT * FROM {table}")

        dump_output += f'INSERT INTO `{table}` FORMAT TSV'

        for row in insert_query:
            dump_output += '\n' + '\t'.join(stringify_row(row))

        dump_output += ';\n\n'

    with gzip.GzipFile(dump_path, 'w+') as f:
        f.write(dump_output.encode())

    return dump_path


def dump_database(environment):
    logger.info(f'{datetime.now()}: Creating backup')

    filename = f'{environment.get("DATABASE_TYPE")}_{environment.get("DATABASE_NAME")}_{datetime.now().strftime("%Y_%m_%d")}'
    dump_path = os.path.join('/tmp', filename)

    dump_database_methods = {
        'mysql': dump_general('/bin/bash -c \'set -o pipefail; mysqldump -h "{host}" -u "{user}" -p"{password}" --databases "{database}" -P {port} --protocol tcp | gzip -9 > {dump_path}\'', '.sql.gz'),
        'postgresql': dump_general('PGPASSWORD="{password}" pg_dump -h "{host}" -U "{user}" -d "{database}" -p {port} -Fp -Z9 > {dump_path}', 'sql.gz'),
        'mongodb': dump_mongodb,
        'clickhouse': dump_clickhouse,
    }

    database_type = environment.get('DATABASE_TYPE').lower()
    dump_database_method = dump_database_methods.get(database_type)

    if dump_database_method:
        dump_path = dump_database_method(environment, dump_path)

        file_size = 0
        try:
            file_size = os.path.getsize(dump_path)
        except Exception as e:
            logger.error("Failed to get size of file.")
            logger.exception(e)

        logger.info(f'{datetime.now()}: Backup created. Uploading to S3')
        try:
            s3 = boto3.client('s3')
            try:
                region = environment.get('AWS_DEFAULT_REGION')
                s3.create_bucket(
                    Bucket=environment.get('GLACIER_BUCKET_NAME'),
                    **({'CreateBucketConfiguration': {'LocationConstraint': region}} if region != 'us-east-1' else {}),
                )
            except (s3.exceptions.BucketAlreadyExists, s3.exceptions.BucketAlreadyOwnedByYou):
                pass

            try:
                configuration = s3.get_bucket_lifecycle_configuration(
                    Bucket=environment.get('GLACIER_BUCKET_NAME')
                )
            except botocore.exceptions.ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'NoSuchLifecycleConfiguration':
                    configuration = {}
                else:
                    raise

            glacierizer_current_rule = next(filter(lambda r: r['ID'] == 'GLACIERIZER_EXPIRE_AFTER', configuration.get('Rules', [])), None)
            existing_rules = list(filter(lambda r: r['ID'] != 'GLACIERIZER_EXPIRE_AFTER', configuration.get('Rules', [])))

            glacierizer_current_expire = glacierizer_current_rule.get('Expire', {}).get('Days', None) if glacierizer_current_rule else None
            glacierizer_new_expire = environment.get('GLACIER_EXPIRE_AFTER')

            glacierizer_rule_enabled = glacierizer_new_expire > 0
            glacierizer_rule_changed = glacierizer_current_expire != glacierizer_new_expire

            glacierizer_new_rule = None
            if glacierizer_rule_enabled and glacierizer_rule_changed:
                glacierizer_new_rule = {
                    'ID': 'GLACIERIZER_EXPIRE_AFTER',
                    'Status': 'Enabled',
                    'Expiration': {
                        'Days': glacierizer_new_expire,
                    },
                    'Filter': {},
                }

            if glacierizer_new_rule:
                s3.put_bucket_lifecycle_configuration(
                    Bucket=environment.get('GLACIER_BUCKET_NAME'),
                    LifecycleConfiguration={
                        'Rules': [*existing_rules, glacierizer_new_rule]
                    }
                )
            elif glacierizer_rule_enabled is False and glacierizer_current_rule is not None:
                if len(existing_rules) == 0:
                    s3.delete_bucket_lifecycle(
                        Bucket=environment.get('GLACIER_BUCKET_NAME')
                    )
                else:
                    s3.put_bucket_lifecycle_configuration(
                        Bucket=environment.get('GLACIER_BUCKET_NAME'),
                        LifecycleConfiguration={
                            'Rules': existing_rules
                        }
                    )

            with open(dump_path, 'rb') as file:
                logger.info(s3.put_object(
                    Bucket=environment.get('GLACIER_BUCKET_NAME'),
                    Key=filename,
                    Body=file,
                    StorageClass=storage_class_map[environment.get('GLACIER_STORAGE_CLASS')]
                ))
                logger.info('Archive upload done.')
                send_slack_message(environment, f"Successfully created and uploaded DB dump ({sizeof_fmt(file_size)}).")
        except Exception as e:
            logger.exception(e)
            send_slack_message(
                environment,
                f"Failed to upload DB dump ({sizeof_fmt(file_size)}) to AWS S3 ({storage_class_map.get(environment.get('GLACIER_STORAGE_CLASS'), 'UNKNOWN')}). Please check the error in the container logs.",
                'FAIL'
            )
    else:
        logger.error(f'Database of type {database_type} is not supported. Supported types are: {dump_database_methods.keys()}')
