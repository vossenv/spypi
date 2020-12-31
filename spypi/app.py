import importlib
import logging.config
import os
import sys

import click
import yaml
from click_default_group import DefaultGroup

from spypi.config import load_config, ConfigValidationError, CONFIG_DEFAULTS
from spypi.error import ImageReadException
from spypi.utils import get_environment, init_logger, is_windows, show_image

if not is_windows():
    sys.path.insert(0, '/usr/local/lib')
    sys.path.insert(0, '/usr/lib/python37.zip')
    sys.path.insert(0, '/usr/local/lib/python3.7/dist-packages')
    try:
        importlib.import_module('cv2')
        importlib.import_module('ArducamSDK')
        importlib.import_module('picamera')
    except ImportError as e:
        click.echo("Unable to import {} - have you run the install script?".format(e))
        click.echo("Find it here: https://github.com/vossenv/spypi")
        exit()
else:
    sys.path.insert(0, os.path.abspath('./lib'))

from spypi.camera import Camera, FrameViewer

logger = init_logger({})


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
        init_logger(cfg['logging'])
        log_meta(ctx.params, cfg)
        init_process(cfg)
    except ConfigValidationError as e:
        logger.critical(e)
        exit()


def init_process(cfg):
    c = Camera.create(cfg['hardware'])
    FrameViewer(c)


if __name__ == '__main__':
    cli()
