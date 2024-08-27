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


def get_env():
    environment = {}

    env_variables: dict[str, dict[str, Type | bool | str | list | int]] = {
        'TEST': {'type': bool, 'required': False, 'default': False},
        'CRON': {'type': str},
        'START_MANUAL_MANAGEMENT_SERVER': {'type': bool, 'required': False, 'default': True},
        'MANUAL_MANAGEMENT_PORT': {'type': int, 'required': False, 'default': 33399},
        'DATABASE_TYPE': {'type': str, 'enum': ['postgresql', 'mysql', 'clickhouse', 'mongodb']},
        'DATABASE_HOST': {'type': str},
        'DATABASE_NAME': {'type': str},
        'DATABASE_USER': {'type': str, 'required': False, 'default': ''},
        'DATABASE_PASSWORD': {'type': str, 'required': False, 'default': ''},
        'DATABASE_PORT': {'type': int, 'required': False, 'default': 0},
        'AUTH_DATABASE_NAME': {'type': str, 'required': False, 'default': 'admin'},
        'GLACIER_BUCKET_NAME': {'type': str, 'regex': '(?!(^xn--|-s3alias$))^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'},
        'GLACIER_STORAGE_CLASS': {'type': str, 'enum': ['instant', 'flexible', 'deep'], 'default': 'flexible'},
        'GLACIER_EXPIRE_AFTER': {'type': int, 'default': 0},
        'AWS_DEFAULT_REGION': {'type': str},
        'AWS_ACCESS_KEY_ID': {'type': str, 'required': False},
        'AWS_SECRET_ACCESS_KEY': {'type': str, 'required': False},
        'PROJECT_NAME': {'type': str, 'required': False, 'default': gethostname()},
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
                    raise AttributeError(f"Couldn't cast to the {options['type']}. {e.__class__.__name__}: {e}")
            elif options.get('enum') and value.lower() not in options['enum']:
                raise AttributeError(f'Environment value {name} is expected to be one of [{options["possible_values"]}]')
            elif options.get('regex') and re.match(options['regex'], value) is None:
                raise AttributeError(f'Environment value {name} does not match regex expression {options["regex"]}')
            else:
                environment[name] = value

    if environment['DATABASE_PORT'] == 0:
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

