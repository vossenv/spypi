import logging.config
import os

import click
import yaml
from click_default_group import DefaultGroup

from install import get_environment
from spypi.config import load_config, ConfigValidationError, CONFIG_DEFAULTS
from spypi.resources import get_resource


# import cv2


def init_logger(filename=None, level='DEBUG'):
    with open(get_resource("logger_config.yaml")) as cfg:
        data = yaml.safe_load(cfg)
        if filename:
            data['handlers']['file']['filename'] = filename
        else:
            data['loggers']['']['handlers'] = ['console']
        data['loggers']['']['level'] = level.upper()
        logging.config.dictConfig(data)
        return logging.getLogger()


def log_meta(params):
    logging.info("App Version: {}".format(ENV_METADATA['app_version']))
    logging.info("Python Version: {}".format(ENV_METADATA['python_version']))
    logging.info("Platform: {0} / {1}".format(ENV_METADATA['os'], ENV_METADATA['os_version']))
    logging.info("CLI Parameters: " + str(params))


def promt_default_config(filename):
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
        promt_default_config(config_filename)
        exit()
    try:
        cfg = load_config(config_filename)
        init_logger(cfg['logging']['filename'], cfg['logging']['level'])
      #  resolve_depenencies(cfg['hardware']['camera'])
        log_meta(ctx.params)
    except ConfigValidationError as e:
        logger.critical(e)
    except PermissionError:
        click.echo("Failed to install dependency - please re-run using sudo!")



@cli.command(help="Install arducam and openCV")
@click.option('--no-ardu', type=bool, default=False, is_flag=True)
@click.pass_context
def install(ctx, no_ardu):
    pass

    print()

ENV_METADATA = get_environment()
logger = init_logger()

if __name__ == '__main__':
    cli()
