import os

from setuptools import setup, find_packages

from spypi._version import __version__

with open("README.md", "r") as fh:
    long_description = fh.read()

def package_files(*dirs):
    paths = []
    for d in dirs:
        for (path, directories, filenames) in os.walk(d):
            for filename in filenames:
                paths.append(os.path.join('..', path, filename))
    return paths

extra_files = package_files('spypi/resources')
setup_deps = [
          'pyinstaller',
          'wheel',
          'twine'
      ],
setup(name='adobe-serial-tool',
      version=__version__,
      description='Spy Pi',
      long_description=long_description,
      long_description_content_type="text/markdown",
      classifiers=[],
      url='https://github.com/vossenv/spypi',
      maintainer='Danimae Vossen',
      maintainer_email='vossen.dm@gmail.com',
      license='MIT',
      packages=find_packages(),
      package_data={
          'spypi': extra_files,
      },
      install_requires=[
          # 'click',
          # 'click-default-group',
          # 'pyyaml'
      ],
      extras_require={
          'setup': setup_deps,
      },
      setup_requires=setup_deps,
      entry_points={
          # 'console_scripts': [
          #     'askt = adobe_serial_tool.app:cli',
          # ]
      },
      )
