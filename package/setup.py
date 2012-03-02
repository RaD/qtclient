# -*- coding: utf-8 -*-

from distutils.core import setup

setup(name='advisor-client',
      version='0.4.4',
      description='Accounting System / Client Interface',
      author='Ruslan Popov',
      author_email='ruslan.popov@gmail.com',
      maintainer='Ruslan Popov',
      maintainer_email='ruslan.popov@gmail.com',
      url='http://snegiri.dontexist.org/projects/advisor/client/',
      packages=['advisor-client'],
      package_dir={'advisor-client': 'client'},
      package_data={'advisor-client': [
          'dialogs/*.py',
          'uis/*.ui',
          'advisor-client_*.qm',
          'manager.css'
          ]}
     )
