import yaml
from schema import Schema


def config_schema() -> Schema:
    from schema import And, Optional, Or, Regex
    return Schema({
        'hardware':{
            'frame_width': int
        }

        # 'identity_source': {
        #     'connector': And(str, len),
        #     'type': Or('csv', 'okta', 'ldap', 'adobe_console'), #TODO: single "source of truth" for these options
        # },
        # 'user_sync': {
        #     'create_users': bool,
        #     'deactivate_users': bool,
        #     'sign_only_limit': Or(int, Regex(r'^\d+%$')),
        # },
        # 'logging': {
        #     'log_to_file': bool,
        #     'file_log_directory': And(str, len),
        #     'file_log_name_format': And(str, len),
        #     'file_log_level': Or('info', 'debug'), #TODO: what are the valid values here?
        #     'console_log_level': Or('info', 'debug'), #TODO: what are the valid values here?
        # },
        # 'invocation_defaults': {
        #     'users': Or('mapped', 'all'), #TODO: single "source of truth" for these options
        #     #'directory_group_filter': Or('mapped', 'all', None)
        # }
    })

def load_config(path):

    with open(path) as f:
        cfg = yaml.safe_load(f)
    _validate(cfg)
    return cfg


def _validate(raw_config: dict):
    from schema import SchemaError
    try:
        config_schema().validate(raw_config)
    except SchemaError as e:
        raise ConfigValidationError(e.code) from e


class ConfigValidationError(Exception):
    def __init__(self, message):
        super(ConfigValidationError, self).__init__(message)