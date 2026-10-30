"""A small fake PWI4 HTTP server for tests (Python 2.7, stdlib only).

It implements the PWI4 endpoints that cdk700's PWI4 path uses, answers with
/status text in PWI4 4.1.4's key order and formats, and simulates timing:
mount slews and homing, M3 port changes, focuser and rotator moves, and
field-angle tracking (derotation).  It models the PWI4 behaviour that matters
for a two-port CDK700:

* focuser.* and rotator field angle / is_moving / is_slewing follow the
  GUI-selected device, which follows the M3 port ("Select from M3");
* rotator.is_connected / mech_position_degs always describe Rotator1;
* /focuser/connect, /rotator/connect and /rotator/enable act on index 0;
* /focuser/find_home and /rotator/find_home take index=0|1.

Failure modes for tests: `fail_mode` is one of None, 'hang', 'garbage',
'http500', 'close'; `fail_paths` restricts it to some paths.

Manual use (for daytime checks of cdk700 without PWI4):
    python2 tests/fake_pwi4_server.py --port 8220
"""
import BaseHTTPServer
import SocketServer
import re
import threading
import time
import urlparse


class Device(object):
    def __init__(self, position):
        self.position = float(position)
        self.start = float(position)
        self.target = float(position)
        self.t0 = 0.0
        self.t1 = 0.0
        self.connected = False
        self.enabled = False
        self.homing_until = 0.0

    def goto(self, target, duration, now):
        self.start = self.current(now)
        self.target = float(target)
        self.t0 = now
        self.t1 = now + duration

    def current(self, now):
        if now >= self.t1:
            return self.target
        frac = (now - self.t0) / max(1e-9, self.t1 - self.t0)
        return self.start + (self.target - self.start) * frac

    def moving(self, now):
        return now < self.t1 or now < self.homing_until


class FakePWI4(object):
    def __init__(self):
        self.lock = threading.RLock()
        self.requests = []
        self.fail_mode = None
        self.fail_paths = None
        self.hang_seconds = 30.0
        # timing (seconds)
        self.slew_time = 0.4
        self.home_time = 0.5
        self.m3_time = 0.2
        self.select_lag = 0.05
        self.focuser_time = 0.3
        self.rotator_time = 0.3
        self.connect_works = True
        self.m3_stuck = False
        self.home_reports_slewing = False
        # state
        self.mount_connected = False
        self.axis_enabled = [False, False]
        self.tracking = False
        self.ra = 2.0
        self.dec = 10.0
        self.alt = 45.0
        self.az = 180.0
        self.target_ra = 2.0
        self.target_dec = 10.0
        self.slew_until = 0.0
        self.home_until = 0.0
        self.offsets = {}
        self.model_files = set(['T9_port1.dat', 'T9_port2.dat'])
        self.model = ''
        self.m3_port = 1
        self.m3_target = 1
        self.m3_until = 0.0
        self.focusers = [Device(25000.0), Device(24000.0)]
        self.rotators = [Device(180.0), Device(90.0)]
        self.field_target = [None, None]
        self.field_at_target = 30.0
        self.field_offset = [0.0, 0.0]
        self.temperatures = {'primary': 12.5, 'secondary': 12.0, 'm3': 11.5, 'ambient': 10.0}
        self.temperatures_exist = True
        self.focusers[1].connected = True  # port-2 devices auto-connected by PWI4
        self.rotators[1].connected = True

    # -- derived state ---------------------------------------------------
    def now(self):
        return time.time()

    def current_port(self, now):
        if now < self.m3_until or self.m3_stuck:
            return 0
        return self.m3_target

    def selected(self, now):
        port = self.current_port(now)
        if port == 0 or now < self.m3_until + self.select_lag:
            return self._last_selected
        self._last_selected = port - 1
        return self._last_selected

    _last_selected = 0

    def mech(self, idx, now):
        if self.field_target[idx] is not None and now >= self.rotators[idx].t1:
            return (self.field_at_target + self.field_offset[idx] - self.field_target[idx]) % 360.0
        return self.rotators[idx].current(now) % 360.0

    def field(self, idx, now):
        return (self.field_at_target + self.field_offset[idx] - self.mech(idx, now)) % 360.0

    def slewing(self, now):
        if now < self.slew_until:
            return True
        return self.home_reports_slewing and now < self.home_until

    # -- status text -----------------------------------------------------
    def status_text(self):
        now = self.now()
        sel = self.selected(now)
        foc = self.focusers[sel]
        rot = self.rotators[sel]
        moving_mount = now < self.slew_until or now < self.home_until
        lines = [
            ('pwi4.version', '4.1.4.99'),
            ('pwi4.version_field[0]', '4'), ('pwi4.version_field[1]', '1'),
            ('pwi4.version_field[2]', '4'), ('pwi4.version_field[3]', '99'),
            ('response.timestamp_utc', time.strftime('%Y-%m-%d %H:%M:%S.000000', time.gmtime(now))),
            ('site.latitude_degs', '31.680407'), ('site.longitude_degs', '-110.878977'),
            ('site.height_meters', '2316'), ('site.lmst_hours', '5.5'),
            ('mount.is_connected', b(self.mount_connected)),
            ('mount.geometry', '0'),
            ('mount.timestamp_utc', time.strftime('%Y-%m-%d %H:%M:%S.0000', time.gmtime(now))),
            ('mount.julian_date', '2461343.5'),
            ('mount.update_duration_msec', '12'), ('mount.update_count', '1000'),
            ('mount.slew_time_constant', '0.5'),
            ('mount.ra_apparent_hours', f(self.ra)), ('mount.dec_apparent_degs', f(self.dec)),
            ('mount.ra_j2000_hours', f(self.ra)), ('mount.dec_j2000_degs', f(self.dec)),
            ('mount.target_ra_apparent_hours', f(self.target_ra)),
            ('mount.target_dec_apparent_degs', f(self.target_dec)),
            ('mount.azimuth_degs', f(self.az)), ('mount.altitude_degs', f(self.alt)),
            ('mount.is_slewing', b(self.slewing(now))),
            ('mount.is_tracking', b(self.tracking)),
            ('mount.field_angle_here_degs', f(self.field_at_target)),
            ('mount.field_angle_at_target_degs', f(self.field_at_target)),
            ('mount.field_angle_rate_at_target_degs_per_sec', '0'),
            ('mount.path_angle_at_target_degs', '0'),
            ('mount.path_angle_rate_at_target_degs_per_sec', '0'),
            ('mount.distance_to_sun_degs', '120'),
            ('mount.axis0_wrap_range_min_degs', '-180'),
        ]
        for axis in ('ra', 'dec', 'axis0', 'axis1', 'path', 'transverse'):
            key = 'mount.offsets.%s_arcsec' % axis
            lines += [(key + '.total', f(self.offsets.get(axis, 0.0))), (key + '.rate', '0'),
                      (key + '.gradual_offset_progress', '0')]
        lines += [('mount.spiral_offset.x', '0'), ('mount.spiral_offset.y', '0'),
                  ('mount.spiral_offset.x_step_arcsec', '0'), ('mount.spiral_offset.y_step_arcsec', '0')]
        for axis in (0, 1):
            p = 'mount.axis%d.' % axis
            lines += [(p + 'is_enabled', b(self.axis_enabled[axis])),
                      (p + 'rms_error_arcsec', '0.1'), (p + 'dist_to_target_arcsec', '0'),
                      (p + 'servo_error_arcsec', '0'), (p + 'min_mech_position_degs', '-270'),
                      (p + 'max_mech_position_degs', '270'), (p + 'target_mech_position_degs', '0'),
                      (p + 'position_degs', f(self.az if axis == 0 else self.alt)),
                      (p + 'position_timestamp', 'x'), (p + 'max_velocity_degs_per_sec', '10'),
                      (p + 'setpoint_velocity_degs_per_sec', '2.5' if moving_mount else '0'),
                      (p + 'measured_velocity_degs_per_sec', '2.5' if moving_mount else '0'),
                      (p + 'acceleration_degs_per_sec_sqr', '0'), (p + 'measured_current_amps', '0')]
        lines += [('mount.model.filename', self.model), ('mount.model.num_points_total', '0'),
                  ('mount.model.num_points_enabled', '0'), ('mount.model.rms_error_arcsec', '0'),
                  ('focuser.exists', 'true'),
                  ('focuser.is_connected', b(foc.connected)), ('focuser.is_enabled', b(foc.enabled)),
                  ('focuser.position', f(foc.current(now))), ('focuser.is_moving', b(foc.moving(now))),
                  ('rotator.exists', 'true'),
                  ('rotator.is_connected', b(self.rotators[0].connected)),
                  ('rotator.is_enabled', b(self.rotators[0].enabled)),
                  ('rotator.mech_position_degs', f(self.mech(0, now))),
                  ('rotator.field_angle_degs', f(self.field(sel, now))),
                  ('rotator.is_moving', b(rot.moving(now) or self.field_target[sel] is not None)),
                  ('rotator.is_slewing', b(rot.moving(now) or self.field_target[sel] is not None)),
                  ('m3.exists', '1'), ('m3.port', str(self.current_port(now))),
                  ('autofocus.is_running', 'false'), ('autofocus.success', 'false'),
                  ('autofocus.best_position', '0'), ('autofocus.tolerance', '0')]
        return '\n'.join('%s=%s' % kv for kv in lines) + '\n'

    # -- command handling ---------------------------------------------------
    def handle(self, path, q):
        """Return (http_code, body)."""
        now = self.now()
        p = lambda k: q.get(k, [None])[0]
        if path == '/status':
            return 200, self.status_text()
        if path == '/temperatures/pw1000':
            if not self.temperatures_exist:
                return 404, 'not found'
            return 200, ''.join('temperature.%s=%.3f\n' % kv for kv in sorted(self.temperatures.items()))
        if path == '/mount/connect':
            self.mount_connected = self.connect_works
        elif path == '/mount/disconnect':
            self.mount_connected = False
        elif path in ('/mount/enable', '/mount/disable'):
            axis = p('axis')
            if axis not in ('0', '1'):
                return 400, 'Invalid value for axis: %s. Must be 0 or 1' % axis
            self.axis_enabled[int(axis)] = (path == '/mount/enable') and self.mount_connected
        elif path == '/mount/find_home':
            self.home_until = now + self.home_time
        elif path == '/mount/stop':
            self.slew_until = 0.0
            self.tracking = False
        elif path in ('/mount/goto_ra_dec_j2000', '/mount/goto_ra_dec_apparent'):
            try:
                ra, dec = float(p('ra_hours')), float(p('dec_degs'))
            except (TypeError, ValueError):
                return 400, 'Invalid ra/dec parameters'
            self.target_ra, self.target_dec = ra, dec
            self.ra, self.dec = ra, dec
            self.alt, self.az = 60.0, 120.0
            self.slew_until = now + self.slew_time
            self.tracking = True
        elif path == '/mount/goto_alt_az':
            self.alt, self.az = float(p('alt_degs')), float(p('az_degs'))
            self.slew_until = now + self.slew_time
            self.tracking = False
        elif path == '/mount/tracking_on':
            self.tracking = True
        elif path == '/mount/tracking_off':
            self.tracking = False
        elif path == '/mount/offset':
            for key, values in q.items():
                m = re.match(r'^(ra|dec|axis0|axis1|path|transverse)_(add_arcsec|set_rate_arcsec_per_sec)$', key)
                if not m:
                    return 400, 'Unknown parameter %s' % key
                if m.group(2) == 'add_arcsec':
                    self.offsets[m.group(1)] = self.offsets.get(m.group(1), 0.0) + float(values[0])
        elif path == '/mount/model/load':
            name = p('filename')
            if not name or not re.match(r'^[a-zA-Z0-9._]+$', name):
                return 400, "filename: only letters, numbers, '.', and '_' allowed"
            self.model = name
        elif path == '/mount/model/save':
            self.model_files.add(p('filename'))
        elif path == '/mount/model/add_point':
            pass
        elif path == '/m3/goto':
            port = p('port')
            if port not in ('1', '2'):
                return 400, "Invalid value for 'port'. Must be 1 or 2"
            if int(port) != self.m3_target or self.m3_stuck:
                self.m3_target = int(port)
                self.m3_until = now + self.m3_time
        elif path == '/m3/stop':
            pass
        elif path in ('/focuser/connect', '/focuser/disconnect'):
            self.focusers[0].connected = (path == '/focuser/connect') and self.connect_works
        elif path in ('/focuser/enable', '/focuser/disable'):
            self.focusers[self.selected(now)].enabled = path.endswith('enable')
        elif path == '/focuser/goto':
            dev = self.focusers[self.selected(now)]
            dev.goto(float(p('target')), self.focuser_time, now)
        elif path == '/focuser/stop':
            dev = self.focusers[self.selected(now)]
            dev.goto(dev.current(now), 0.0, now)
        elif path in ('/focuser/find_home', '/rotator/find_home'):
            idx = int(p('index') or 0)
            devs = self.focusers if path.startswith('/focuser') else self.rotators
            if idx not in (0, 1):
                return 400, 'index {0} does not exist'.format(idx)
            devs[idx].homing_until = now + self.focuser_time
            if path.startswith('/rotator'):
                self.field_target[idx] = None
        elif path in ('/rotator/connect', '/rotator/disconnect'):
            self.rotators[0].connected = (path == '/rotator/connect') and self.connect_works
        elif path == '/rotator/enable':
            self.rotators[0].enabled = True
        elif path == '/rotator/goto_mech':
            sel = self.selected(now)
            self.field_target[sel] = None
            current = self.mech(sel, now)
            self.field_target[sel] = None
            self.rotators[sel].goto(current, 0.0, now)
            self.rotators[sel].goto(float(p('degs')), self.rotator_time, now)
        elif path == '/rotator/goto_field':
            sel = self.selected(now)
            target = float(p('degs'))
            mech = (self.field_at_target + self.field_offset[sel] - target) % 360.0
            self.rotators[sel].goto(mech, self.rotator_time, now)
            self.field_target[sel] = target
        elif path == '/rotator/offset':
            sel = self.selected(now)
            if self.field_target[sel] is not None:
                self.field_target[sel] += float(p('degs'))
        elif path == '/rotator/stop':
            sel = self.selected(now)
            self.rotators[sel].goto(self.mech(sel, now), 0.0, now)
            self.field_target[sel] = None
        elif path in ('/fans/on', '/fans/off', '/autofocus/start'):
            pass
        else:
            return 404, 'Command not found'
        return 200, self.status_text()


def b(value):
    return 'true' if value else 'false'


def f(value):
    return repr(float(value))


class _Handler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        fake = self.server.fake
        parsed = urlparse.urlparse(self.path)
        query = urlparse.parse_qs(parsed.query, keep_blank_values=True)
        with fake.lock:
            fake.requests.append((parsed.path, dict((k, v[0]) for k, v in query.items())))
            mode = fake.fail_mode
            if fake.fail_paths is not None and parsed.path not in fake.fail_paths:
                mode = None
        if mode == 'hang':
            time.sleep(fake.hang_seconds)
            return
        if mode == 'close':
            self.close_connection = 1
            return
        if mode == 'garbage':
            code, body = 200, '<html>PWI is starting...</html>'
        elif mode == 'http500':
            code, body = 500, 'Internal server error'
        else:
            with fake.lock:
                code, body = fake.handle(parsed.path, query)
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _Server(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class FakePWI4Server(object):
    """Run a FakePWI4 on 127.0.0.1 (ephemeral port by default) in a thread."""

    def __init__(self, port=0, fake=None):
        self.fake = fake or FakePWI4()
        self.httpd = _Server(('127.0.0.1', port), _Handler)
        self.httpd.fake = self.fake
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def paths(self):
        return [p for p, _ in self.fake.requests]

    def commands(self):
        """Requests other than /status and /temperatures."""
        return [(p, q) for p, q in self.fake.requests if p not in ('/status', '/temperatures/pw1000')]


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--port', type=int, default=8220)
    args = parser.parse_args()
    server = FakePWI4Server(args.port)
    print('fake PWI4 listening on 127.0.0.1:%d (Ctrl-C to stop)' % server.port)
    try:
        server.httpd.serve_forever()
    except KeyboardInterrupt:
        server.stop()

