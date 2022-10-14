from setuptools import setup
from setuptools.command.install import install
import sys
import os
import time
import atexit
import traceback
import shutil

class InstallCommand(install):
    
    user_options = install.user_options + [
            ('modules-dir=', 'm', 'Modules directory'),
            ('install-defaults=','d','Install default')
    ]
    
    def initialize_options (self):
        install.initialize_options(self)
    
    def finalize_options (self):
        install.finalize_options(self)
    
    def run(self):
        install.run(self)

def readme ():
    try:
        with open('README.rst') as f:
            return f.read()
    except IOError:
        return ''

data_files = ['cravat.yml', 
              'cravat-system.template.yml', 
              'modules/cravat.yml', 
              'example_input',
              'wincravat.pyw']
for root, dirs, files in os.walk(os.path.join('cravat', 'webviewer')):
    root_files = [os.path.join('..', root, f) for f in files]
    data_files.extend(root_files)
for root, dirs, files in os.walk(os.path.join('cravat', 'liftover')):
    root_files = [os.path.join('..', root, f) for f in files]
    data_files.extend(root_files)
for root, dirs, files in os.walk(os.path.join('cravat', 'annotator_template')):
    root_files = [os.path.join('..', root, f) for f in files]
    data_files.extend(root_files)
for root, dirs, files in os.walk(os.path.join('cravat', 'webresult')):
    root_files = [os.path.join('..', root, f) for f in files]
    data_files.extend(root_files)
for root, dirs, files in os.walk(os.path.join('cravat', 'webstore')):
    root_files = [os.path.join('..', root, f) for f in files]
    data_files.extend(root_files)
for root, dirs, files in os.walk(os.path.join('cravat', 'websubmit')):
    root_files = [os.path.join('..', root, f) for f in files]
    data_files.extend(root_files)

setup(
    name='open-cravat',
    packages=['cravat'],
    version='2.2.8',
    description='OpenCRAVAT - variant analysis toolkit',
    long_description=readme(),
    author='RyangGuk Kim, Kyle Moad, Mike Ryan, and Rachel Karchin',
    author_email='support@opencravat.org',
    url='https://www.opencravat.org',
    license='',
    package_data={
        'cravat': data_files
    },
    entry_points={
        'console_scripts': [
            'oc=cravat.oc:main',
        ]
    },
    cmdclass={
              'install':InstallCommand,
              },
    install_requires=[
        'pyyaml',
        'requests',
        'requests-toolbelt',
        'pyliftover',
        'websockets',
        'markdown',
        'aiohttp',
        'chardet>=3.0.4',
        'aiosqlite',
        'oyaml',
        'intervaltree',
        'xlsxwriter',
        'openpyxl',
        'twobitreader',
        'nest-asyncio',
        'psutil',
        'mpmath',
        'PyVCF3',
        ],
    python_requires='>=3.8',
)
