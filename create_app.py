# -*- coding: utf-8 -*-
#
# Copyright © 2012 The Spyder development team
# Licensed under the terms of the MIT License
# (see spyderlib/__init__.py for details)

"""
Create a stand-alone Mac OS X app using py2app

To be used like this:
$ python create_app.py py2app
"""

from setuptools import setup

from distutils.sysconfig import get_python_lib
import fileinput
import shutil
import os
import os.path as osp
import subprocess
import sys

from IPython.core.completerlib import module_list

from spyderlib import __version__ as spy_version
from spyderlib.config import EDIT_EXT
from spyderlib.utils.programs import find_program

#==============================================================================
# Auxiliary functions
#==============================================================================

def get_stdlib_modules():
    """
    Returns a list containing the names of all the modules available in the
    standard library.
    
    Based on the function get_root_modules from the IPython project.
    Present in IPython.core.completerlib in v0.13.1
    
    Copyright (C) 2010-2011 The IPython Development Team.
    Distributed under the terms of the BSD License.
    """
    modules = list(sys.builtin_module_names)
    for path in sys.path[1:]:
        if 'site-packages' not in path:
            modules += module_list(path)
    
    modules = set(modules)
    if '__init__' in modules:
        modules.remove('__init__')
    modules = list(modules)
    return modules

#==============================================================================
# App creation
#==============================================================================

shutil.copyfile('scripts/spyder', 'Spyder.py')

APP = ['Spyder.py']
DEPS = ['pylint', 'logilab_astng', 'logilab_common', 'pep8', 'setuptools']
EXCLUDES = DEPS + ['mercurial', 'nose']
PACKAGES = ['spyderlib', 'spyderplugins', 'sphinx', 'jinja2', 'docutils',
            'IPython', 'zmq', 'pygments', 'rope', 'distutils', 'PIL', 'PyQt4',
            'sklearn', 'skimage', 'pandas', 'sympy', 'mpmath', 'statsmodels',
            'mpl_toolkits']
INCLUDES = get_stdlib_modules()
EDIT_EXT = [ext[1:] for ext in EDIT_EXT]

OPTIONS = {
    'argv_emulation': True,
    'compressed' : False,
    'optimize': 0,
    'packages': PACKAGES,
    'includes': INCLUDES,
    'excludes': EXCLUDES,
    'iconfile': 'img_src/spyder.icns',
    'plist': {'CFBundleDocumentTypes': [{'CFBundleTypeExtensions': EDIT_EXT,
                                         'CFBundleTypeName': 'Text File',
                                         'CFBundleTypeRole': 'Editor'}],
              'CFBundleIdentifier': 'org.spyder-ide',
              'CFBundleShortVersionString': spy_version}
}

setup(
    app=APP,
    options={'py2app': OPTIONS}
)

os.remove('Spyder.py')

#==============================================================================
# Post-app creation
#==============================================================================

# Main paths
resources = 'dist/Spyder.app/Contents/Resources'
system_python_lib = get_python_lib()
app_python_lib = osp.join(resources, 'lib', 'python2.7')

# Add our docs to the app
docs = osp.join(system_python_lib, 'spyderlib', 'doc')
docs_dest = osp.join(app_python_lib, 'spyderlib', 'doc')
shutil.copytree(docs, docs_dest)

# Add necessary Python programs to the app
PROGRAMS = ['pylint', 'pep8']
system_progs = [find_program(p) for p in PROGRAMS]
progs_dest = [resources + osp.sep + p for p in PROGRAMS]
for i in range(len(PROGRAMS)):
    shutil.copy2(system_progs[i], progs_dest[i])

# Add deps needed for PROGRAMS to the app
deps = []
for package in os.listdir(system_python_lib):
    for d in DEPS:
        if package.startswith(d):
            deps.append(package)

for i in deps:
    if osp.isdir(osp.join(system_python_lib, i)):
        shutil.copytree(osp.join(system_python_lib, i),
                        osp.join(app_python_lib, i))
    else:
        shutil.copy2(osp.join(system_python_lib, i),
                     osp.join(app_python_lib, i))

# Hack to make pep8 work inside the app
pep8_egg = filter(lambda d: d.startswith('pep8'), deps)[0]
pep8_script = osp.join(app_python_lib, pep8_egg, 'pep8.py')
for line in fileinput.input(pep8_script, inplace=True):
    if line.strip().startswith('codes = ERRORCODE_REGEX.findall'):
        print "            codes = ERRORCODE_REGEX.findall(function.__doc__ or 'W000')"
    else:
        print line,

# Function to adjust the interpreter used by PROGRAMS
# (to be added to __boot.py__)
change_interpreter = \
"""
PROGRAMS = %s

def _change_interpreter(program):
    import fileinput
    import sys
    try:
        for line in fileinput.input(program, inplace=True):
           if line.startswith('#!'):
               print '#!' + sys.executable
           else:
               print line,
    except:
        pass

for p in PROGRAMS:
    _change_interpreter(p)
""" % str(PROGRAMS)

# Add RESOURCEPATH to PATH, so that Spyder can find PROGRAMS inside the app
new_path = \
"""
old_path = os.environ['PATH']
os.environ['PATH'] = os.environ['RESOURCEPATH'] + os.pathsep + old_path
"""

# Add IPYTHONDIR to the app env because it seems IPython gets confused
# about its location when running inside the app
ip_dir = \
"""
from IPython.utils.path import get_ipython_dir
os.environ['IPYTHONDIR'] = get_ipython_dir()
"""

# Add a way to grab environment variables inside the app.
# Thanks a lot to Ryan Clary for posting it here
# https://groups.google.com/forum/?fromgroups=#!topic/spyderlib/lCXOYk-FSWI
get_env = \
r"""
def _get_env():
    import os
    import subprocess as sp
    envstr = sp.check_output('source /etc/profile; source ~/.profile; printenv',
                             shell=True)
    env = [a.split('=') for a in envstr.strip().split('\n')]
    os.environ.update(env)
_get_env()
"""

# Add our modifications to __boot__.py so that they can be taken into
# account when the app is started
boot_file = 'dist/Spyder.app/Contents/Resources/__boot__.py'
reset_line = "_reset_sys_path()"
run_line = "_run()"
for line in fileinput.input(boot_file, inplace=True):
    if line.startswith(reset_line):
        print reset_line
        print get_env
    elif line.startswith(run_line):
        print change_interpreter
        print new_path
        print ip_dir
        print run_line
    else:
        print line,

# Run macdeployqt so that the app can use the internal Qt Framework
subprocess.call(['macdeployqt', 'dist/Spyder.app'])