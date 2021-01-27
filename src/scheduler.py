import os
import boto3
import logging.config
from datetime import datetime

from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BlockingScheduler

logging.config.fileConfig('logging.ini')
logger = logging.getLogger('ddg_scheduler')


def cast_to_type(value, cast_type):
    if type(value) == cast_type:
        return value
    elif cast_type == bool:
        return value.lower() == 'true'
    return cast_type(value)


def get_env():
    environment = {}

    env_variables = {
        'TEST': {'type': bool, 'required': False, 'default': False},
        'CRON': {'type': str},
        'DATABASE_TYPE': {'type': str, 'possible_values': ['postgresql', 'mysql']},
        'DATABASE_HOST': {'type': str},
        'DATABASE_NAME': {'type': str},
        'DATABASE_USER': {'type': str},
        'DATABASE_PASSWORD': {'type': str},
        'GLACIER_VAULT_NAME': {'type': str},
        'AWS_DEFAULT_REGION': {'type': str},
        'AWS_ACCESS_KEY_ID': {'type': str},
        'AWS_SECRET_ACCESS_KEY': {'type': str},
    }

    for name, options in env_variables.items():
        value = os.getenv(name)
        required = options.get('required', True)

        if required and (value is None or len(value) == 0):
            raise AttributeError(f'Environment value {name} is missing or empty')
        elif not required and value is None:
            environment[name] = options.get('default')
        elif value is not None:
            if type(value) != options['type']:
                try:
                    environment[name] = cast_to_type(value, options['type'])
                except Exception as e:
                    raise AttributeError(f'Couldn\'t cast to the {options["type"]}: {e}')
            elif options.get('possible_values') and value.lower() not in options['possible_values']:
                raise AttributeError(f'Environment value {name} is expected to be one of [{options["possible_values"]}]')
            else:
                environment[name] = value
    return environment


def dump_database():
    logger.info(f'{datetime.now()}: Creating backup')

    filename = f'{environment.get("DATABASE_NAME")}_{datetime.now().strftime("%d_%m_%Y")}.sql.gz'
    dump_path = os.path.join('/tmp', filename)

    dump_database_templates = {
        'mysql': 'mysqldump -h {host} -u {user} -p{password} --databases {database} --protocol tcp | gzip -9 > {dump_path}',
        'postgresql': 'PGPASSWORD={password} pg_dump -h {host} -U {user} -d {database} -Fp -Z9 > {dump_path}',
    }

    database_type = environment.get('DATABASE_TYPE').lower()
    dump_database_template = dump_database_templates.get(database_type)

    if dump_database_template:
        dump_command = dump_database_template.format(
            host=environment.get('DATABASE_HOST'),
            user=environment.get('DATABASE_USER'),
            password=environment.get('DATABASE_PASSWORD'),
            database=environment.get('DATABASE_NAME'),
            dump_path=dump_path.format(database=environment.get('DATABASE_NAME')),
        )
        return_code = os.system(dump_command)

        if return_code != 0:
            logger.error("RETURN CODE OF DUMP PROCESS != 0. CHECK OUTPUT ABOVE FOR ERRORS!")
        else:
            try:
                glacier = boto3.client('glacier')
                glacier.create_vault(vaultName=environment.get('GLACIER_VAULT_NAME'))
                with open(dump_path, 'rb') as f:
                    logger.info(glacier.upload_archive(
                        vaultName=environment.get('GLACIER_VAULT_NAME'),
                        archiveDescription=filename,
                        body=f,
                    ))
                    logger.info('Glacier upload done.')
            except Exception as e:
                logger.exception(e)
    else:
        logger.error(f'Database of type {database_type} is not supported. If you see this message something went horribly wrong.')


if __name__ == "__main__":
    environment = get_env()

    if environment.get('TEST'):
        import time
        time.sleep(30)
        dump_database()
    else:
        dumper_scheduler = BlockingScheduler()
        dumper_scheduler.add_job(dump_database, CronTrigger.from_crontab(os.getenv('CRON')))
        dumper_scheduler.start()
