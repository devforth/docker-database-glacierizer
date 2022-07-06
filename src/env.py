import os
from socket import gethostname


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
        'START_MANUAL_MANAGEMENT_SERVER': {'type': bool, 'required': False, 'default': True},
        'MANUAL_MANAGEMENT_PORT': {'type': int, 'required': False, 'default': 33399},
        'DATABASE_TYPE': {'type': str, 'possible_values': ['postgresql', 'mysql', 'clickhouse']},
        'DATABASE_HOST': {'type': str},
        'DATABASE_NAME': {'type': str},
        'DATABASE_USER': {'type': str},
        'DATABASE_PASSWORD': {'type': str},
        'DATABASE_PORT': {'type': int, 'required': False, 'default': 0},
        'GLACIER_VAULT_NAME': {'type': str},
        'AWS_DEFAULT_REGION': {'type': str},
        'AWS_ACCESS_KEY_ID': {'type': str},
        'AWS_SECRET_ACCESS_KEY': {'type': str},
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
                    raise AttributeError(f'Couldn\'t cast to the {options["type"]}: {e}')
            elif options.get('possible_values') and value.lower() not in options['possible_values']:
                raise AttributeError(f'Environment value {name} is expected to be one of [{options["possible_values"]}]')
            else:
                environment[name] = value

    if environment['DATABASE_PORT'] == 0:
        port_map = {
            'mysql': 3306,
            'postgresql': 5432,
            'clickhouse': 9000,
        }
        environment['DATABASE_PORT'] = port_map.get(environment['DATABASE_TYPE'].lower(), 0)

    if environment['DATABASE_PORT'] == 0:
        raise AttributeError(f'Couldn\'t figure out value for DATABASE_PORT. Please specify it as environment value')

    print(environment)

    return environment

