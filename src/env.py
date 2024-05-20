import os
import re
from socket import gethostname
from typing import Type


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
                return cast_to_type(value, options['type'])
            except Exception as e:
                raise AttributeError(f"Couldn't cast to the {options['type']}. {e.__class__.__name__}: {e}")
        elif options.get('enum') and value.lower() not in options['enum']:
            raise AttributeError(f'Environment value {name} is expected to be one of [{options["possible_values"]}]')
        elif options.get('regex') and re.match(options['regex'], value) is None:
            raise AttributeError(f'Environment value {name} does not match regex expression {options["regex"]}')
        else:
            return value

def get_env():
    environment = {}

    env_variables_type: dict[str, dict] = {
        'DATABASE_TYPE': {'type': str, 'enum': ['postgresql', 'mysql', 'clickhouse', 'mongodb', 'sqlite', 'files']},
    }

    for name, options in env_variables_type.items():
        environment[name] = parse_env(name, options)

    env_variables_database: dict[str, dict] = {
        'DATABASE_TYPE': {'type': str, 'enum': ['postgresql', 'mysql', 'clickhouse', 'mongodb']},
        'DATABASE_HOST': {'type': str},
        'DATABASE_NAME': {'type': str},
        'DATABASE_USER': {'type': str, 'required': False, 'default': ''},
        'DATABASE_PASSWORD': {'type': str, 'required': False, 'default': ''},
        'DATABASE_PORT': {'type': int, 'required': False, 'default': 0},
        'AUTH_DATABASE_NAME': {'type': str, 'required': False, 'default': 'admin'},
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
        'START_MANUAL_MANAGEMENT_SERVER': {'type': bool, 'required': False, 'default': True},
        'MANUAL_MANAGEMENT_PORT': {'type': int, 'required': False, 'default': 33399},
        'GLACIER_BUCKET_NAME': {'type': str, 'regex': '(?!(^xn--|-s3alias$))^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'},
        'GLACIER_STORAGE_CLASS': {'type': str, 'enum': ['instant', 'flexible', 'deep'], 'default': 'flexible'},
        'GLACIER_EXPIRE_AFTER': {'type': int, 'default': 0},
        'AWS_DEFAULT_REGION': {'type': str},
        'AWS_ACCESS_KEY_ID': {'type': str},
        'AWS_SECRET_ACCESS_KEY': {'type': str},
        'PROJECT_NAME': {'type': str, 'required': False, 'default': gethostname()},
        'SLACK_WEBHOOK': {'type': str, 'required': False},
        'DUMP_NAME': {'type': str, 'required': False},
        **(
            env_variables_files if environment['DATABASE_TYPE'] == 'files'
            else env_variables_sqlite if environment['DATABASE_TYPE'] == 'sqlite'
            else env_variables_database
        ),
    }

    for name, options in env_variables.items():
        environment[name] = parse_env(name, options)

    if environment.get('DATABASE_PORT', None) == 0:
        port_map = {
            'mysql': 3306,
            'postgresql': 5432,
            'clickhouse': 9000,
            'mongodb': 27017,
        }
        environment['DATABASE_PORT'] = port_map.get(environment['DATABASE_TYPE'].lower(), 0)

        if environment['DATABASE_PORT'] == 0:
            raise AttributeError(f"Couldn't figure out value for DATABASE_PORT. Please specify it in environment values")

    return environment

