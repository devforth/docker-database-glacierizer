import os
import boto3
import logging.config
from datetime import datetime
from slack_sdk.webhook import WebhookClient

from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers.background import BackgroundScheduler

from server import AuthServer

logging.config.fileConfig('logging.ini')
logger = logging.getLogger('ddg_scheduler')


def sizeof_fmt(num):
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if abs(num) < 1024.0:
            return "%.1f%s" % (num, unit)
        num /= 1024.0
    return "%.1f%s" % (num, 'PiB')


def send_slack_message(environment, message, type='SUCCESS'):
    webhook_url = environment['SLACK_WEBHOOK']
    project_name = environment['PROJECT_NAME']

    color_map = {
        'SUCCESS': '#36a64f',
        'FAIL': '#ee2700',
        'OTHER': '#FFCC00'
    }
    fallback_color = '#808080'

    logger.info(message)

    if project_name and len(project_name) > 0:
        project_name += " "

    if not webhook_url:
        return
    try:
        client = WebhookClient(webhook_url)
        response = client.send(
            attachments=[
                {
                    "color": color_map.get(type, fallback_color),
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"{project_name}Glacierizer"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": message
                            }
                        }
                    ]
                }
            ]
        )
    except Exception as e:
        logger.exception(e)


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
        'START_SERVER': {'type': bool, 'required': False, 'default': True},
        'SERVER_PORT': {'type': int, 'required': False, 'default': 33399},
        'SERVER_BASIC_AUTH_USER': {'type': str, 'required': False, 'default': 'admin'},
        'SERVER_BASIC_AUTH_PASSWORD': {'type': str, 'required': False, 'default': 'admin'},
        'DATABASE_TYPE': {'type': str, 'possible_values': ['postgresql', 'mysql']},
        'DATABASE_HOST': {'type': str},
        'DATABASE_NAME': {'type': str},
        'DATABASE_USER': {'type': str},
        'DATABASE_PASSWORD': {'type': str},
        'DATABASE_PORT': {'type': int, 'required': False, 'default': 0},
        'GLACIER_VAULT_NAME': {'type': str},
        'AWS_DEFAULT_REGION': {'type': str},
        'AWS_ACCESS_KEY_ID': {'type': str},
        'AWS_SECRET_ACCESS_KEY': {'type': str},
        'PROJECT_NAME': {'type': str, 'required': False},
        'SLACK_WEBHOOK': {'type': str, 'required': False}
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

    if environment['DATABASE_PORT'] == 0:
        port_map = {
            'mysql': 3306,
            'postgresql': 5432,
        }
        environment['DATABASE_PORT'] = port_map.get(environment['DATABASE_TYPE'].lower(), 0)

    if environment['DATABASE_PORT'] == 0:
        raise AttributeError(f'Couldn\'t figure out value for DATABASE_PORT. Please specify it as environment value')

    return environment


def dump_database():
    logger.info(f'{datetime.now()}: Creating backup')

    filename = f'{environment.get("DATABASE_NAME")}_{datetime.now().strftime("%d_%m_%Y")}.sql.gz'
    dump_path = os.path.join('/tmp', filename)

    dump_database_templates = {
        'mysql': 'set -o pipefail; mysqldump -h "{host}" -u "{user}" -p"{password}" --databases "{database}" -P {port} --protocol tcp | gzip -9 > {dump_path}',
        'postgresql': 'PGPASSWORD="{password}" pg_dump -h "{host}" -U "{user}" -d "{database}" -p {port} -Fp -Z9 > {dump_path}',
    }

    database_type = environment.get('DATABASE_TYPE').lower()
    dump_database_template = dump_database_templates.get(database_type)

    if dump_database_template:
        dump_command = dump_database_template.format(
            host=environment.get('DATABASE_HOST'),
            user=environment.get('DATABASE_USER'),
            password=environment.get('DATABASE_PASSWORD'),
            database=environment.get('DATABASE_NAME'),
            port=environment.get('DATABASE_PORT'),
            dump_path=dump_path.format(database=environment.get('DATABASE_NAME')),
        )
        wait_exit_status = os.system(dump_command)
        exit_status = os.waitstatus_to_exitcode(wait_exit_status)

        if wait_exit_status != 0 or exit_status != 0:
            logger.error("RETURN CODE OF DUMP PROCESS != 0. CHECK OUTPUT ABOVE FOR ERRORS!")
            send_slack_message(environment, "Failed to create DB dump. Please check the error in the container logs.", 'FAIL')
        else:
            file_size = 0

            try:
                file_size = os.path.getsize(dump_path)
            except Exception as e:
                logger.error("Failed to get size of file.")
                logger.exception(e)

            logger.info(f'{datetime.now()}: Backup created. Uploading to glacier')
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
                    send_slack_message(environment, f"Successfully created and uploaded DB dump ({sizeof_fmt(file_size)}).")
            except Exception as e:
                logger.exception(e)
                send_slack_message(environment, f"Failed to upload DB dump ({sizeof_fmt(file_size)}) to AWS Glacier. Please check the error in the container logs.", 'FAIL')
    else:
        logger.error(f'Database of type {database_type} is not supported. If you see this message something went horribly wrong.')


if __name__ == "__main__":
    environment = get_env()

    if environment.get('TEST'):
        import time
        time.sleep(10)
        dump_database()
        time.sleep(300)
    else:
        dumper_scheduler = BackgroundScheduler()
        dumper_scheduler.add_job(dump_database, CronTrigger.from_crontab(environment.get('CRON')))
        dumper_scheduler.start()

        if environment.get('START_SERVER'):
            def on_get():
                send_slack_message(environment, 'Backup triggered from server', 'OTHER')
                dump_database()

            server = AuthServer(('', environment.get('SERVER_PORT')), logger)
            server.set_auth(environment.get('SERVER_BASIC_AUTH_USER'), environment.get('SERVER_BASIC_AUTH_PASSWORD'))
            server.set_on_get(on_get)
            server.serve_forever()
