import logging.config

import click
import yaml
from click_default_group import DefaultGroup

from spypi.resources import get_resource

with open(get_resource("logger_config.yaml")) as cfg:
    logging.config.dictConfig(yaml.safe_load(cfg))
    logger = logging.getLogger()
    logger.info("------------------------------- Starting New Run -------------------------------")


def log_params(params):
    logger.info("Parameters: " + str(params))


@click.group(cls=DefaultGroup, default='run', default_if_no_args=True)
@click.pass_context
def cli(ctx):
    ctx.obj = {'help': ctx.get_help()}


@cli.command(
    help="Spypy help text",
    context_settings=dict(max_content_width=400))
@click.pass_context
@click.option('-k', '--key',
              default=False,
              is_flag=True,
              help="XXXXXXXXXXXXX")
def run(ctx, key):
    log_params(ctx.params)
    click.echo("Option:  " + str(key))


if __name__ == '__main__':
    cli()
