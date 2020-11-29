import json
import logging.config

import click
import yaml
from click_default_group import DefaultGroup

from spypi.config import load_config, ConfigValidationError
from spypi.resources import get_resource


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


logger = init_logger()


def log_params(params):
    logging.info("Parameters: " + str(params))


@click.group(cls=DefaultGroup, default='run', default_if_no_args=True, help="Spypy help text")
@click.pass_context
def cli(ctx):
    ctx.obj = {'help': ctx.get_help()}


@cli.command(
    help="Start the process",
    context_settings=dict(max_content_width=400))
@click.pass_context
@click.option('-c', '--config-filename', default='config.yaml', type=click.Path(exists=True))
def run(ctx, config_filename):
    try:
        cfg = load_config(config_filename)
        init_logger(cfg['logging']['filename'], cfg['logging']['level'])
    except ConfigValidationError as e:
        logger.critical(e)
    log_params(ctx.params)

    print()


if __name__ == '__main__':
    cli()
