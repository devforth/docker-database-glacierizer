import os
import boto3
import logging.config
from datetime import datetime

from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BlockingScheduler

logging.config.fileConfig('logging.ini')
logger = logging.getLogger('ddgc_scheduler')


def check_env():
    env_variables = {
        'CRON': {'type': str},
        'DATABASE_TYPE': {'type': str, 'possible_values': ['postgresql', 'mysql']},
        'DATABASE_HOST': {'type': str},
        'DATABASE_NAME': {'type': str},
        'DATABASE_USER': {'type': str},
        'DATABASE_PASSWORD': {'type': str},
        'GLACIER_VAULT_NAME': {'type': str},
        'AWS_S3_REGION_NAME': {'type': str},
        'AWS_ACCESS_KEY_ID': {'type': str},
        'AWS_SECRET_ACCESS_KEY': {'type': str},
    }

    for name, options in env_variables.items():
        value = os.getenv(name)

        if options.get('required', True) and (value is None or len(value) == 0):
            raise AttributeError(f'Environment value {name} is missing or empty')
        elif value is not None:
            if type(value) != options['type']:
                raise AttributeError(f'Environment value {name} is expected to be of \'{options["type"]}\' type, got \'{type(value)}\' instead')
            elif options.get('possible_values') and value.lower() not in options['possible_values']:
                raise AttributeError(f'Environment value {name} is expected to be one of [{options["possible_values"]}]')


def dump_database():
    logger.info(f'{datetime.now()}: Creating backup')

    filename = f'{os.getenv("DATABASE_NAME")}_{datetime.now().strftime("%d_%m_%Y")}.sql.gz'
    dump_path = os.path.join('/tmp', filename)

    dump_database_templates = {
        'mysql': 'mysqldump -h {host} -u {user} -p{password} --databases {database} | gzip -9 > {dump_path}',
        'postgresql': 'PGPASSWORD={password} pg_dump -h {host} -U {user} -d {database} -Fp -Z9 > {dump_path}',
    }

    database_type = os.getenv('DATABASE_TYPE').lower()
    dump_database_template = dump_database_templates.get(database_type)

    if dump_database_template:
        dump_command = dump_database_template.format(
            host=os.getenv('DATABASE_HOST'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASSWORD'),
            database=os.getenv('DATABASE_NAME'),
            dump_path=dump_path.format(database=os.getenv('DATABASE_NAME')),
        )
        return_code = os.system(dump_command)

        if return_code != 0:
            logger.error("RETURN CODE OF DUMP PROCESS != 0. CHECK OUTPUT ABOVE FOR ERRORS!")
        else:
            try:
                glacier = boto3.client('glacier')
                glacier.create_vault(vaultName=os.getenv('GLACIER_VAULT_NAME'))
                with open(dump_path, 'rb') as f:
                    logger.info(glacier.upload_archive(
                        vaultName=os.getenv('GLACIER_VAULT_NAME'),
                        archiveDescription=filename,
                        body=f,
                    ))
                    logger.info('Glacier upload done.')
            except Exception as e:
                logger.exception(e)
    else:
        logger.error(f'Database of type {database_type} is not supported. If you see this message something went horribly wrong.')


if __name__ == "__main__":
    check_env()

    dumper_scheduler = BlockingScheduler()
    dumper_scheduler.add_job(dump_database, CronTrigger.from_crontab(os.getenv('CRON')))
    dumper_scheduler.start()

