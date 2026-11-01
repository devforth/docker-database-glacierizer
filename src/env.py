import os
import re
import logging
from socket import gethostname
from typing import Type

logger = logging.getLogger('ddgscheduler')


def cast_to_type(value, cast_type):
    if type(value) == cast_type:
        return value
    elif cast_type == bool:
        return value.lower() == 'true'
    return cast_type(value)

def parse_env(name: str, options: dict[str, Type | bool | str | list | int]):
    value = os.getenv(name)
    required = options.get('required', True)

    if required and (value is None or len(value) == 0):
        raise AttributeError(f'Environment value {name} is missing or empty')
    elif not required and value is None:
        return options.get('default')
    elif value is not None:
        if type(value) != options['type']:
            try:
                value = cast_to_type(value, options['type'])
            except Exception as e:
                raise AttributeError(f"Couldn't cast to the {options['type']}. {e.__class__.__name__}: {e}")
        elif options.get('enum') and value.lower() not in options['enum']:
            raise AttributeError(f'Environment value {name} is expected to be one of {options["enum"]}')
        elif options.get('regex') and re.match(options['regex'], value) is None:
            raise AttributeError(f'Environment value {name} does not match regex expression {options["regex"]}')

        if 'min' in options and value < options['min']:
            raise AttributeError(f"Environment value {name} must be >= {options['min']}")
        if 'max' in options and value > options['max']:
            raise AttributeError(f"Environment value {name} must be <= {options['max']}")

        return value

def get_env():
    environment = {}

    env_variables_type: dict[str, dict] = {
        'DATABASE_TYPE': {'type': str, 'enum': ['postgresql', 'mysql', 'clickhouse', 'mongodb', 'qdrant', 'sqlite', 'files']},
    }

    for name, options in env_variables_type.items():
        environment[name] = parse_env(name, options)

    database_type = environment['DATABASE_TYPE'].lower()

    env_variables_database: dict[str, dict] = {
        'DATABASE_TYPE': {'type': str, 'enum': ['postgresql', 'mysql', 'clickhouse', 'mongodb', 'qdrant']},
        'DATABASE_HOST': {'type': str},
        'DATABASE_NAME': {'type': str, 'required': False, 'default': ''},
        'DATABASE_USER': {'type': str, 'required': False, 'default': ''},
        'DATABASE_PASSWORD': {'type': str, 'required': False, 'default': ''},
        'QDRANT_API_KEY': {'type': str, 'required': False, 'default': ''},
        'DATABASE_PORT': {'type': int, 'required': False, 'default': 0},
        'AUTH_DATABASE_NAME': {'type': str, 'required': False, 'default': 'admin'},
        'CLICKHOUSE_TIMEOUT': {'type': int, 'required': False, 'default': 300},
    }

    env_variables_sqlite: dict[str, dict] = {
        'DATABASE_TYPE': {'type': str, 'enum': ['sqlite']},
        'DATABASE_PATH': {'type': str},
    }

    env_variables_files: dict[str, dict] = {
        'DATABASE_TYPE': {'type': str, 'enum': ['files']},
        'FILES_PATH': {'type': str},
    }

    env_variables: dict[str, dict] = {
        'TEST': {'type': bool, 'required': False, 'default': False},
        'CRON': {'type': str},
        'START_MANUAL_MANAGEMENT_SERVER': {'type': bool, 'required': False, 'default': False},
        'MANUAL_MANAGEMENT_HOST': {'type': str, 'required': False, 'default': '127.0.0.1'},
        'MANUAL_MANAGEMENT_PORT': {'type': int, 'required': False, 'default': 33399},
        'MANUAL_MANAGEMENT_TOKEN': {'type': str, 'required': False},
        'GLACIER_BUCKET_NAME': {'type': str, 'regex': '(?!(^xn--|-s3alias$))^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'},
        'GLACIER_STORAGE_CLASS': {'type': str, 'enum': ['instant', 'flexible', 'deep'], 'required': False, 'default': 'flexible'},
        'GLACIER_EXPIRE_AFTER': {'type': int, 'required': False, 'default': 0},
        'AWS_DEFAULT_REGION': {'type': str},
        'AWS_ACCESS_KEY_ID': {'type': str, 'required': False},
        'AWS_SECRET_ACCESS_KEY': {'type': str, 'required': False},
        'PROJECT_NAME': {'type': str, 'required': False, 'default': gethostname()},
        'SLACK_WEBHOOK': {'type': str, 'required': False},
        'LOCAL_DUMPS_COUNT': {'type': int, 'required': False, 'default': 1, 'min': 0, 'max': 20},
        'DUMP_PATH_DIR': {'type': str, 'required': False, 'default': '/tmp'},
        'DUMP_NAME': {'type': str, 'required': False},
        **(
            env_variables_files if database_type == 'files'
            else env_variables_sqlite if database_type == 'sqlite'
            else env_variables_database
        ),
    }

    for name, options in env_variables.items():
        environment[name] = parse_env(name, options)

    if database_type not in ('qdrant', 'sqlite', 'files') and not environment.get('DATABASE_NAME'):
        raise AttributeError("Environment value DATABASE_NAME is missing or empty")

    if environment['START_MANUAL_MANAGEMENT_SERVER'] and not environment.get('MANUAL_MANAGEMENT_TOKEN'):
        raise AttributeError("Environment value MANUAL_MANAGEMENT_TOKEN is missing or empty. It is required when START_MANUAL_MANAGEMENT_SERVER is true")

    if database_type == 'qdrant' and not environment.get('QDRANT_API_KEY'):
        logger.warning("Environment variable QDRANT_API_KEY is not set. Are you sure your database is public?")

    if environment.get('DATABASE_PORT', None) == 0:
        port_map = {
            'mysql': 3306,
            'postgresql': 5432,
            'clickhouse': 9000,
            'mongodb': 27017,
            'qdrant': 6333,
        }
        environment['DATABASE_PORT'] = port_map.get(database_type, 0)

        if environment['DATABASE_PORT'] == 0:
            raise AttributeError(f"Couldn't figure out value for DATABASE_PORT. Please specify it in environment values")

    return environment
