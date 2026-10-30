"""PWI4 /status -> PWI2-shaped status tree (pwi4.legacy_status), no network."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
support.install_stubs()
import pwi4  # noqa: E402
from fake_pwi4_server import FakePWI4  # noqa: E402

ten = support._ten


def raw_status(**over):
    fake = FakePWI4()
    fake.mount_connected = True
    fake.axis_enabled = [True, True]
    fake.tracking = True
    fake.ra, fake.dec = 5.25, -0.5
    fake.alt, fake.az = 30.0, 270.0
    for k, v in over.items():
        setattr(fake, k, v)
    raw = pwi4.parse_status_text(fake.status_text())
    return fake, raw


class MappingTest(unittest.TestCase):

    def setUp(self):
        self.state = pwi4.DriverState()

    def test_mount_fields(self):
        fake, raw = raw_status()
        s = pwi4.legacy_status(raw, {}, self.state)
        self.assertEqual(s.mount.connected, 'True')
        self.assertEqual(s.mount.tracking, 'True')
        self.assertEqual(s.mount.moving, 'False')
        self.assertEqual(s.mount.alt_enabled, 'True')
        self.assertEqual(s.mount.azm_motor_error_message, 'No error')
        self.assertAlmostEqual(ten(s.mount.ra_2000), 5.25, places=6)   # hours
        self.assertAlmostEqual(ten(s.mount.dec_2000), -0.5, places=5)  # small negative dec keeps its sign
        self.assertTrue(s.mount.dec_2000.startswith('-00 30'))
        self.assertAlmostEqual(ten(s.mount.ra), 5.25, places=6)
        self.assertAlmostEqual(float(s.mount.alt_radian), math.radians(30.0))
        self.assertAlmostEqual(float(s.mount.azm_radian), math.radians(270.0))
        self.assertAlmostEqual(ten(s.status.lst), 5.5)
        self.assertEqual(s.mount.encoders_have_been_set, 'False')
        self.state.homed = True
        self.assertEqual(pwi4.legacy_status(raw, {}, self.state).mount.encoders_have_been_set, 'True')

    def test_homed_key_preferred_when_present(self):
        fake, raw = raw_status()
        raw['mount.axis0.is_homed'] = 'true'
        raw['mount.axis1.is_homed'] = 'false'
        self.state.homed = True
        self.assertEqual(pwi4.legacy_status(raw, {}, self.state).mount.encoders_have_been_set, 'False')

    def test_disabled_axis_is_reported_as_error(self):
        fake, raw = raw_status(axis_enabled=[True, False])
        s = pwi4.legacy_status(raw, {}, self.state)
        self.assertEqual(s.mount.alt_enabled, 'False')
        self.assertNotEqual(s.mount.alt_motor_error_code, '0')

    def test_m3_and_per_port_focusers(self):
        fake, raw = raw_status()
        s = pwi4.legacy_status(raw, {}, self.state)
        self.assertEqual(s.m3.port, '1')
        self.assertEqual(s.focuser1.position, '25000')      # integer microns, int() works
        self.assertEqual(int(s.focuser1.position), 25000)
        self.assertEqual(s.focuser2.position, 'UNKNOWN')    # not selected, never seen
        self.assertEqual(s.focuser.goto_complete, 'True')
        fake.m3_target = 2
        raw2 = pwi4.parse_status_text(fake.status_text())
        s2 = pwi4.legacy_status(raw2, {}, self.state)
        self.assertEqual(s2.m3.port, '2')
        self.assertEqual(s2.focuser2.position, '24000')
        self.state.last_focus['1'] = 25000.0
        self.assertEqual(pwi4.legacy_status(raw2, {}, self.state).focuser1.position, '25000')

    def test_m3_between_ports(self):
        fake, raw = raw_status(m3_stuck=True)
        s = pwi4.legacy_status(raw, {}, self.state)
        self.assertEqual(s.m3.port, '0')
        self.assertEqual(s.m3.moving_rotate, 'True')

    def test_rotator_positions(self):
        fake, raw = raw_status()
        s = pwi4.legacy_status(raw, {}, self.state)
        self.assertAlmostEqual(float(s.rotator1.position), 180.0)   # Rotator1 mech reported directly
        self.assertEqual(s.rotator2.position, 'UNKNOWN')
        fake.m3_target = 2
        raw2 = pwi4.parse_status_text(fake.status_text())
        s2 = pwi4.legacy_status(raw2, {}, self.state)
        self.assertAlmostEqual(float(s2.rotator2.position), 90.0)   # derived from field angle
        self.assertAlmostEqual(float(s2.rotator1.position), 180.0)

    def test_derotation_flags(self):
        fake, raw = raw_status()
        s = pwi4.legacy_status(raw, {}, self.state)
        self.assertEqual(s.rotator.altaz_derotate, 'False')
        self.assertEqual(s.rotator1.goto_complete, 'True')
        field = float(raw['rotator.field_angle_degs'])
        fake.field_target[0] = field
        self.state.derotate['1'] = field
        raw2 = pwi4.parse_status_text(fake.status_text())
        s2 = pwi4.legacy_status(raw2, {}, self.state)
        self.assertEqual(s2.rotator.altaz_derotate, 'True')
        self.assertEqual(s2.rotator1.goto_complete, 'True')
        self.state.derotate['1'] = field + 10.0
        self.assertEqual(pwi4.legacy_status(raw2, {}, self.state).rotator1.goto_complete, 'False')

    def test_temperatures(self):
        fake, raw = raw_status()
        s = pwi4.legacy_status(raw, {'primary': '12.500', 'ambient': '-999.000', 'm3': 'nan'}, self.state)
        self.assertEqual(float(s.temperature.primary), 12.5)
        self.assertEqual(s.temperature.ambient, 'UNKNOWN')   # PWI4 sentinel rejected
        self.assertEqual(s.temperature.m3, 'UNKNOWN')
        self.assertEqual(s.temperature.backplate, 'UNKNOWN')  # PWI4 has no backplate sensor
        self.assertRaises(ValueError, float, s.temperature.ambient)  # callers' try/float falls back

    def test_sexagesimal_rounding(self):
        self.assertEqual(pwi4.sexagesimal(23.99999999, hours=True), '00 00 00.000')
        self.assertEqual(pwi4.sexagesimal(-10.999999999, signed=True, places=2), '-11 00 00.00')
        self.assertEqual(pwi4.sexagesimal(None), 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
