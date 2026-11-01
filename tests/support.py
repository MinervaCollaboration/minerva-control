"""Shared helpers for the cdk700 / PWI4 tests (Python 2.7, stdlib only).

cdk700.py imports a lot of heavy or site-specific modules (numpy, astropy,
ephem, matplotlib, the MINERVA mail/pdu/env/utils modules, ...).  None of
them are needed to exercise the PWI2/PWI4 request logic, so this module
installs small stand-ins in sys.modules *before* cdk700 is imported.  If a
real configobj is installed it is used; otherwise a minimal INI reader that
understands the telescope_N.ini subset is installed instead.

Nothing here talks to real hardware: the PWI4 tests use the fake server in
fake_pwi4_server.py on 127.0.0.1, and the PWI2 tests replace urlopen and
os.system with recorders.
"""
import logging
import os
import re
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LIB = os.path.join(REPO, 'minerva_library')


def _module(name, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


class _Anything(object):
    """Accepts any attribute access / call; used for unused heavy modules."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return _Anything()

    def __call__(self, *args, **kwargs):
        return _Anything()


def _ten(string):
    # identical to minerva_library/utils.py ten()
    array = re.split(' |:', string)
    if "-" in array[0]:
        return float(array[0]) - float(array[1]) / 60.0 - float(array[2]) / 3600.0
    return float(array[0]) + float(array[1]) / 60.0 + float(array[2]) / 3600.0


class MemoryHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def text(self):
        return '\n'.join(r.getMessage() for r in self.records)


LOG_HANDLERS = {}


def _setup_logger(base_dir, night, logger_name):
    logger = logging.getLogger('test.' + logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = MemoryHandler()
    logger.addHandler(handler)
    LOG_HANDLERS[logger_name] = handler
    return logger


class _Site(object):
    def __init__(self, config, base):
        self.latitude = '31.680407'
        self.longitude = '-110.878977'
        self.elevation = 2316.0


class _Pdu(object):
    def __init__(self, *args, **kwargs):
        self.panel = _Anything()
        self.inst = _Anything()

    def reboot(self, *args):
        pass


MAIL_SENT = []


def _mail_send(*args, **kwargs):
    MAIL_SENT.append((args, kwargs))


class MiniConfigObj(dict):
    """Tiny reader for the telescope_N.ini subset (sections + key = value).

    Only used when the real configobj package is not installed.
    """

    def __init__(self, filename):
        dict.__init__(self)
        section = self
        with open(filename) as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('['):
                    name = line.strip('[]').strip()
                    section = {}
                    self[name] = section
                    continue
                if '=' not in line:
                    continue
                key, value = line.split('=', 1)
                value = value.strip()
                if value[:1] in ('"', "'"):
                    quote = value[0]
                    value = value[1:value.index(quote, 1)]
                else:
                    value = value.split('#', 1)[0].strip()
                section[key.strip()] = value


def install_stubs():
    if getattr(install_stubs, 'done', False):
        return
    mpl = _module('matplotlib', use=lambda *a, **k: None)
    pyplot = _module('matplotlib.pyplot')
    mpl.pyplot = pyplot
    for name in ('ipdb', 'numpy', 'ephem', 'random_unused'):
        _module(name)
    sys.modules['numpy'].cos = __import__('math').cos
    _module('mail', send=_mail_send)
    _module('pdu', pdu=_Pdu)
    _module('pdu_thach', pdu=_Pdu)
    _module('utils', setup_logger=_setup_logger, ten=_ten)
    _module('env', site=_Site)
    _module('autofocus', autofocus=lambda *a, **k: None)
    astropy = _module('astropy')
    io = _module('astropy.io')
    fits = _module('astropy.io.fits')
    io.fits = fits
    astropy.io = io
    coords = _module('astropy.coordinates', SkyCoord=_Anything)
    astropy.coordinates = coords
    units = _module('astropy.units')
    astropy.units = units
    wcs = _module('astropy.wcs')
    astropy.wcs = wcs
    try:
        import configobj  # noqa: F401  (use the real one when available)
    except ImportError:
        _module('configobj', ConfigObj=MiniConfigObj)
    if LIB not in sys.path:
        sys.path.insert(0, LIB)
    install_stubs.done = True


TELESCOPE_INI = """name = test telescope configuration file
[Setup]
	HOST = 127.0.0.1
	NETWORKPORT = %(pwi2_port)s
	LOGNAME = telescope_9
	ID = 'T9'
	IMAGER = 'C9'
	GUIDER = 'GC9'
	FAU = 'F9'
	PDU = apc_9.ini
	MODELDIR = '%(modeldir)s'
	DATADIR = '%(datadir)s'
	SITEINI = 'site_test.ini'
	HORIZON = 21.0 # degrees
	WIN10 = True
%(extra_setup)s
[PORT]
	IMAGER = '1'
	FAU = '2'
[DEFAULT_FOCUS]
	0 = 'UNKNOWN'
	1 = 25000
	2 = 25000
[FOCUS_OFFSET]
	0 = 'UNKNOWN'
	1 = 0
	2 = 0
[F0]
	0 = 23850.0
	1 = 23850.0
	2 = 23850.0
[C0]
	0 = 0.0
	1 = -29.1
	2 = -29.1
[T0]
	0 = 10.089
	1 = 10.089
	2 = 10.089
[C1]
	0 = 0.0
	1 = -74.9
	2 = -74.9
[dT0]
	0 = 3.254
	1 = 3.254
	2 = 3.254
[C2]
	0 = 0
	1 = 434.6
	2 = 434.6
[G0]
	0 = 0.7777
	1 = 0.7777
	2 = 0.7777
[MINFOCUS]
	0 = 100
	1 = 455
	2 = 100
[MAXFOCUS]
	0 = 33000
	1 = 33000
	2 = 33000
[MODEL]
	0 = 'UNKNOWN'
	1 = 'T9.Port1.PXP'
	2 = 'T9.Port2.PXP'
%(extra_sections)s
[ROTATOROFFSET]
	0 = 'UNKNOWN'
	1 = 0.0
	2 = 249.666
"""

PASSWORD = 'not-a-real-password-123'


class Sandbox(object):
    """A throw-away base_directory with config/, credentials/, log/."""

    def __init__(self, extra_setup='', extra_sections='', pwi2_port='44444'):
        self.base = tempfile.mkdtemp(prefix='cdk700test.')
        for sub in ('config', 'credentials', 'log', 'models', 'data', 'dependencies'):
            os.mkdir(os.path.join(self.base, sub))
        self.modeldir = os.path.join(self.base, 'models') + '/'
        for name in ('T9.Port1.PXP', 'T9.Port2.PXP'):
            open(self.modeldir + name, 'w').close()
        shutil.copy(os.path.join(REPO, 'dependencies', 'telstateunknown.xml'),
                    os.path.join(self.base, 'dependencies'))
        with open(os.path.join(self.base, 'credentials', 'authentication.txt'), 'w') as fh:
            fh.write('observer\n%s\n' % PASSWORD)
        with open(os.path.join(self.base, 'config', 'telescope_9.ini'), 'w') as fh:
            fh.write(TELESCOPE_INI % dict(
                pwi2_port=pwi2_port, modeldir=self.modeldir,
                datadir=os.path.join(self.base, 'data') + '/',
                extra_setup=extra_setup, extra_sections=extra_sections))

    def cleanup(self):
        shutil.rmtree(self.base, ignore_errors=True)


class FakeTime(object):
    """Replacement for cdk700's `time` module: sleep() is fast but real.

    Sleeps are scaled by `factor` so that wait loops still advance the
    wall clock (their timeouts use datetime.utcnow()).
    """

    def __init__(self, factor=0.0, cap=0.05):
        import time as _time
        self._time = _time
        self.factor = factor
        self.cap = cap
        self.slept = []

    def sleep(self, seconds):
        self.slept.append(seconds)
        self._time.sleep(min(seconds * self.factor, self.cap))

    def __getattr__(self, name):
        return getattr(self._time, name)


def import_cdk700():
    install_stubs()
    import cdk700
    return cdk700
