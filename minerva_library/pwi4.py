"""PlaneWave PWI4 HTTP client and PWI2-compatible status mapping for cdk700.

cdk700.CDK700 uses this module when a telescope's config file sets
PWI_VERSION = 4.  PWI2 telescopes never import anything from here.

PWI4 API reference
------------------
Endpoints, parameter names and /status keys were checked against two
primary sources (see docs/pwi4.md for the full list):

* PlaneWave's reference client pwi4_client.py (shipped with PWI4), and
* the PWI4 4.1.4 binary itself (PWI4.exe, route table and the IL of its
  HTTP handlers, e.g. MainModule::Status, ::M3Goto, ::FocuserGoto).

Facts from the 4.1.4 binary that shape this module:

* /status is "key=value" lines.  Booleans are "true"/"false"; m3.port is
  an integer (1, 2; 0 = between ports or no M3).
* /status has NO temperatures; GET /temperatures/pw1000 returns
  temperature.primary/secondary/m3/ambient (-999 when there is no PW1000
  ACR controller).  There is no backplate temperature in PWI4.
* focuser.* in /status, and /focuser/goto|stop|enable, act on the focuser
  that is *selected in the PWI4 GUI*.  With "Select from M3" ticked on the
  Focuser and Rotator tabs that selection follows the M3 port (updated by
  the GUI's refresh timer).  /focuser/connect, /rotator/connect and
  /rotator/enable always act on device index 0 (Focuser1/Rotator1).
* rotator.is_connected, rotator.is_enabled and rotator.mech_position_degs
  always describe Rotator index 0 (Rotator1); rotator.field_angle_degs,
  rotator.is_moving and rotator.is_slewing describe the selected rotator.
* /mount/offset ra_* values are arcsec of the RA *coordinate* (scaled by
  1/3600 and added to the target RA; no cos(dec) factor), like PWI2's
  incrementra.
* /mount/goto_ra_dec_* need decimal numbers (ParseDoubleStrict), not
  sexagesimal strings.
* /mount/model/load|save accept only filenames matching ^[a-zA-Z0-9._]+$.

Every request has a timeout.  Failures raise PWI4Error subclasses; this
module never fabricates a status.
"""
import math
import re
import socket
import urllib
import urllib2
import httplib

DEFAULT_PORT = 8220
DEFAULT_TIMEOUT = 10.0
UNKNOWN = 'UNKNOWN'
MODEL_FILENAME_RE = re.compile(r'^[a-zA-Z0-9._]+$')


class PWI4Error(Exception):
    """Any failure talking to PWI4."""


class PWI4Unreachable(PWI4Error):
    """Connection refused, timed out, or dropped (PWI4 not answering)."""


class PWI4CommandError(PWI4Error):
    """PWI4 answered with an HTTP error (bad command or parameters)."""

    def __init__(self, message, code=None, body=''):
        PWI4Error.__init__(self, message)
        self.code = code
        self.body = body


class PWI4BadResponse(PWI4Error):
    """PWI4 answered with something that is not a PWI4 status."""


def parse_status_text(text):
    """Parse PWI4 "key=value" lines into a dict (same rules as pwi4_client)."""
    result = {}
    for line in text.split('\n'):
        fields = line.rstrip('\r').split('=', 1)
        if len(fields) == 2:
            result[fields[0]] = fields[1]
    return result


class PWI4Client(object):
    """Minimal PWI4 HTTP client (Python 2, stdlib only)."""

    def __init__(self, host, port=DEFAULT_PORT, timeout=DEFAULT_TIMEOUT):
        self.host = host
        self.port = int(port)
        self.timeout = float(timeout)

    def make_url(self, path, **params):
        params = [(k, v) for k, v in sorted(params.items()) if v is not None]
        url = 'http://%s:%d%s' % (self.host, self.port, path)
        if params:
            # like pwi4_client: encode spaces as %20 rather than '+'
            url += '?' + urllib.urlencode(params).replace('+', '%20')
        return url

    def request(self, path, timeout=None, **params):
        """GET path; return the body text.  Raises PWI4Error on any failure."""
        url = self.make_url(path, **params)
        if timeout is None:
            timeout = self.timeout
        try:
            response = urllib2.urlopen(url, timeout=timeout)
            try:
                return response.read()
            finally:
                response.close()
        except urllib2.HTTPError as e:
            try:
                body = e.read()
            except Exception:
                body = ''
            raise PWI4CommandError('PWI4 %s returned HTTP %s: %s' % (path, e.code, body.strip()[:200]),
                                   code=e.code, body=body)
        except urllib2.URLError as e:
            raise PWI4Unreachable('PWI4 %s:%d unreachable (%s): %s' % (self.host, self.port, path, e.reason))
        except (socket.timeout, socket.error, httplib.HTTPException) as e:
            raise PWI4Unreachable('PWI4 %s:%d no answer to %s within %.1f s (%s: %s)'
                                  % (self.host, self.port, path, timeout, e.__class__.__name__, e))

    def request_status(self, path, timeout=None, **params):
        """Send a command that answers with a full status; return it as a dict."""
        text = self.request(path, timeout=timeout, **params)
        status = parse_status_text(text)
        if 'pwi4.version' not in status or 'mount.is_connected' not in status:
            raise PWI4BadResponse('PWI4 %s: response is not a PWI4 status: %r' % (path, text[:200]))
        return status

    def status(self):
        return self.request_status('/status')

    def temperatures(self):
        """Return {'primary':..,'secondary':..,'m3':..,'ambient':..} as strings, or {}.

        /temperatures/pw1000 is not in pwi4_client.py; it exists in PWI4
        4.1.4.  A 404 (older/newer PWI4) gives {} rather than an error.
        """
        try:
            text = self.request('/temperatures/pw1000')
        except PWI4CommandError as e:
            if e.code == 404:
                return {}
            raise
        out = {}
        for key, value in parse_status_text(text).items():
            if key.startswith('temperature.'):
                out[key[len('temperature.'):]] = value
        return out


# ---------------------------------------------------------------------------
# PWI2-compatible status tree
# ---------------------------------------------------------------------------

class Section(object):
    """Attribute bag mirroring cdk700.Status (values are strings, as in PWI2)."""

    def __str__(self):
        result = ""
        for k, v in self.__dict__.items():
            result += "%s: %s\n" % (k, str(v))
        return result


def _section(**values):
    s = Section()
    for k, v in values.items():
        setattr(s, k, v)
    return s


def _bool(raw, key):
    value = raw.get(key)
    if value is None:
        return UNKNOWN
    return 'True' if value.strip().lower() == 'true' else 'False'


def _float(raw, key):
    try:
        value = float(raw[key])
    except (KeyError, ValueError, TypeError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def sexagesimal(value, hours=False, signed=False, places=3):
    """Format like PWI2: 'HH MM SS.SSS' (RA/LST) or '+DD MM SS.SS' (Dec).

    The output parses with utils.ten().
    """
    if value is None:
        return UNKNOWN
    if hours:
        value = value % 24.0
    sign = '-' if value < 0 else '+'
    total = abs(value) * 3600.0
    scale = 10 ** places
    total = round(total * scale) / scale
    d = int(total // 3600)
    m = int((total - d * 3600) // 60)
    s = total - d * 3600 - m * 60
    if s >= 60.0 - 0.5 / scale:
        s = 0.0
        m += 1
    if m >= 60:
        m -= 60
        d += 1
    if hours:
        d = d % 24
    text = '%02d %02d %0*.*f' % (d, m, places + 3, places, s)
    return (sign + text) if signed else text


def wrap180(angle):
    return (angle + 180.0) % 360.0 - 180.0


def _num(value, integer=False):
    if value is None:
        return UNKNOWN
    if integer:
        return str(int(round(value)))
    return repr(float(value))


def good_temperature(text):
    """Return a float temperature, or None for missing / sentinel values."""
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or value <= -99.0 or value > 80.0:
        return None
    return value


class DriverState(object):
    """What cdk700 itself knows that PWI4 does not report.

    derotate[port]  : target field angle (deg) while cdk700 has derotation on
    resume_derotate[port] : a rotatorMove() interrupted derotation; it resumes
                      at the next rotatorStartDerotating() (inPosition does this)
    homing          : True while cdk700 is waiting for /mount/find_home
    homed           : cdk700 saw a successful home in this process
    focuser_homing  : {port: bool}
    rotator_homing  : {port: bool}
    last_focus      : {port: microns} last focuser position seen on that port
    last_rotator    : {port: degs} last mech position seen/commanded
    rotator_status_port : M3 port of PWI4's Rotator index 0 (default '1')
    rotator_field_offset : {port: degs} PWI4 "Position angle offset" setting
    """

    def __init__(self, rotator_status_port='1', rotator_field_offset=None):
        self.derotate = {'1': None, '2': None}
        self.resume_derotate = {'1': False, '2': False}
        self.homing = False
        self.homed = False
        self.focuser_homing = {'1': False, '2': False}
        self.rotator_homing = {'1': False, '2': False}
        self.last_focus = {}
        self.last_rotator = {}
        self.rotator_status_port = str(rotator_status_port)
        self.rotator_field_offset = rotator_field_offset or {'1': 0.0, '2': 0.0}


def m3_port(raw):
    try:
        return str(int(float(raw.get('m3.port', '0'))))
    except ValueError:
        return '0'


def rotator_mech_position(raw, port, state):
    """Mechanical rotator angle (deg) for an M3 port, or None if unknown.

    * The port of PWI4's Rotator index 0: rotator.mech_position_degs.
    * The other port, while the M3 is on it (so it is the GUI-selected
      rotator): derived from the reported field angle by inverting PWI4's
      ucRotatorControl.ConvertFieldAngle, assuming the PWI4 rotator
      settings "reverse positive direction" and "altitude compensation" are
      off:  field = field_angle_at_target + offset - mech.
    """
    port = str(port)
    if port == state.rotator_status_port:
        return _float(raw, 'rotator.mech_position_degs')
    if m3_port(raw) == port:
        target = _float(raw, 'mount.field_angle_at_target_degs')
        field = _float(raw, 'rotator.field_angle_degs')
        if target is None or field is None:
            return None
        offset = float(state.rotator_field_offset.get(port, 0.0))
        return (target + offset - field) % 360.0
    return None


def legacy_status(raw, temps, state):
    """Build a PWI2-shaped status tree from a PWI4 /status dict.

    raw   : dict from PWI4Client.status()
    temps : dict from PWI4Client.temperatures() (may be {})
    state : DriverState

    See docs/pwi4.md ("Status-field mapping") for the table.  Values are
    strings, as PWI2's XML produced; anything PWI4 does not report is the
    string 'UNKNOWN' (never a made-up number).
    """
    port = m3_port(raw)
    slewing = _bool(raw, 'mount.is_slewing')
    tracking = _bool(raw, 'mount.is_tracking')
    connected = _bool(raw, 'mount.is_connected')
    az_en = _bool(raw, 'mount.axis0.is_enabled')
    alt_en = _bool(raw, 'mount.axis1.is_enabled')

    ra_app = _float(raw, 'mount.ra_apparent_hours')
    dec_app = _float(raw, 'mount.dec_apparent_degs')
    alt = _float(raw, 'mount.altitude_degs')
    az = _float(raw, 'mount.azimuth_degs')

    def rad(x):
        return UNKNOWN if x is None else repr(math.radians(x))

    def motor(enabled, code):
        if enabled == 'True':
            return ('0', 'No error') if code else 'No error'
        return ('-1', 'Axis not enabled') if code else 'Axis not enabled'

    if 'mount.axis0.is_homed' in raw and 'mount.axis1.is_homed' in raw:
        homed = 'True' if (_bool(raw, 'mount.axis0.is_homed') == 'True' and
                           _bool(raw, 'mount.axis1.is_homed') == 'True') else 'False'
    else:
        homed = 'True' if state.homed else 'False'

    mount = _section(
        connected=connected,
        on_target='True' if (connected == 'True' and slewing == 'False' and tracking == 'True') else 'False',
        moving=slewing,
        tracking=tracking,
        ra=sexagesimal(ra_app, hours=True),
        dec=sexagesimal(dec_app, signed=True, places=2),
        ra_target=sexagesimal(_float(raw, 'mount.target_ra_apparent_hours'), hours=True),
        dec_target=sexagesimal(_float(raw, 'mount.target_dec_apparent_degs'), signed=True, places=2),
        ra_2000=sexagesimal(_float(raw, 'mount.ra_j2000_hours'), hours=True),
        dec_2000=sexagesimal(_float(raw, 'mount.dec_j2000_degs'), signed=True, places=2),
        ra_radian=UNKNOWN if ra_app is None else repr(ra_app * math.pi / 12.0),
        dec_radian=rad(dec_app),
        azm_radian=rad(az),
        alt_radian=rad(alt),
        azm_rms_error_arcsec=_num(_float(raw, 'mount.axis0.rms_error_arcsec')),
        alt_rms_error_arcsec=_num(_float(raw, 'mount.axis1.rms_error_arcsec')),
        azm_motor_error_code=motor(az_en, True)[0],
        alt_motor_error_code=motor(alt_en, True)[0],
        azm_motor_error_message=motor(az_en, False),
        alt_motor_error_message=motor(alt_en, False),
        azm_enabled=az_en,
        alt_enabled=alt_en,
        pointing_model=raw.get('mount.model.filename', UNKNOWN) or UNKNOWN,
        is_finding_home='True' if state.homing else 'False',
        encoders_have_been_set=homed,
    )

    timestamp = raw.get('response.timestamp_utc', '')
    status = _section(
        utc=timestamp.split(' ')[-1] if timestamp else UNKNOWN,
        lst=sexagesimal(_float(raw, 'site.lmst_hours'), hours=True),
        jd=raw.get('mount.julian_date', UNKNOWN),
    )

    # --- focusers: PWI4 reports only the GUI-selected (= M3 port) focuser
    f_conn = _bool(raw, 'focuser.is_connected')
    f_pos = _float(raw, 'focuser.position')
    f_moving = _bool(raw, 'focuser.is_moving')
    focuser = _section(connected=f_conn, position=_num(f_pos, integer=True), unit='Micron',
                       moving=f_moving,
                       goto_complete={'True': 'False', 'False': 'True'}.get(f_moving, UNKNOWN))
    focusers = {}
    for p in ('1', '2'):
        homing = 'True' if state.focuser_homing.get(p) else 'False'
        if p == port:
            focusers[p] = _section(connected=f_conn, position=focuser.position, unit='Micron',
                                   moving=f_moving, goto_complete=focuser.goto_complete,
                                   finding_home=homing)
        else:
            last = state.last_focus.get(p)
            focusers[p] = _section(connected=UNKNOWN, position=_num(last, integer=True), unit='Micron',
                                   moving=UNKNOWN, goto_complete=UNKNOWN, finding_home=homing)

    # --- rotators
    r_moving = _bool(raw, 'rotator.is_moving')
    r_slewing = _bool(raw, 'rotator.is_slewing')
    field = _float(raw, 'rotator.field_angle_degs')
    rotators = {}
    for p in ('1', '2'):
        mech = rotator_mech_position(raw, p, state)
        if mech is None:
            mech = state.last_rotator.get(p)
        homing = 'True' if state.rotator_homing.get(p) else 'False'
        if p == port:
            target = state.derotate.get(p)
            if target is not None:
                if r_slewing != 'True' or field is None:
                    complete = 'False'
                else:
                    complete = 'True' if abs(wrap180(field - target)) < 0.5 else 'False'
            else:
                complete = {'True': 'False', 'False': 'True'}.get(r_slewing, UNKNOWN)
            moving = r_moving
        else:
            complete = UNKNOWN
            moving = UNKNOWN
        rotators[p] = _section(
            connected=_bool(raw, 'rotator.is_connected') if p == state.rotator_status_port else UNKNOWN,
            position=_num(mech), unit='Degree', moving=moving, goto_complete=complete,
            finding_home=homing)

    derotating = 'False'
    if port in ('1', '2') and state.derotate.get(port) is not None and r_slewing == 'True':
        derotating = 'True'
    if port in ('1', '2') and state.resume_derotate.get(port):
        # a rotator move interrupted derotation; it is restarted (from the new
        # angle) by the next rotatorStartDerotating, as PWI2 kept derotating
        derotating = 'True'
    current_rot = rotators.get(port)
    rotator = _section(
        connected=_bool(raw, 'rotator.is_connected'),
        position=current_rot.position if current_rot else _num(_float(raw, 'rotator.mech_position_degs')),
        unit='Degree', moving=r_moving,
        goto_complete=current_rot.goto_complete if current_rot else UNKNOWN,
        altaz_derotate=derotating)

    m3 = _section(connected='True' if raw.get('m3.exists', '0').strip() not in ('0', 'false', '') else 'False',
                  port=port, moving_rotate='False' if port in ('1', '2') else 'True',
                  unit='Degree')

    temperature = _section()
    for name in ('primary', 'secondary', 'm3', 'ambient', 'backplate'):
        value = good_temperature(temps.get(name))
        setattr(temperature, name, UNKNOWN if value is None else repr(value))

    root = _section(status=status, mount=mount, focuser=focuser, focuser1=focusers['1'],
                    focuser2=focusers['2'], rotator=rotator, rotator1=rotators['1'],
                    rotator2=rotators['2'], m3=m3, temperature=temperature,
                    fans=_section(on=UNKNOWN))
    root.raw = raw
    return root


def mount_motion_stopped(raw, velocity_tolerance=1e-4):
    """True when PWI4 reports no slew and both axes' setpoint velocities ~0."""
    if _bool(raw, 'mount.is_slewing') != 'False':
        return False
    for axis in ('0', '1'):
        v = _float(raw, 'mount.axis%s.setpoint_velocity_degs_per_sec' % axis)
        if v is not None and abs(v) > velocity_tolerance:
            return False
    return True


def to_hours(value):
    """Decimal hours from a number or a 'HH MM SS' / 'HH:MM:SS' string."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return _sexagesimal_to_float(value)


def to_degrees(value):
    """Decimal degrees from a number or a '+DD MM SS' / 'DD:MM:SS' string."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return _sexagesimal_to_float(value)


def _sexagesimal_to_float(text):
    parts = re.split(r'[ :]+', str(text).strip())
    if len(parts) != 3:
        raise ValueError('cannot parse %r as a number or sexagesimal' % (text,))
    sign = -1.0 if parts[0].startswith('-') else 1.0
    return sign * (abs(float(parts[0])) + float(parts[1]) / 60.0 + float(parts[2]) / 3600.0)
