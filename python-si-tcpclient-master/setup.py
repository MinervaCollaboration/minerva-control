import os
import sys

from distutils.core import setup

# append si to sys.path to get current version
build_dir = os.getcwd ()
src_dir   = os.path.join (build_dir, 'si')

old_sys_path = sys.path
sys.path.insert (0, src_dir)

from si import __version__, __description__, __author__, __license__

# modules
si_modules = ['si',
              'si.packets',
              'si.commands']

si_scripts = ['si-grabber']

# setup

setup(name='si',
      package_dir      = {"si": "si"},

      packages         = si_modules,
      scripts          = si_scripts,

      version          = __version__,
      description      = __description__,
      author           = __author__)
