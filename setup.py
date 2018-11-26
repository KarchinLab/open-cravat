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
        self.modules_dir = None
        self.install_defaults = 'True'
    
    def finalize_options (self):
        install.finalize_options(self)
    
    def run(self):
        """
        Using method found at https://stackoverflow.com/a/43078078
        Needed because pip runs install commands 
        """
        def _post_install():
            wf = open('test.txt', 'w')
            try:
                from cravat import constants as c
                def find_cravat_path():
                    for p in sys.path:
                        if os.path.isdir(p) and 'cravat' in os.listdir(p):
                            return os.path.join(p, 'cravat')
                install_path = find_cravat_path()
                system_conf_path = os.path.join(install_path,
                                                c.system_conf_fname)
                system_template_conf_path = c.system_conf_template_path
                if self.modules_dir == None:
                    default_modules_dir = os.path.join(
                        install_path, c.default_modules_dir_relative)
                else:
                    default_modules_dir = self.modules_dir
                if not(os.path.exists(c.system_conf_path)):
                    shutil.copy(system_template_conf_path,
                                system_conf_path)
                else:
                    shutil.copy(c.system_conf_path, system_conf_path)
                from cravat import admin_util as au
                au.set_modules_dir(default_modules_dir)
            except:
                import traceback
                wf.write(traceback.format_exc() + '\n')
            wf.write('done\n')
            wf.close()
            
        atexit.register(_post_install)
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
              'example_input']
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
    version='0.0.140',
    description='Open-CRAVAT - variant analysis toolkit',
    long_description=readme(),
    author='Rick Kim, Kyle Moad, Mike Ryan, and Rachel Karchin',
    author_email='rkim@insilico.us.com',
    url='http://www.cravat.us',
    license='',
    package_data={
        'cravat': data_files
    },
    entry_points={
        'console_scripts': [
            'cravat-admin=cravat.cravat_admin:main',
            'cravat=cravat.runcravat:main',
            'cravat-view=cravat.cravat_web:result',
            'cravat-store=cravat.cravat_web:store',
            'wcravat=cravat.cravat_web:submit',
            'cravat-filter=cravat.cravat_filter:main',
            'cravat-report=cravat.cravat_report:main',
            'cravat-test=cravat.cravat_test:main',
            'cravat-util=cravat.cravat_util:main',
            'cv=cravat.runcravat:main',
            'cva=cravat.cravat_admin:main',
        ]
    },
    cmdclass={
              'install':InstallCommand,
              },
    #install_requires=['pyyaml', 'requests', 'requests_toolbelt', 'pyliftover', 'websockets', 'markdown', 'aiohttp', 'aiohttp_session', 'cryptography'],
    install_requires=['pyyaml', 'requests', 'requests_toolbelt', 'pyliftover', 'websockets', 'markdown', 'aiohttp'],
)
