import importlib
import logging.config
import logging.config
import os
import sys

import click
import yaml
from click_default_group import DefaultGroup

from spypi.config import load_config, ConfigValidationError, CONFIG_DEFAULTS
from spypi.resources import get_environment
from spypi.resources import get_resource

lib_paths = [
    '/usr/local/lib',
    '/usr/local/lib/python3.7/dist-packages'
]

for l in lib_paths:
    if l not in sys.path:
        sys.path.insert(0, l)
try:
    importlib.import_module('cv2')
    importlib.import_module('ArducamSDK')
except ImportError:
    click.echo("Unable to import CV2 - have you run the install script?")
    click.echo("Find it here: https://github.com/vossenv/spypi")
    exit()


def init_logger(filename=None, level='DEBUG'):
    with open(get_resource("logger_config.yaml")) as cfg:
        data = yaml.safe_load(cfg)
        if filename:
            data['handlers']['file']['filename'] = filename
        else:
            data['handlers'].pop('file')
            data['loggers']['']['handlers'] = ['console']
        data['loggers']['']['level'] = level.upper()
        logging.config.dictConfig(data)
        return logging.getLogger()


logger = init_logger()


def log_meta(params, cfg):
    meta = get_environment()
    logging.info("App Version: {}".format(meta['app_version']))
    logging.info("Python Version: {}".format(meta['python_version']))
    logging.info("Platform: {0} / {1}".format(meta['os'], meta['os_version']))
    logging.info("CLI Parameters: " + str(params))
    logging.info("Options: {}".format(cfg))


def prompt_default_config(filename):
    if click.confirm("The specified configuration file '{}' does not exist.\n"
                     "Would you like to initialize the default configuration file with this name?".format(filename)):
        with open(filename, 'w') as f:
            yaml.safe_dump(CONFIG_DEFAULTS, f)
        click.echo("Generated: {}".format(filename))


@click.group(cls=DefaultGroup, default='run', default_if_no_args=True, help="Spypy help text")
@click.pass_context
def cli(ctx):
    ctx.obj = {'help': ctx.get_help()}


@cli.command(
    help="Start the process",
    context_settings=dict(max_content_width=400))
@click.pass_context
@click.option('-c', '--config-filename', default='config.yaml', type=str)
def run(ctx, config_filename):
    if not os.path.exists(config_filename):
        prompt_default_config(config_filename)
        exit()
    try:
        ctx.params['config_filename'] = config_filename = os.path.abspath(config_filename)
        cfg = load_config(config_filename)
        init_logger(cfg['logging']['filename'], cfg['logging']['level'])
        log_meta(ctx.params, cfg)

    except ConfigValidationError as e:
        logger.critical(e)


if __name__ == '__main__':
    cli()
