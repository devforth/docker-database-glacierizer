import os
import glob
import gzip
import boto3
import logging
from pathlib import Path

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

def remove_older_dumps(env, dump_path):
    db_type = env.get('DATABASE_TYPE').lower()
    if db_type == 'mongodb':
        file_extension = '.tar.gz'
    elif db_type == 'qdrant':
        file_extension = '.snapshot.gz'
    else:
        file_extension = '.sql.gz'
        
    filename_template = os.path.join(
        env.get("DUMP_PATH_DIR", "/tmp"),
        f'{env.get("DATABASE_TYPE")}_{env.get("DATABASE_NAME")}_*{file_extension}',
    )
    
    clear_all = env.get('CLEAR_ALL_DUMPS', 'false')
    
    for filename_ in glob.glob(filename_template):
        try:
            if clear_all or filename_ != dump_path:
                os.remove(filename_)
                logger.info(f"Removed file: {filename_}")
        except EnvironmentError as error:
            logger.error(f"Error while trying to remove older dumps. {error=}")


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
    template_auth = 'mkdir -p "{dump_path}.folder" && mongodump -h "{host}" --port {port} -u "{user}" -p "{password}" -d "{database}" --authenticationDatabase="{auth_database}" --out "{dump_path}.folder" && tar -czf {dump_path} -C "{dump_path}.folder" . && rm -rf "{dump_path}.folder"'
    template_noauth = 'mkdir -p "{dump_path}.folder" && mongodump -h "{host}" --port {port} -d "{database}" --out "{dump_path}.folder" && tar -czf {dump_path} -C "{dump_path}.folder" . && rm -rf "{dump_path}.folder"'

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

    exit_status = __run_command(f'/bin/bash -c "{dump_command}"')
    if exit_status != 0:
        logger.error("RETURN CODE OF DUMP PROCESS != 0. CHECK OUTPUT ABOVE FOR ERRORS!")
        send_slack_message(environment, "Failed to create DB dump. Please check the error in the container logs.",
                           'FAIL')
        raise Exception('Failed to create dump of database')

    return dump_path

def dump_clickhouse(environment, output_path):
    filename = os.path.basename(output_path) + '.zip'

    client = ClickhouseClient(
        host=environment.get('DATABASE_HOST'),
        user=environment.get('DATABASE_USER'),
        password=environment.get('DATABASE_PASSWORD'),
        database=environment.get('DATABASE_NAME'),
        port=environment.get('DATABASE_PORT'),
        send_receive_timeout=environment.get('CLICKHOUSE_TIMEOUT') # 5 minutes
    )

    backup_query = f'''
        BACKUP DATABASE `{environment.get("DATABASE_NAME")}`
        TO S3(
            'https://{environment.get("GLACIER_BUCKET_NAME")}.s3.amazonaws.com/{filename}', 
            '{environment.get("AWS_ACCESS_KEY_ID")}', 
            '{environment.get("AWS_SECRET_ACCESS_KEY")}'
        )
        SETTINGS 
            compression_method = 'lzma', 
            compression_level = 4,
            s3_storage_class = 'STANDARD';
    '''
    client.execute(backup_query)

    s3 = boto3.client('s3')
    s3.copy(
        CopySource={
            "Bucket": environment.get('GLACIER_BUCKET_NAME'),
            "Key": filename
        },
        Bucket=environment.get('GLACIER_BUCKET_NAME'),
        Key=filename,
        ExtraArgs={
            'StorageClass': storage_class_map[environment.get('GLACIER_STORAGE_CLASS')],
            'MetadataDirective': 'COPY',
        }
    )

    return None

def dump_qdrant(environment, output_path):
    import urllib.request
    import json
    import shutil
    import gzip

    host = environment.get('DATABASE_HOST')
    port = environment.get('DATABASE_PORT')
    api_key = environment.get('QDRANT_API_KEY')
    collection_name = environment.get('DATABASE_NAME')

    headers = {}
    if api_key:
        headers['api-key'] = api_key

    if collection_name:
        snapshot_url = f"http://{host}:{port}/collections/{collection_name}/snapshots?wait=true"
    else:
        snapshot_url = f"http://{host}:{port}/snapshots?wait=true"

    logger.info(f'{datetime.now()}: Creating Qdrant snapshot via REST API')
    req = urllib.request.Request(snapshot_url, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            snapshot_name = data['result']['name']
    except Exception as e:
        logger.error(f"Failed to create Qdrant snapshot: {e}")
        send_slack_message(environment, "Failed to create Qdrant DB dump. Please check the error in the container logs.", 'FAIL')
        raise Exception(f'Failed to create dump of Qdrant database: {e}')

    if collection_name:
        download_url = f"http://{host}:{port}/collections/{collection_name}/snapshots/{snapshot_name}"
    else:
        download_url = f"http://{host}:{port}/snapshots/{snapshot_name}"
        
    logger.info(f'{datetime.now()}: Downloading and compressing Qdrant snapshot {snapshot_name}')
    req_dl = urllib.request.Request(download_url, method="GET", headers=headers)
    dump_path = output_path + '.snapshot.gz'
    try:
        with urllib.request.urlopen(req_dl) as response, gzip.open(dump_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    except Exception as e:
        logger.error(f"Failed to download Qdrant snapshot: {e}")
        send_slack_message(environment, "Failed to download Qdrant DB dump. Please check the error in the container logs.", 'FAIL')
        raise Exception(f'Failed to download dump of Qdrant database: {e}')
        
    try:
        delete_req = urllib.request.Request(download_url, method="DELETE", headers=headers)
        urllib.request.urlopen(delete_req)
        logger.info(f'{datetime.now()}: Successfully deleted Qdrant snapshot from server disk')
    except Exception as e:
        logger.warning(f"Failed to delete Qdrant snapshot from server (this is non-fatal): {e}")

    return dump_path

def prepare_s3_bucket(environment):
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

    glacierizer_current_rule = next(
        filter(lambda r: r['ID'] == 'GLACIERIZER_EXPIRE_AFTER', configuration.get('Rules', [])), None)
    existing_rules = list(filter(lambda r: r['ID'] != 'GLACIERIZER_EXPIRE_AFTER', configuration.get('Rules', [])))

    glacierizer_current_expire = glacierizer_current_rule.get('Expiration', {}).get('Days',
                                                                                None) if glacierizer_current_rule else None
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

def create_dump(environment):
    filename = f'{environment.get("DATABASE_TYPE")}_{environment.get("DATABASE_NAME")}_{datetime.now().strftime("%Y_%m_%d_%H_%M")}'
    dump_dir = environment.get("DUMP_PATH_DIR", "/tmp")
    dump_path = os.path.join(dump_dir, filename)
    
    Path(dump_dir).mkdir(parents=True, exist_ok=True)

    dump_database_methods = {
        'mysql': dump_general('/bin/bash -c \'set -o pipefail; mysqldump -h "{host}" -u "{user}" -p"{password}" --databases "{database}" -P {port} --protocol tcp | gzip -9 > {dump_path}\'', '.sql.gz'),
        'postgresql': dump_general('PGPASSWORD="{password}" pg_dump -h "{host}" -U "{user}" -d "{database}" -p {port} -Fp -Z9 > {dump_path}', '.sql.gz'),
        'mongodb': dump_mongodb,
        'clickhouse': dump_clickhouse,
        'qdrant': dump_qdrant,
    }

    database_type = environment.get('DATABASE_TYPE').lower()
    dump_database_method = dump_database_methods.get(database_type)

    if not dump_database_method:
        raise NotImplemented(f"database of type {database_type} is not supported")

    dump_path = dump_database_method(environment, dump_path)
    return dump_path


def dump_database(environment):
    logger.info(f'Creating backup')

    file_size = 0
    try:
        prepare_s3_bucket(environment)
        dump_path = create_dump(environment)
        logger.info(f'Backup created {dump_path=}')

        if dump_path:
            logger.info(f'Uploading to S3')
            s3 = boto3.client('s3')

            try:
                file_size = os.path.getsize(dump_path)
            except Exception as e:
                logger.error("Failed to get size of file.")
                logger.exception(e)

            with open(dump_path, 'rb') as file:
                logger.info(s3.put_object(
                    Bucket=environment.get('GLACIER_BUCKET_NAME'),
                    Key=os.path.basename(dump_path),
                    Body=file,
                    StorageClass=storage_class_map[environment.get('GLACIER_STORAGE_CLASS')]
                ))

                logger.info('Archive upload done.')
                remove_older_dumps(env = environment, dump_path = dump_path)
                send_slack_message(environment, f"Successfully created and uploaded DB dump ({sizeof_fmt(file_size)}).")

    except Exception as e:
        logger.exception(e)
        send_slack_message(
            environment,
            f"Failed to upload DB dump ({sizeof_fmt(file_size)}) to AWS S3 ({storage_class_map.get(environment.get('GLACIER_STORAGE_CLASS'), 'UNKNOWN')}). Please check the error in the container logs.",
            'FAIL'
        )
