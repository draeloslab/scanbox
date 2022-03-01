#!/usr/bin/env python
# Install script for scanbox python

import os
from os.path import join as pjoin
from setuptools import setup
from setuptools.command.install import install

longdescription = '''Scanbox Neurolabware control'''
datapath = pjoin(os.path.expanduser('~'), 'scanbox')
if not os.path.isdir(datapath):
    os.makedirs(datapath)
    print('Created folder: {0}'.format(datapath))

setup(
  name = 'scanbox',
  version = '0.0',
  author = 'Joao Couto',
  author_email = 'jpcouto@gmail.com',
  description = (longdescription),
  long_description = longdescription,
  license = 'GPL',
  packages = ['scanbox'],
  entry_points = {
        'console_scripts': [
          'scanbox = scanbox.gui:main',        ]
        },
    )
