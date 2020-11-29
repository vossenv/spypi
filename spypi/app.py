import logging.config
import os
import platform
import site

import click
import distro
import requests
import yaml
from click_default_group import DefaultGroup

from spypi._version import __version__
from spypi.config import load_config, ConfigValidationError, CONFIG_DEFAULTS
from spypi.resources import get_resource

libraries = [
    'https://github.com/ArduCAM/ArduCAM_USB_Camera_Shield/raw/master/'
    'RaspberryPi/Python/External_trigger_demo/ArducamSDK.so',
    'https://github.com/ArduCAM/ArduCAM_USB_Camera_Shield/raw/'
    'master/RaspberryPi/Python/External_trigger_demo/ArducamSDK.cpython-37m-arm-linux-gnueabihf.so'
]


def get_environment():
    env_os = platform.system()
    if env_os.lower() == "windows":
        env_os_version = platform.version()
    elif env_os.lower() == "linux":
        vers = distro.linux_distribution()
        env_os = vers[0]
        env_os_version = vers[1] + " " + vers[2]
    else:
        raise EnvironmentError("Unknown / unsupported platform: {}".format(env_os))
    return {
        'app_version': __version__,
        'python_version': platform.python_version(),
        'os': env_os,
        'os_version': env_os_version
    }


def download_library(url, destination):
    name = url.split('/')[-1]
    filename = os.path.join(destination, name)
    logger.info("Downloading external library '{0}' to '{1}'".format(name, destination))
    res = requests.get(url)
    with open(filename, 'wb') as f:
        f.write(res.content)
    logger.info("Library installed succesfully!")


def resolve_depenencies(camera_type):
    is_raspbian = 'raspbian' in ENV_METADATA['os'].lower()

    if not is_raspbian and camera_type == 'arducam':
        raise EnvironmentError("Arducam must be run on Pi/Raspbian")

    if camera_type == 'arducam':
        try:
            import ArducamSDK
        except ModuleNotFoundError:
            if click.confirm("Arducam library was not found.  Download now?"):
                libdir = site.getsitepackages()[0]
                for l in libraries:
                    download_library(l, libdir)
            else:
                click.echo("Please manually install libraries to dist-packages continue: ")
                for l in libraries:
                    click.echo(l)
                exit()


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
        resolve_depenencies(cfg['hardware']['camera'])
        log_meta(ctx.params)
    except ConfigValidationError as e:
        logger.critical(e)
    except PermissionError:
        click.echo("Failed to install dependency - please re-run using sudo!")


ENV_METADATA = get_environment()
logger = init_logger()

if __name__ == '__main__':
    cli()
