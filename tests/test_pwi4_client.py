"""pwi4.PWI4Client against the fake server: requests, timeouts and failures."""
import os
import socket
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import support  # noqa: E402
support.install_stubs()
import pwi4  # noqa: E402
from fake_pwi4_server import FakePWI4Server  # noqa: E402


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class ClientTest(unittest.TestCase):

    def setUp(self):
        self.server = FakePWI4Server().start()
        self.client = pwi4.PWI4Client('127.0.0.1', self.server.port, timeout=1.0)

    def tearDown(self):
        self.server.stop()

    def test_status_parses(self):
        raw = self.client.status()
        self.assertEqual(raw['pwi4.version'], '4.1.4.99')
        self.assertEqual(raw['m3.port'], '1')
        self.assertEqual(raw['mount.is_connected'], 'false')

    def test_make_url_sorted_and_percent20(self):
        url = self.client.make_url('/mount/goto_ra_dec_j2000', ra_hours=1.5, dec_degs=-2.25, skip=None)
        self.assertEqual(url, 'http://127.0.0.1:%d/mount/goto_ra_dec_j2000?dec_degs=-2.25&ra_hours=1.5'
                         % self.server.port)
        self.assertTrue(self.client.make_url('/x', a='b c').endswith('?a=b%20c'))

    def test_command_params_reach_server(self):
        self.client.request_status('/m3/goto', port='2')
        self.assertEqual(self.server.fake.requests[-1], ('/m3/goto', {'port': '2'}))

    def test_hang_times_out(self):
        self.server.fake.fail_mode = 'hang'
        self.server.fake.hang_seconds = 5.0
        t0 = time.time()
        self.assertRaises(pwi4.PWI4Unreachable, self.client.status)
        self.assertLess(time.time() - t0, 3.0)

    def test_connection_refused(self):
        client = pwi4.PWI4Client('127.0.0.1', free_port(), timeout=1.0)
        t0 = time.time()
        self.assertRaises(pwi4.PWI4Unreachable, client.status)
        self.assertLess(time.time() - t0, 2.0)

    def test_closed_without_answer(self):
        self.server.fake.fail_mode = 'close'
        self.assertRaises(pwi4.PWI4Unreachable, self.client.status)

    def test_garbage(self):
        self.server.fake.fail_mode = 'garbage'
        self.assertRaises(pwi4.PWI4BadResponse, self.client.status)

    def test_http_errors(self):
        try:
            self.client.request_status('/mount/enable', axis=-1)
        except pwi4.PWI4CommandError as e:
            self.assertEqual(e.code, 400)
        else:
            self.fail('no error')
        self.assertRaises(pwi4.PWI4CommandError, self.client.request_status, '/no/such/command')
        self.server.fake.fail_mode = 'http500'
        self.assertRaises(pwi4.PWI4CommandError, self.client.status)

    def test_temperatures(self):
        temps = self.client.temperatures()
        self.assertEqual(float(temps['primary']), 12.5)
        self.server.fake.temperatures_exist = False
        self.assertEqual(self.client.temperatures(), {})


class ParseTest(unittest.TestCase):

    def test_parse_status_text(self):
        d = pwi4.parse_status_text('a=1\r\nb=x=y\nnoequals\n\n')
        self.assertEqual(d, {'a': '1', 'b': 'x=y'})

    def test_to_hours_degrees(self):
        self.assertAlmostEqual(pwi4.to_hours('10 30 00'), 10.5)
        self.assertAlmostEqual(pwi4.to_degrees('-00 30 00'), -0.5)
        self.assertAlmostEqual(pwi4.to_degrees(12), 12.0)
        self.assertRaises(ValueError, pwi4.to_hours, 'nonsense')


if __name__ == '__main__':
    unittest.main()
