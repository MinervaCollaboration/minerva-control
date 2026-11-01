"""cdk700.CDK700 with PWI_VERSION = 4, driven against the fake PWI4 server."""
import os
import socket
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
from fake_pwi4_server import FakePWI4Server  # noqa: E402

cdk700 = support.import_cdk700()
import cdk700_pwi4  # noqa: E402
import pwi4  # noqa: E402

ten = support._ten

PWI4_SETUP = """	PWI_VERSION = 4
	PWI4_PORT = %(port)d
	PWI4_TIMEOUT = 1.0
	PWI4_M3_TIMEOUT = 2.0
	PWI4_M3_SETTLE = 1.0
	PWI4_POLL = 0.05
	PWI4_START_TIMEOUT = 2.0
	PWI4_REMOTE_TIMEOUT = 0.5
"""
PWI4_SECTIONS = """[PWI4_MODEL]
	1 = 'T9_port1.dat'
	2 = 'T9_port2.dat'
"""


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class FakePopen(object):
    """Records remote commands instead of running sshpass/winexe."""
    calls = []
    hang = False

    def __init__(self, argv, **kwargs):
        FakePopen.calls.append(argv)
        self.returncode = None if FakePopen.hang else 0
        self.killed = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def communicate(self):
        return ('SUCCESS', '')


class PWI4TestCase(unittest.TestCase):
    sections = PWI4_SECTIONS

    def setUp(self):
        self.server = FakePWI4Server().start()
        self.fake = self.server.fake
        self.fake.select_lag = 0.01   # GUI re-selection lag < scaled PWI4_M3_SETTLE
        self.sandbox = support.Sandbox(extra_setup=PWI4_SETUP % {'port': self.server.port},
                                       extra_sections=self.sections)
        self.saved = (cdk700.time, cdk700_pwi4.time, cdk700_pwi4.subprocess.Popen)
        fast = support.FakeTime(factor=0.05, cap=0.05)
        cdk700.time = fast
        cdk700_pwi4.time = fast
        FakePopen.calls = []
        FakePopen.hang = False
        cdk700_pwi4.subprocess.Popen = FakePopen
        self.tel = cdk700.CDK700('telescope_9.ini', self.sandbox.base)
        self.log = support.LOG_HANDLERS['telescope_9']
        del self.fake.requests[:]

    def tearDown(self):
        cdk700.time, cdk700_pwi4.time, cdk700_pwi4.subprocess.Popen = self.saved
        self.server.stop()
        self.sandbox.cleanup()

    def ready(self):
        """Put the fake mount in the connected/enabled/tracking state."""
        self.fake.mount_connected = True
        self.fake.axis_enabled = [True, True]
        self.fake.tracking = True
        self.fake.focusers[0].connected = True
        self.fake.focusers[0].enabled = True
        self.fake.focusers[1].enabled = True
        self.fake.rotators[0].connected = True
        self.fake.rotators[0].enabled = True

    def commands(self):
        return self.server.commands()

    def command_paths(self):
        return [p for p, _ in self.commands()]


class TestConfig(PWI4TestCase):

    def test_pwi4_selected_by_config(self):
        self.assertEqual(self.tel.pwi_version, 4)
        self.assertEqual(self.tel.pwi4.port, self.server.port)
        self.assertEqual(self.tel.pwi4_exe, 'PWI4.exe')
        self.assertEqual(self.tel.pwi4_start_task, 'Start PWI4')

    def test_real_configs_default_to_pwi2(self):
        support.install_stubs()
        from configobj import ConfigObj
        for n in ('1', '2', '3', '4'):
            config = ConfigObj(os.path.join(support.REPO, 'config', 'telescope_%s.ini' % n))
            self.tel._pwi4_load_config(config)
            self.assertEqual(self.tel.pwi_version, 2, 'telescope_%s.ini must stay on PWI2' % n)
            self.assertTrue(self.tel.pwi4 is None)

    def test_pwi2_requests_refused(self):
        self.assertFalse(self.tel.pwiRequest(device='mount', cmd='connect'))


class TestConnect(PWI4TestCase):

    def test_initialize_from_cold(self):
        self.fake.focusers[0].connected = False
        self.assertTrue(self.tel.initialize(tracking=True, derotate=True))
        paths = self.command_paths()
        self.assertEqual(paths[0], '/mount/connect')
        self.assertIn(('/mount/enable', {'axis': '0'}), self.commands())
        self.assertIn(('/mount/enable', {'axis': '1'}), self.commands())
        self.assertNotIn(('/mount/enable', {'axis': '-1'}), self.commands())
        self.assertIn('/focuser/connect', paths)
        self.assertIn('/mount/tracking_on', paths)
        self.assertIn('/rotator/goto_field', paths)
        self.assertTrue(self.tel.isInitialized(tracking=True, derotate=True))
        self.assertFalse(self.tel.isInitialized(tracking=False, derotate=True))

    def test_initialize_fails_when_connect_fails(self):
        self.fake.connect_works = False
        t0 = time.time()
        self.assertFalse(self.tel.initialize())
        self.assertLess(time.time() - t0, 20.0)
        self.assertIn('Failed to connect to mount', self.log.text())

    def test_home(self):
        self.ready()
        t0 = time.time()
        self.assertTrue(self.tel.home())
        self.assertGreaterEqual(time.time() - t0, self.fake.home_time)
        self.assertIn('/mount/find_home', self.command_paths())
        self.assertEqual(self.tel.getStatus().mount.encoders_have_been_set, 'True')
        self.assertEqual(self.tel.getStatus().mount.is_finding_home, 'False')

    def test_home_fails_if_axis_drops(self):
        self.ready()
        self.fake.home_time = 5.0
        threading.Timer(0.3, lambda: self.fake.axis_enabled.__setitem__(0, False)).start()
        self.assertFalse(self.tel.home())


class TestSlew(PWI4TestCase):

    def test_slew_and_inposition(self):
        self.ready()
        self.tel.mountGotoRaDecJ2000(5.5, -10.25)
        self.assertEqual(self.commands()[-1], ('/mount/goto_ra_dec_j2000',
                                               {'ra_hours': '5.5', 'dec_degs': '-10.25'}))
        t0 = time.time()
        self.assertTrue(self.tel.inPosition(m3port='1', ra=5.5, dec=-10.25, derotate=False))
        self.assertGreaterEqual(time.time() - t0, self.fake.slew_time)
        s = self.tel.getStatus()
        self.assertAlmostEqual(ten(s.mount.ra_2000), 5.5, places=5)
        self.assertAlmostEqual(ten(s.mount.dec_2000), -10.25, places=4)
        self.assertEqual(s.mount.moving, 'False')

    def test_sexagesimal_targets_are_sent_as_decimal(self):
        self.ready()
        self.tel.mountGotoRaDecJ2000('05 30 00', '-10 15 00')
        self.assertEqual(self.commands()[-1][1], {'ra_hours': '5.5', 'dec_degs': '-10.25'})

    def test_inposition_detects_wrong_position(self):
        self.ready()
        self.tel.mountGotoRaDecJ2000(5.5, -10.25)
        self.assertFalse(self.tel.inPosition(m3port='1', ra=6.0, dec=-10.25, derotate=False))

    def test_inposition_fails_on_axis_fault(self):
        self.ready()
        self.fake.slew_time = 5.0
        self.tel.mountGotoRaDecJ2000(5.5, -10.25)
        threading.Timer(0.3, lambda: self.fake.axis_enabled.__setitem__(1, False)).start()
        t0 = time.time()
        self.assertFalse(self.tel.inPosition(m3port='1', derotate=False))
        self.assertLess(time.time() - t0, 4.0)
        self.assertIn('altitude drive', self.log.text())

    def test_altaz_and_park(self):
        self.ready()
        self.tel.mountGotoAltAz(25.0, 0.0)
        self.assertEqual(self.commands()[-1], ('/mount/goto_alt_az', {'alt_degs': '25.0', 'az_degs': '0.0'}))
        self.assertTrue(self.tel.inPosition(alt=25.0, az=0.0, pointingTolerance=3600.0, derotate=False))

    def test_tracking(self):
        self.ready()
        self.tel.mountTrackingOff()
        self.assertEqual(self.tel.getStatus().mount.tracking, 'False')
        self.tel.mountTrackingOn()
        self.assertEqual(self.tel.getStatus().mount.tracking, 'True')
        self.assertFalse(self.tel.isMoving())

    def test_offsets(self):
        self.ready()
        self.tel.mountOffsetRaDec(1.5, -2.0)
        self.assertEqual(self.commands()[-1], ('/mount/offset', {'ra_add_arcsec': '1.5', 'dec_add_arcsec': '-2.0'}))
        self.tel.mountOffsetAltAz(3.0, -4.0)
        self.assertEqual(self.commands()[-1], ('/mount/offset', {'axis1_add_arcsec': '3.0', 'axis0_add_arcsec': '-4.0'}))
        self.tel.mountOffsetAltAzFixed(1.0, 2.0)
        self.assertEqual(self.commands()[-1], ('/mount/offset', {'axis1_add_arcsec': '1.0', 'axis0_add_arcsec': '2.0'}))
        self.assertEqual(self.fake.offsets, {'ra': 1.5, 'dec': -2.0, 'axis0': -2.0, 'axis1': 4.0})
        self.tel.mountSetTrackingRateOffsets(0.1, -0.2)
        self.assertEqual(self.commands()[-1][1], {'ra_set_rate_arcsec_per_sec': '0.1',
                                                  'dec_set_rate_arcsec_per_sec': '-0.2'})


class TestFocuser(PWI4TestCase):

    def test_move_and_wait(self):
        self.ready()
        self.assertTrue(self.tel.focuserMoveAndWait(26000, '1'))
        self.assertEqual(self.commands()[-1], ('/focuser/goto', {'target': '26000.0'}))
        self.assertEqual(self.tel.getFocuserStatus('1').position, '26000')
        self.assertAlmostEqual(self.fake.focusers[1].position, 24000.0)  # other port untouched

    def test_out_of_bounds(self):
        self.ready()
        self.assertFalse(self.tel.focuserMoveAndWait(50, '1'))
        self.assertEqual(self.commands(), [])

    def test_other_port_switches_m3_first(self):
        self.ready()
        self.assertTrue(self.tel.focuserMoveAndWait(23000, '2'))
        paths = self.command_paths()
        self.assertLess(paths.index('/m3/goto'), paths.index('/focuser/goto'))
        self.assertAlmostEqual(self.fake.focusers[1].current(time.time()), 23000.0)
        self.assertAlmostEqual(self.fake.focusers[0].current(time.time()), 25000.0)
        self.assertEqual(self.tel.getStatus().m3.port, '2')
        self.assertEqual(self.fake.model, 'T9_port2.dat')

    def test_lock_released_on_error(self):
        self.ready()
        orig = self.tel._pwi4_raw
        calls = [0]

        def flaky():
            calls[0] += 1
            if calls[0] > 2:
                raise pwi4.PWI4BadResponse('garbage')
            return orig()
        self.tel._pwi4_raw = flaky
        self.assertFalse(self.tel.focuserMoveAndWait(26000, '1'))
        self.tel._pwi4_raw = orig
        result = []
        t = threading.Thread(target=lambda: result.append(self.tel.focuserMoveAndWait(25500, '1')))
        t.daemon = True
        t.start()
        t.join(5.0)
        self.assertFalse(t.is_alive(), 'focuser lock leaked')
        self.assertEqual(result, [True])

    def test_lock_released_on_exception(self):
        self.ready()
        self.tel.focuserMove = lambda *a: 1 / 0
        self.assertRaises(ZeroDivisionError, self.tel.focuserMoveAndWait, 26000, '1')
        lock = self.tel._pwi4_port_lock('focuser')
        t = threading.Thread(target=lambda: (lock.acquire(), lock.release()))
        t.daemon = True
        t.start()
        t.join(5.0)
        self.assertFalse(t.is_alive(), 'focuser lock leaked')

    def test_focuser_home(self):
        self.ready()
        self.assertTrue(self.tel.focuserHomeAndWait('2'))
        self.assertIn(('/focuser/find_home', {'index': '1'}), self.commands())
        self.assertEqual(self.tel.getFocuserStatus('2').finding_home, 'False')

    def test_disconnect_port2_refused(self):
        self.ready()
        self.assertFalse(self.tel.focuserDisconnect('2'))
        self.assertNotIn('/focuser/disconnect', self.command_paths())


class TestRotator(PWI4TestCase):

    def test_move_wait_and_derotate(self):
        self.ready()
        self.assertTrue(self.tel.rotatorMove(100.0, '1', wait=True))
        self.assertEqual(self.commands()[-1], ('/rotator/goto_mech', {'degs': '100.0'}))
        self.assertAlmostEqual(float(self.tel.getRotatorStatus('1').position), 100.0, places=3)
        self.tel.rotatorStartDerotating('1')
        self.assertEqual(self.commands()[-1][0], '/rotator/goto_field')
        self.assertAlmostEqual(float(self.commands()[-1][1]['degs']), (30.0 - 100.0) % 360.0, places=3)
        self.assertTrue(self.tel.inPosition(m3port='1', derotate=True))
        s = self.tel.getStatus()
        self.assertEqual(s.rotator.altaz_derotate, 'True')
        self.assertEqual(s.rotator1.goto_complete, 'True')
        self.tel.rotatorStopDerotating('1')
        self.assertEqual(self.tel.getStatus().rotator.altaz_derotate, 'False')

    def test_move_while_derotating_resumes(self):
        # acquireTarget: initialize(derotate=True), rotatorMove(angle), slew, inPosition(derotate=True)
        self.ready()
        self.assertTrue(self.tel.initialize(tracking=True, derotate=True))
        self.tel.rotatorMove(120.0, '1')
        self.assertEqual(self.tel.getStatus().rotator.altaz_derotate, 'True')   # PWI2-like
        self.assertTrue(self.tel.isInitialized(tracking=True, derotate=True))
        self.assertTrue(self.tel.inPosition(m3port='1', derotate=True))
        last_field = [q for p, q in self.commands() if p == '/rotator/goto_field'][-1]
        self.assertAlmostEqual(float(last_field['degs']), (30.0 - 120.0) % 360.0, places=3)
        self.assertEqual(self.tel.getStatus().rotator.altaz_derotate, 'True')

    def test_port2_position_derived(self):
        self.ready()
        self.assertTrue(self.tel.rotatorMove(45.0, '2', wait=True))
        self.assertEqual(self.tel.getStatus().m3.port, '2')
        self.assertAlmostEqual(float(self.tel.getRotatorStatus('2').position), 45.0, places=3)
        self.assertAlmostEqual(float(self.tel.getRotatorStatus('1').position), 180.0, places=3)

    def test_rotator_lock_released_on_timeout(self):
        self.ready()
        self.fake.rotator_time = 10.0
        self.assertFalse(self.tel.rotatorMove(10.0, '1', wait=True, timeout=0.3))
        lock = self.tel._pwi4_port_lock('rotator')
        t = threading.Thread(target=lambda: (lock.acquire(), lock.release()))
        t.daemon = True
        t.start()
        t.join(5.0)
        self.assertFalse(t.is_alive())


class TestM3(PWI4TestCase):

    def test_switch_loads_pwi4_model(self):
        self.ready()
        self.assertTrue(self.tel.m3port_switch('2'))
        self.assertIn(('/mount/model/load', {'filename': 'T9_port2.dat'}), self.commands())
        self.assertIn(('/m3/goto', {'port': '2'}), self.commands())
        self.assertEqual(self.tel.getStatus().m3.port, '2')
        self.assertEqual(self.tel.getStatus().mount.tracking, 'True')
        n = len(self.commands())
        self.assertTrue(self.tel.m3port_switch('2'))     # already there: nothing sent
        self.assertEqual(len(self.commands()), n)

    def test_switch_times_out(self):
        self.ready()
        self.fake.m3_stuck = True
        t0 = time.time()
        self.assertFalse(self.tel.m3port_switch('2'))
        self.assertLess(time.time() - t0, self.tel.pwi4_m3_timeout + 3.0)
        self.assertIn('/m3/stop', self.command_paths())
        self.assertEqual(self.command_paths().count('/m3/goto'), 1)   # not re-sent in a loop

    def test_switch_when_pwi4_down(self):
        self.ready()
        self.fake.fail_mode = 'hang'
        self.fake.hang_seconds = 3.0
        t0 = time.time()
        self.assertFalse(self.tel.m3port_switch('2'))
        self.assertLess(time.time() - t0, 3.0)

    def test_bad_port(self):
        self.assertFalse(self.tel.m3port_switch('3'))


class TestModels(PWI4TestCase):
    sections = ''   # no [PWI4_MODEL]

    def test_no_model_is_a_warned_noop(self):
        self.ready()
        self.assertTrue(self.tel.m3port_switch('2'))
        self.assertNotIn('/mount/model/load', self.command_paths())
        self.assertIn('PWI2 .PXP models cannot be loaded by PWI4', self.log.text())
        self.assertFalse(self.tel.mountSetPointingModel('T9.Port1.PXP'))
        self.assertFalse(self.tel.mountSaveModel('T9.Port1.PXP'))
        self.assertNotIn('/mount/model/save', self.command_paths())

    def test_add_point(self):
        self.ready()
        self.tel.mountAddToModel(10.5, '-20 15 00')
        self.assertEqual(self.commands()[-1], ('/mount/model/add_point',
                                               {'ra_j2000_hours': '10.5', 'dec_j2000_degs': '-20.25'}))
        self.assertFalse(self.tel.mountSync(10.5, 20.0))


class TestFailures(PWI4TestCase):

    def test_status_raises_never_fakes(self):
        self.fake.fail_mode = 'hang'
        self.fake.hang_seconds = 3.0
        t0 = time.time()
        self.assertRaises(pwi4.PWI4Error, self.tel.getStatus)
        self.assertLess(time.time() - t0, 2.5)
        self.assertFalse(self.tel.isInitialized())
        self.assertFalse(self.tel.inPosition(derotate=False))
        self.assertFalse(self.tel.home())

    def test_refused(self):
        self.tel.pwi4 = pwi4.PWI4Client('127.0.0.1', free_port(), timeout=1.0)
        self.assertRaises(pwi4.PWI4Unreachable, self.tel.getStatus)
        self.assertFalse(self.tel.initialize())
        self.assertFalse(self.tel.mountGotoRaDecJ2000(1.0, 2.0))
        self.assertTrue(self.tel.isMoving())   # cannot confirm it is stopped

    def test_garbage(self):
        self.fake.fail_mode = 'garbage'
        self.assertRaises(pwi4.PWI4BadResponse, self.tel.getStatus)
        self.assertFalse(self.tel.focuserMoveAndWait(26000, '1'))

    def test_guess_focus_without_pwi4(self):
        self.fake.fail_mode = 'garbage'
        self.tel.guessFocus('1')
        self.assertAlmostEqual(self.tel.focus['1'], 23850.0)   # F0: no -99 C temperatures used

    def test_guess_focus_rejects_sentinel_temperatures(self):
        self.ready()
        self.fake.temperatures = {'primary': -999.0, 'secondary': -999.0, 'm3': -999.0, 'ambient': -999.0}
        self.tel._pwi4_temps = ({}, 0.0)
        self.tel.guessFocus('1')
        import math
        g = math.sin(math.radians(self.fake.alt))
        self.assertAlmostEqual(self.tel.focus['1'], 23850.0 + 434.6 * (g - 0.7777), places=3)

    def test_recover_reconnects(self):
        self.fake.connect_works = True
        self.assertTrue(self.tel.recover(tracking=True, derotate=False))
        self.assertIn('recovered after reconnecting', self.log.text())


class TestProcessControl(PWI4TestCase):

    def test_kill_and_start(self):
        self.ready()
        self.assertTrue(self.tel.killPWI())
        self.assertTrue(self.tel.startPWI())
        cmds = [argv[-1] for argv in FakePopen.calls]
        self.assertEqual(cmds, ['taskkill /IM PWI4.exe /f', 'schtasks /Run /TN "Start PWI4"'])
        self.assertEqual(FakePopen.calls[0][:3], ['sshpass', '-p', support.PASSWORD])
        self.assertNotIn(support.PASSWORD, self.log.text())
        self.assertIn('****', self.log.text())
        self.assertIn(('/mount/model/load', {'filename': 'T9_port1.dat'}), self.commands())

    def test_start_fails_if_pwi4_never_answers(self):
        self.tel.pwi4 = pwi4.PWI4Client('127.0.0.1', free_port(), timeout=0.2)
        t0 = time.time()
        self.assertFalse(self.tel.startPWI())
        self.assertLess(time.time() - t0, 10.0)

    def test_remote_command_timeout(self):
        FakePopen.hang = True
        t0 = time.time()
        self.assertFalse(self.tel.killPWI())
        self.assertLess(time.time() - t0, 5.0)
        self.assertNotIn(support.PASSWORD, self.log.text())

    def test_reboot_telcom_does_not_log_password(self):
        self.tel.reboot_telcom()
        self.assertNotIn(support.PASSWORD, self.log.text())


if __name__ == '__main__':
    unittest.main()
