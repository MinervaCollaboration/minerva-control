"""PWI2 telescopes must send exactly the same requests as before the PWI4 port.

A scripted session of cdk700 calls is run against a recorder that replaces
urllib.urlopen (PWI2 HTTP) and os.system (remote process control).  The
resulting request log is compared line-for-line with
tests/data/pwi2_golden_requests.golden, which was generated from the
unmodified master version of cdk700.py (commit ace883b).

Regenerate (only when a PWI2 change is intended!):
    python2 tests/test_cdk700_pwi2_unchanged.py --write
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402

GOLDEN = os.path.join(support.HERE, 'data', 'pwi2_golden_requests.golden')


def _status_xml(**over):
    with open(os.path.join(support.REPO, 'dependencies', 'telstateunknown.xml')) as fh:
        xml = fh.read()
    subs = {
        '<connected>False</connected>': '<connected>True</connected>',
        '<azm_enabled>False</azm_enabled>': '<azm_enabled>True</azm_enabled>',
        '<alt_enabled>False</alt_enabled>': '<alt_enabled>True</alt_enabled>',
        '<tracking>False</tracking>': '<tracking>True</tracking>',
        '<altaz_derotate>False</altaz_derotate>': '<altaz_derotate>True</altaz_derotate>',
        '<position>-9999</position>': '<position>25000</position>',
        '<encoders_have_been_set>False</encoders_have_been_set>':
            '<encoders_have_been_set>True</encoders_have_been_set>',
        '<lst>00 00 00.000</lst>': '<lst>05 30 00.000</lst>',
        '<ra>00 00 00.000</ra>': '<ra>04 00 00.000</ra>',
        '<dec>+00 00 00.00</dec>': '<dec>+20 00 00.00</dec>',
    }
    subs.update(over)
    for old, new in subs.items():
        xml = xml.replace(old, new)
    return xml


class _Resp(object):
    def __init__(self, text):
        self.text = text

    def read(self):
        return self.text


def record_pwi2_session():
    """Run a fixed sequence of cdk700 calls on a PWI2 telescope; return the request log."""
    cdk700 = support.import_cdk700()
    sandbox = support.Sandbox()
    log = []
    xml = {'value': _status_xml()}

    def fake_urlopen(url, *args, **kwargs):
        log.append('HTTP ' + url.replace('127.0.0.1:44444', 'HOST:PORT'))
        return _Resp(xml['value'])

    def fake_system(cmd):
        log.append('SYSTEM ' + cmd.replace(sandbox.base, 'BASE'))
        return 0

    saved = (cdk700.urllib.urlopen, cdk700.os.system, cdk700.time)
    cdk700.urllib.urlopen = fake_urlopen
    cdk700.os.system = fake_system
    cdk700.time = support.FakeTime(factor=0.0)
    try:
        tel = cdk700.CDK700('telescope_9.ini', sandbox.base)
        log.append('--- initialize')
        tel.initialize(tracking=True, derotate=True)
        log.append('--- low-level mount')
        tel.mountConnect()
        tel.mountEnableMotors()
        tel.mountHome()
        tel.mountGotoRaDecJ2000(10.5, 20.25)
        tel.mountGotoRaDecApparent(10.5, 20.25)
        tel.mountGotoAltAz(45.0, 180.0)
        tel.mountOffsetRaDec(1.5, -2.0)
        tel.mountOffsetAltAz(3.0, -4.0)
        tel.mountTrackingOn()
        tel.mountTrackingOff()
        tel.mountSetTrackingRateOffsets(0.1, -0.2)
        tel.mountStop()
        tel.mountSetPointingModel('T9.Port1.PXP')
        tel.mountAddToModel(10.5, 20.25)
        tel.mountSaveModel('T9.Port1.PXP')
        tel.mountSync(10.5, 20.25)
        tel.mountDisableMotors()
        tel.mountDisconnect()
        log.append('--- focuser/rotator')
        tel.focuserConnect('1')
        tel.focuserMove(20000, '1')
        tel.focuserIncrement(10, '2')
        tel.focuserStop('2')
        tel.focuserHome('1')
        tel.focuserMoveAndWait(25000, '1')
        tel.rotatorMove(100.0, '1')
        tel.rotatorIncrement(1.5, '2')
        tel.rotatorStop('1')
        tel.rotatorStartDerotating('2')
        tel.rotatorStopDerotating('1')
        tel.rotatorHome('2')
        tel.startAutoFocus()
        log.append('--- m3')
        tel.m3SelectPort('1')
        tel.m3Stop()
        tel.m3port_switch('1')
        log.append('--- status')
        tel.getStatus()
        tel.getFocuserStatus('1')
        tel.getRotatorStatus('2')
        log.append('--- slew + inPosition')
        tel.inPosition(m3port='2', tracking=True, derotate=False)
        log.append('--- shutdown')
        tel.shutdown('1')
        log.append('--- process control')
        tel.killPWI()
        tel.startPWI()
        tel.reboot_telcom()
    finally:
        cdk700.urllib.urlopen, cdk700.os.system, cdk700.time = saved
        sandbox.cleanup()
    return log


class TestPWI2RequestsUnchanged(unittest.TestCase):

    def test_requests_identical_to_master(self):
        with open(GOLDEN) as fh:
            golden = fh.read().splitlines()
        self.assertEqual(record_pwi2_session(), golden)

    def test_default_is_pwi2(self):
        cdk700 = support.import_cdk700()
        sandbox = support.Sandbox()
        try:
            tel = cdk700.CDK700('telescope_9.ini', sandbox.base)
        finally:
            sandbox.cleanup()
        self.assertEqual(getattr(tel, 'pwi_version', 2), 2)


if __name__ == '__main__':
    if '--write' in sys.argv:
        lines = record_pwi2_session()
        with open(GOLDEN, 'w') as fh:
            fh.write('\n'.join(lines) + '\n')
        print('wrote %d lines to %s' % (len(lines), GOLDEN))
    else:
        unittest.main()
