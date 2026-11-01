"""PWI4 implementation of the cdk700.CDK700 public methods.

CDK700 inherits from PWI4Mixin.  Each public CDK700 method that talks to
PWI starts with

    if self.pwi_version == 4: return self._pwi4_<name>(...)

so PWI2 telescopes (PWI_VERSION absent or 2 in telescope_N.ini) run the
original code unchanged.  See docs/pwi4.md for the design, the status-field
mapping and the on-site cutover checklist.

Rules followed throughout this file (the legacy PWI2 path is not changed):
  * every HTTP request has a timeout (pwi4.PWI4Client);
  * getStatus() raises pwi4.PWI4Error when PWI4 cannot be read -- it never
    returns a canned "idle" status; methods that answer a yes/no question
    (initialize, isInitialized, inPosition, home, m3port_switch, the
    *AndWait methods) catch it, log it, and return False;
  * every wait loop has a real timeout;
  * focuser/rotator locks are released in try/finally;
  * the Windows password is never logged.
"""
import math
import os
import subprocess
import time

import mail
import pwi4
from pwi4 import PWI4Error


def _setup_value(setup, key, default):
    try:
        value = setup[key]
    except KeyError:
        return default
    if isinstance(value, basestring):
        value = value.split('#', 1)[0].strip()
        if value == '':
            return default
    return value


class PWI4Mixin:

    # ------------------------------------------------------------------
    # configuration
    # ------------------------------------------------------------------
    def _pwi4_load_config(self, config):
        """Read the PWI selection and PWI4 settings (called from load_config).

        [Setup]
          PWI_VERSION        2 (default) or 4
          PWI4_PORT          PWI4 HTTP port on HOST (default 8220)
          PWI4_TIMEOUT       seconds per HTTP request (default 10)
          PWI4_EXE           Windows process name to kill (default PWI4.exe)
          PWI4_START_TASK    Windows scheduled task that starts PWI4
                             (default "Start PWI4")
          PWI4_START_TIMEOUT seconds to wait for PWI4 to answer after start (90)
          PWI4_REMOTE_TIMEOUT seconds allowed for one ssh/winexe command (60)
          PWI4_M3_TIMEOUT    seconds for an M3 port change (default 30)
          PWI4_M3_SETTLE     seconds to wait after the M3 arrives so the PWI4
                             GUI re-selects that port's focuser/rotator (2)
          PWI4_POLL          status polling interval in seconds (0.5)
          PWI4_ROTATOR_STATUS_PORT  M3 port of PWI4's Rotator1 (default 1)
        [PWI4_MODEL]          PWI4 pointing-model file per M3 port (optional)
        [PWI4_ROTATOR_FIELD_OFFSET]  PWI4 rotator "position angle offset"
                             per port (optional, default 0)
        """
        setup = config['Setup']
        self.pwi_version = int(_setup_value(setup, 'PWI_VERSION', 2))
        if self.pwi_version not in (2, 4):
            raise ValueError('PWI_VERSION must be 2 or 4, not %r' % self.pwi_version)
        self.pwi4_port = int(_setup_value(setup, 'PWI4_PORT', pwi4.DEFAULT_PORT))
        self.pwi4_timeout = float(_setup_value(setup, 'PWI4_TIMEOUT', pwi4.DEFAULT_TIMEOUT))
        self.pwi4_exe = str(_setup_value(setup, 'PWI4_EXE', 'PWI4.exe'))
        self.pwi4_start_task = str(_setup_value(setup, 'PWI4_START_TASK', 'Start PWI4'))
        self.pwi4_start_timeout = float(_setup_value(setup, 'PWI4_START_TIMEOUT', 90.0))
        self.pwi4_remote_timeout = float(_setup_value(setup, 'PWI4_REMOTE_TIMEOUT', 60.0))
        self.pwi4_m3_timeout = float(_setup_value(setup, 'PWI4_M3_TIMEOUT', 30.0))
        self.pwi4_m3_settle = float(_setup_value(setup, 'PWI4_M3_SETTLE', 2.0))
        self.pwi4_poll = float(_setup_value(setup, 'PWI4_POLL', 0.5))
        status_port = str(_setup_value(setup, 'PWI4_ROTATOR_STATUS_PORT', '1'))
        models = {}
        for port, name in config.get('PWI4_MODEL', {}).items():
            models[str(port)] = str(name).strip()
        self.pwi4_model = models
        offsets = {'1': 0.0, '2': 0.0}
        for port, value in config.get('PWI4_ROTATOR_FIELD_OFFSET', {}).items():
            offsets[str(port)] = float(value)
        self.pwi4_state = pwi4.DriverState(rotator_status_port=status_port,
                                           rotator_field_offset=offsets)
        self._pwi4_temps = ({}, 0.0)
        self._pwi4_warned = set()
        if self.pwi_version == 4:
            self.pwi4 = pwi4.PWI4Client(self.HOST, self.pwi4_port, self.pwi4_timeout)
        else:
            self.pwi4 = None

    # ------------------------------------------------------------------
    # low-level helpers
    # ------------------------------------------------------------------
    def _pwi4_warn_once(self, key, message):
        if key not in self._pwi4_warned:
            self._pwi4_warned.add(key)
            self.logger.warning(message)

    def _pwi4_raw(self):
        """GET /status as a dict (raises PWI4Error) and update cached values."""
        raw = self.pwi4.status()
        state = self.pwi4_state
        port = pwi4.m3_port(raw)
        if port in ('1', '2'):
            pos = pwi4._float(raw, 'focuser.position')
            if pos is not None:
                state.last_focus[port] = pos
            mech = pwi4.rotator_mech_position(raw, port, state)
            if mech is not None:
                state.last_rotator[port] = mech
        mech0 = pwi4._float(raw, 'rotator.mech_position_degs')
        if mech0 is not None:
            state.last_rotator[state.rotator_status_port] = mech0
            # sanity check of the field-angle inversion used for the other port
            if (port == state.rotator_status_port and state.derotate.get(port) is None and
                    pwi4._bool(raw, 'rotator.is_moving') == 'False'):
                target = pwi4._float(raw, 'mount.field_angle_at_target_degs')
                field = pwi4._float(raw, 'rotator.field_angle_degs')
                if target is not None and field is not None:
                    off = state.rotator_field_offset.get(port, 0.0)
                    derived = (target + off - field) % 360.0
                    if abs(pwi4.wrap180(derived - mech0)) > 1.0:
                        self._pwi4_warn_once(
                            'rotfield',
                            'PWI4 rotator field angle does not invert to the reported mech '
                            'position (derived %.2f, reported %.2f) -- check the PWI4 rotator '
                            'settings (reverse direction / altitude compensation / PA offset); '
                            'positions of the other port\'s rotator will be wrong' % (derived, mech0))
        return raw

    def _pwi4_cmd(self, path, **params):
        """Send a PWI4 command; return the PWI2-shaped status, or False on failure."""
        try:
            raw = self.pwi4.request_status(path, **params)
        except PWI4Error as e:
            self.logger.error('PWI4 command %s %s failed: %s' % (path, params, e))
            return False
        return pwi4.legacy_status(raw, {}, self.pwi4_state)

    def _pwi4_wait(self, predicate, timeout, what):
        """Poll /status until predicate(raw) is true; return raw, or None on timeout."""
        t0 = time.time()
        while True:
            raw = self._pwi4_raw()
            if predicate(raw):
                return raw
            elapsed = time.time() - t0
            if elapsed > timeout:
                self.logger.error('Timed out after %.1f s waiting for %s' % (elapsed, what))
                return None
            time.sleep(self.pwi4_poll)

    def _pwi4_true(self, raw, key):
        return pwi4._bool(raw, key) == 'True'

    def _pwi4_valid_port(self, m3port):
        port = str(m3port)
        if port not in ('1', '2'):
            self.logger.error('Bad M3 port specified (%s)' % (m3port,))
            return None
        return port

    def _pwi4_ensure_port(self, m3port):
        """PWI4 only commands the GUI-selected (= M3 port) focuser/rotator.

        Returns True when the M3 is (now) on m3port.
        """
        port = self._pwi4_valid_port(m3port)
        if port is None:
            return False
        try:
            raw = self._pwi4_raw()
        except PWI4Error as e:
            self.logger.error('PWI4 status unavailable: %s' % e)
            return False
        if pwi4.m3_port(raw) == port:
            return True
        self.logger.info('M3 is on port %s; switching to port %s because PWI4 only commands the '
                         'focuser/rotator of the current M3 port' % (pwi4.m3_port(raw), port))
        return self.m3port_switch(port)

    def _pwi4_clear_derotation(self, port):
        self.pwi4_state.derotate[port] = None
        self.pwi4_state.resume_derotate[port] = False

    def _pwi4_port_lock(self, kind):
        # PWI4 addresses one focuser and one rotator at a time (the M3 port's),
        # so one lock per kind; this matches the legacy effective behavior,
        # where both ports end up sharing the port-2 lock.
        if kind == 'focuser':
            return self.focuser2_lock
        return self.rotator2_lock

    def _pwi4_model_name(self, filename):
        """Map a PWI2 model name (self.model[port]) to the PWI4 one for that port."""
        for port, name in self.model.items():
            if str(name) == str(filename):
                return self.pwi4_model.get(str(port), ''), str(port)
        return str(filename), None

    # ------------------------------------------------------------------
    # status
    # ------------------------------------------------------------------
    def _pwi4_getStatus(self):
        try:
            raw = self._pwi4_raw()
        except PWI4Error as e:
            self.logger.error('PWI4 status unavailable: %s' % e)
            raise
        temps, when = self._pwi4_temps
        if time.time() - when > 30.0:
            try:
                temps = self.pwi4.temperatures()
            except PWI4Error as e:
                self.logger.debug('PWI4 temperatures unavailable: %s' % e)
                temps = {}
            self._pwi4_temps = (temps, time.time())
        status = pwi4.legacy_status(raw, temps, self.pwi4_state)
        self.logger.debug('Alt/Az RMS error: ' + status.mount.alt_rms_error_arcsec + ',' + status.mount.azm_rms_error_arcsec)
        self.logger.debug('Alt/Az: ' + status.mount.alt_radian + ',' + status.mount.azm_radian)
        return status

    def _pwi4_status(self):
        return self._pwi4_raw()

    def _pwi4_guessFocus(self, m3port):
        try:
            status = self.getStatus()
        except PWI4Error:
            status = None
        m1temp = ambtemp = gravity = None
        if status is not None:
            m1temp = pwi4.good_temperature(status.temperature.primary)
            ambtemp = pwi4.good_temperature(status.temperature.ambient)
            try:
                gravity = math.sin(float(status.mount.alt_radian))
            except ValueError:
                gravity = None
        if m1temp is None:
            m1temp = float(self.T0[m3port])
        if ambtemp is None:
            ambtemp = m1temp - float(self.dT0[m3port])
        if gravity is None:
            gravity = float(self.G0[m3port])
        dt = m1temp - ambtemp
        self.focus[m3port] = float(self.F0[m3port]) + \
            float(self.C0[m3port]) * (m1temp - float(self.T0[m3port])) + \
            float(self.C1[m3port]) * (dt - float(self.dT0[m3port])) + \
            float(self.C2[m3port]) * (gravity - float(self.G0[m3port]))
        self.logger.info('Setting nominal focus for port ' + m3port + ' at ' + str(self.focus[m3port]) +
                         ' when T=' + str(m1temp) + ', dT=' + str(dt) + ', gravity=' + str(gravity))

    def _pwi4_isInitialized(self, tracking=True, derotate=True):
        try:
            s = self.getStatus()
        except PWI4Error:
            return False
        checks = [
            (s.mount.connected == 'True', 'mount not connected (' + s.mount.connected + ')'),
            (s.mount.alt_enabled == 'True', 'altitude motor not enabled (' + s.mount.alt_enabled + ')'),
            (s.mount.azm_enabled == 'True', 'azimuth motor not enabled (' + s.mount.azm_enabled + ')'),
            (s.focuser.connected == 'True', 'focuser not connected (' + s.focuser.connected + ')'),
            (s.rotator.connected == 'True', 'rotator not connected (' + s.rotator.connected + ')'),
        ]
        if tracking:
            checks.append((s.mount.tracking == 'True', 'mount not tracking (' + s.mount.tracking + ')'))
        else:
            checks.append((s.mount.tracking == 'False', 'mount tracking (' + s.mount.tracking + ')'))
        if derotate:
            checks.append((s.rotator.altaz_derotate == 'True', 'rotator not tracking (' + s.rotator.altaz_derotate + ')'))
        else:
            checks.append((s.rotator.altaz_derotate == 'False', 'rotator tracking (' + s.rotator.altaz_derotate + ')'))
        for ok, why in checks:
            if not ok:
                self.logger.info(why + ', telescope not initialized')
                return False
        return True

    def _pwi4_initialize(self, tracking=True, derotate=True, extra_sleep=0.0, load_pointing_model=False):
        try:
            raw = self._pwi4_raw()
            if not self._pwi4_true(raw, 'mount.is_connected'):
                self.logger.info('Connecting to mount')
                if not self.mountConnect(extra_sleep=extra_sleep):
                    return False
                raw = self._pwi4_raw()
            if not (self._pwi4_true(raw, 'mount.axis0.is_enabled') and self._pwi4_true(raw, 'mount.axis1.is_enabled')):
                self.logger.info('Enabling motors')
                if not self.mountEnableMotors(extra_sleep=extra_sleep):
                    return False
                raw = self._pwi4_raw()
            for dev in ('focuser', 'rotator'):
                if pwi4._bool(raw, dev + '.exists') == 'False':
                    self.logger.error('PWI4 reports no %s configured' % dev)
                    return False
                if not self._pwi4_true(raw, dev + '.is_connected'):
                    self.logger.info('Connecting to %s' % dev)
                    self._pwi4_cmd('/%s/connect' % dev)
                    raw = self._pwi4_wait(lambda r, d=dev: self._pwi4_true(r, d + '.is_connected'),
                                          10.0 + extra_sleep, dev + ' connection')
                    if raw is None:
                        self.logger.error('PWI4 %s not connected. /%s/connect only reaches device #1; '
                                          'the port-2 device must be auto-connected by PWI4 (see docs/pwi4.md)'
                                          % (dev, dev))
                        return False
                if not self._pwi4_true(raw, dev + '.is_enabled'):
                    self.logger.info('Enabling %s' % dev)
                    self._pwi4_cmd('/%s/enable' % dev)
                    raw = self._pwi4_raw()

            m3port = pwi4.m3_port(raw)
            if load_pointing_model:
                self.logger.info('re-loading pointing model for the current port')
                self.m3port_switch(m3port, force=True)
            s = self.getStatus()

            if tracking:
                if s.mount.tracking != 'True':
                    self.logger.info('Turning mount tracking on')
                    self.mountTrackingOn()
                    time.sleep(1.0 + extra_sleep)
            else:
                if s.mount.tracking != 'False':
                    self.logger.info('Turning mount tracking off')
                    self.mountTrackingOff()
                    time.sleep(1.0 + extra_sleep)

            if derotate:
                if s.rotator.altaz_derotate != 'True':
                    self.logger.info('Turning rotator tracking on')
                    self.rotatorStartDerotating(m3port)
                    time.sleep(1.0 + extra_sleep)
            else:
                if s.rotator.altaz_derotate != 'False':
                    self.logger.info('Turning rotator tracking off')
                    self.rotatorStopDerotating(m3port)
                    time.sleep(1.0 + extra_sleep)
        except PWI4Error as e:
            self.logger.error('PWI4 failure during initialize: %s' % e)
            return False
        return self.isInitialized(tracking=tracking, derotate=derotate)

    # ------------------------------------------------------------------
    # mount
    # ------------------------------------------------------------------
    def _pwi4_mountConnect(self, extra_sleep=0.0):
        if self._pwi4_cmd('/mount/connect') is False:
            return False
        try:
            raw = self._pwi4_wait(lambda r: self._pwi4_true(r, 'mount.is_connected'),
                                  10.0 + extra_sleep, 'mount connection')
        except PWI4Error as e:
            self.logger.error('PWI4 failure while connecting: %s' % e)
            return False
        if raw is None:
            self.logger.error('Failed to connect to mount')
            return False
        return True

    def _pwi4_mountDisconnect(self):
        return self._pwi4_cmd('/mount/disconnect')

    def _pwi4_mountEnableMotors(self, extra_sleep=0.0):
        # PWI4 4.1.4 rejects axis=-1, so enable each axis
        for axis in (0, 1):
            if self._pwi4_cmd('/mount/enable', axis=axis) is False:
                return False
        try:
            raw = self._pwi4_wait(lambda r: self._pwi4_true(r, 'mount.axis0.is_enabled') and
                                  self._pwi4_true(r, 'mount.axis1.is_enabled'),
                                  10.0 + extra_sleep, 'mount axes to enable')
        except PWI4Error as e:
            self.logger.error('PWI4 failure while enabling motors: %s' % e)
            return False
        if raw is None:
            self.logger.error('Failed to enable motors')
            return False
        return True

    def _pwi4_mountDisableMotors(self):
        status = False
        for axis in (0, 1):
            status = self._pwi4_cmd('/mount/disable', axis=axis)
        return status

    def _pwi4_mountHome(self):
        return self._pwi4_cmd('/mount/find_home')

    def _pwi4_mountOffsetRaDec(self, deltaRaArcseconds, deltaDecArcseconds):
        # ra_add_arcsec is arcsec of RA coordinate (no cos(dec)), like PWI2 incrementra
        return self._pwi4_cmd('/mount/offset', ra_add_arcsec=float(deltaRaArcseconds),
                              dec_add_arcsec=float(deltaDecArcseconds))

    def _pwi4_mountOffsetAltAz(self, deltaAltArcseconds, deltaAzArcseconds):
        # axis0 = azimuth, axis1 = altitude on an alt-az mount
        return self._pwi4_cmd('/mount/offset', axis0_add_arcsec=float(deltaAzArcseconds),
                              axis1_add_arcsec=float(deltaAltArcseconds))

    def _pwi4_mountOffsetAltAzFixed(self, deltaAltArcseconds, deltaAzArcseconds):
        # PWI2 jogged each axis for 2 s and then stopped the mount; PWI4 can
        # apply the same net axis offsets directly (no jog, no mount stop).
        return self._pwi4_mountOffsetAltAz(deltaAltArcseconds, deltaAzArcseconds)

    def _pwi4_mountGotoRaDecApparent(self, raAppHours, decAppDegs):
        return self._pwi4_cmd('/mount/goto_ra_dec_apparent', ra_hours=pwi4.to_hours(raAppHours),
                              dec_degs=pwi4.to_degrees(decAppDegs))

    def _pwi4_mountGotoRaDecJ2000(self, ra2000Hours, dec2000Degs, timeout=30.0):
        return self._pwi4_cmd('/mount/goto_ra_dec_j2000', ra_hours=pwi4.to_hours(ra2000Hours),
                              dec_degs=pwi4.to_degrees(dec2000Degs))

    def _pwi4_mountGotoAltAz(self, altDegs, azmDegs):
        return self._pwi4_cmd('/mount/goto_alt_az', alt_degs=pwi4.to_degrees(altDegs),
                              az_degs=pwi4.to_degrees(azmDegs))

    def _pwi4_mountStop(self):
        return self._pwi4_cmd('/mount/stop')

    def _pwi4_mountTrackingOn(self):
        return self._pwi4_cmd('/mount/tracking_on')

    def _pwi4_mountTrackingOff(self):
        return self._pwi4_cmd('/mount/tracking_off')

    def _pwi4_mountSetTrackingRateOffsets(self, raArcsecPerSec, decArcsecPerSec):
        return self._pwi4_cmd('/mount/offset', ra_set_rate_arcsec_per_sec=float(raArcsecPerSec),
                              dec_set_rate_arcsec_per_sec=float(decArcsecPerSec))

    def _pwi4_mountSetPointingModel(self, filename):
        name, port = self._pwi4_model_name(filename)
        return self._pwi4_load_model_file(name, port)

    def _pwi4_load_model_file(self, name, port=None):
        if not name:
            self.logger.warning('No PWI4 pointing model configured for M3 port %s ([PWI4_MODEL] in %s). '
                                'PWI2 .PXP models cannot be loaded by PWI4; keeping the model PWI4 has '
                                'loaded. Build a PWI4 model on-sky for this port.' % (port, self.config_file))
            return False
        if name.lower().endswith('.pxp') or not pwi4.MODEL_FILENAME_RE.match(name):
            self.logger.error('Refusing to ask PWI4 to load %r: PWI4 models only (letters, numbers, '
                              '"." and "_"; not a PWI2 .PXP file)' % name)
            return False
        return self._pwi4_cmd('/mount/model/load', filename=name)

    def _pwi4_mountAddToModel(self, ra, dec):
        return self._pwi4_cmd('/mount/model/add_point', ra_j2000_hours=pwi4.to_hours(ra),
                              dec_j2000_degs=pwi4.to_degrees(dec))

    def _pwi4_mountSaveModel(self, filename):
        name, port = self._pwi4_model_name(filename)
        if not name or not pwi4.MODEL_FILENAME_RE.match(name) or name.lower().endswith('.pxp'):
            self.logger.error('Cannot save PWI4 model for port %s: set a PWI4 model name in '
                              '[PWI4_MODEL] (got %r)' % (port, name))
            return False
        return self._pwi4_cmd('/mount/model/save', filename=name)

    def _pwi4_mountSync(self, ra, dec):
        self.logger.error('mountSync is not supported by PWI4 (no sync command); use mountAddToModel')
        return False

    # ------------------------------------------------------------------
    # M3
    # ------------------------------------------------------------------
    def _pwi4_m3SelectPort(self, m3port):
        port = self._pwi4_valid_port(m3port)
        if port is None:
            return False
        return self._pwi4_cmd('/m3/goto', port=port)

    def _pwi4_m3Stop(self):
        return self._pwi4_cmd('/m3/stop')

    def _pwi4_m3port_switch(self, m3port, force=False):
        """Put the M3 on m3port; returns True on success, False otherwise (bounded)."""
        port = self._pwi4_valid_port(m3port)
        if port is None:
            return False
        try:
            raw = self._pwi4_raw()
            tracking = self._pwi4_true(raw, 'mount.is_tracking')
            current = pwi4.m3_port(raw)
            self.logger.info('Ensuring m3 port is at port %s.' % port)
            if current == port and not force:
                return True
            if force:
                self.logger.info('Re-loading pointing model just to be sure')
            else:
                self.logger.info('Port changed, loading pointing model')
            self._pwi4_load_model_file(self.pwi4_model.get(port, ''), port)
            time.sleep(0.5)
            if tracking:
                self.mountTrackingOn()
            if current != port:
                # derotation of the old port can no longer be stopped once the
                # GUI selects the new port's rotator, so stop it now
                if current in ('1', '2') and (self.pwi4_state.derotate.get(current) is not None or
                                              self.pwi4_state.resume_derotate.get(current)):
                    self.rotatorStopDerotating(current)
                if self.m3SelectPort(port) is False:
                    return False
                raw = self._pwi4_wait(lambda r: pwi4.m3_port(r) == port, self.pwi4_m3_timeout,
                                      'M3 to reach port ' + port)
                if raw is None:
                    self.logger.error('M3 did not reach port %s within %.0f s; stopping M3'
                                      % (port, self.pwi4_m3_timeout))
                    self.m3Stop()
                    return False
                # PWI4's GUI timer moves the focuser/rotator selection to the new port
                time.sleep(self.pwi4_m3_settle)
            return True
        except PWI4Error as e:
            self.logger.error('PWI4 failure during M3 port switch: %s' % e)
            return False

    # ------------------------------------------------------------------
    # focuser
    # ------------------------------------------------------------------
    def _pwi4_focuserConnect(self, m3port):
        if str(m3port) != '1':
            self._pwi4_warn_once('focconn', 'PWI4 /focuser/connect only connects Focuser1; the '
                                 'focuser on port %s must be connected by PWI4 itself' % m3port)
        return self._pwi4_cmd('/focuser/connect')

    def _pwi4_focuserDisconnect(self, m3port):
        if str(m3port) != '1':
            self.logger.warning('Not disconnecting: PWI4 /focuser/disconnect acts on Focuser1, not port %s' % m3port)
            return False
        return self._pwi4_cmd('/focuser/disconnect')

    def _pwi4_focuserMove(self, position, m3port):
        if position < float(self.minfocus[m3port]) or position > float(self.maxfocus[m3port]):
            self.logger.warning('Requested focus on port ' + str(m3port) + ' (' + str(position) + ') out of bounds')
            return False
        if not self._pwi4_ensure_port(m3port):
            return False
        return self._pwi4_cmd('/focuser/goto', target=float(position))

    def _pwi4_focuserMoveAndWait(self, position, m3port, timeout=300.0):
        lock = self._pwi4_port_lock('focuser')
        lock.acquire()
        try:
            if not self.focuserMove(position, m3port):
                self.logger.warning('Focuser on port ' + str(m3port) + ' could not move to requested position (' + str(position) + ')')
                return False
            time.sleep(1.0)
            target = float(position)
            t0 = time.time()

            def arrived(r):
                pos = pwi4._float(r, 'focuser.position')
                return (pwi4._bool(r, 'focuser.is_moving') == 'False' and pos is not None and
                        abs(pos - target) <= 10.0)
            raw = self._pwi4_wait(arrived, timeout, 'focuser on port %s to reach %s' % (m3port, position))
            elapsed = time.time() - t0
            if raw is None:
                self.logger.warning('Focuser on port ' + str(m3port) + ' not at requested position (' +
                                    str(position) + ') after ' + str(elapsed) + ' seconds')
                return False
            self.logger.info('Focuser completed move in ' + str(elapsed) + ' seconds')
            return True
        except PWI4Error as e:
            self.logger.error('PWI4 failure during focuser move: %s' % e)
            return False
        finally:
            lock.release()

    def _pwi4_focuserIncrement(self, offset, m3port):
        if not self._pwi4_ensure_port(m3port):
            return False
        try:
            pos = pwi4._float(self._pwi4_raw(), 'focuser.position')
        except PWI4Error as e:
            self.logger.error('PWI4 status unavailable: %s' % e)
            return False
        if pos is None:
            return False
        return self.focuserMove(pos + float(offset), m3port)

    def _pwi4_focuserStop(self, m3port):
        try:
            on_port = pwi4.m3_port(self._pwi4_raw()) == str(m3port)
        except PWI4Error as e:
            self.logger.error('PWI4 status unavailable: %s' % e)
            return False
        if not on_port:
            self.logger.warning('Not stopping focuser %s: PWI4 only stops the current M3 port\'s focuser' % m3port)
            return False
        return self._pwi4_cmd('/focuser/stop')

    def _pwi4_startAutoFocus(self):
        return self._pwi4_cmd('/autofocus/start')

    def _pwi4_focuserHome(self, m3port):
        port = self._pwi4_valid_port(m3port)
        if port is None:
            return False
        return self._pwi4_cmd('/focuser/find_home', index=int(port) - 1)

    def _pwi4_focuserHomeAndWait(self, m3port, timeout=300.0):
        return self._pwi4_home_device('focuser', m3port, timeout)

    def _pwi4_home_device(self, kind, m3port, timeout):
        port = self._pwi4_valid_port(m3port)
        if port is None:
            return False
        lock = self._pwi4_port_lock(kind)
        flags = self.pwi4_state.focuser_homing if kind == 'focuser' else self.pwi4_state.rotator_homing
        lock.acquire()
        try:
            # the motion is only visible in /status for the current M3 port
            if not self._pwi4_ensure_port(port):
                return False
            flags[port] = True
            if kind == 'rotator':
                self._pwi4_clear_derotation(port)
            if self._pwi4_cmd('/%s/find_home' % kind, index=int(port) - 1) is False:
                return False
            time.sleep(5.0)
            t0 = time.time()
            quiet = [0]

            def stopped(r):
                quiet[0] = quiet[0] + 1 if pwi4._bool(r, kind + '.is_moving') == 'False' else 0
                return quiet[0] >= 3
            raw = self._pwi4_wait(stopped, timeout, 'homing %s %s' % (kind, port))
            if raw is None:
                self.logger.error('Homing ' + kind + ' ' + port + ' failed')
                return False
            self.logger.info('Homing %s %s complete (elapsed time = %.1f)' % (kind, port, time.time() - t0))
            return True
        except PWI4Error as e:
            self.logger.error('PWI4 failure while homing %s %s: %s' % (kind, port, e))
            return False
        finally:
            flags[port] = False
            lock.release()

    # ------------------------------------------------------------------
    # rotator
    # ------------------------------------------------------------------
    def _pwi4_rotatorMove(self, position, m3port, wait=False, timeout=400.0):
        lock = self._pwi4_port_lock('rotator')
        lock.acquire()
        try:
            if not self._pwi4_ensure_port(m3port):
                return False
            port = str(m3port)
            # PWI2 kept derotating across a mechanical move; PWI4's goto_mech
            # ends field tracking, so remember to resume it from the new angle
            resume = (self.pwi4_state.derotate.get(port) is not None or
                      self.pwi4_state.resume_derotate.get(port, False))
            self._pwi4_clear_derotation(port)
            status = self._pwi4_cmd('/rotator/goto_mech', degs=float(position))
            if status is False:
                return False
            self.pwi4_state.last_rotator[port] = float(position) % 360.0
            self.pwi4_state.resume_derotate[port] = resume
            if not wait:
                return status
            time.sleep(1.0)
            t0 = time.time()
            raw = self._pwi4_wait(lambda r: pwi4._bool(r, 'rotator.is_slewing') == 'False' and
                                  pwi4._bool(r, 'rotator.is_moving') == 'False',
                                  timeout, 'rotator %s to reach %s' % (port, position))
            if raw is None:
                self.logger.error('Moving rotator ' + port + ' failed')
                return False
            self.logger.info('Rotator on port %s move complete (%.1f s)' % (port, time.time() - t0))
            if resume:
                return self.rotatorStartDerotating(port) is not False
            return True
        except PWI4Error as e:
            self.logger.error('PWI4 failure during rotator move: %s' % e)
            return False
        finally:
            lock.release()

    def _pwi4_rotatorIncrement(self, offset, m3port):
        if not self._pwi4_ensure_port(m3port):
            return False
        return self._pwi4_cmd('/rotator/offset', degs=float(offset))

    def _pwi4_rotatorStop(self, m3port):
        try:
            on_port = pwi4.m3_port(self._pwi4_raw()) == str(m3port)
        except PWI4Error as e:
            self.logger.error('PWI4 status unavailable: %s' % e)
            return False
        if not on_port:
            self.logger.warning('Not stopping rotator %s: PWI4 only stops the current M3 port\'s rotator' % m3port)
            return False
        self._pwi4_clear_derotation(str(m3port))
        return self._pwi4_cmd('/rotator/stop')

    def _pwi4_rotatorStartDerotating(self, m3port):
        """PWI2 derotatestart == PWI4 goto_field at the current field angle."""
        port = self._pwi4_valid_port(m3port)
        if port is None:
            return False
        if not self._pwi4_ensure_port(port):
            return False
        try:
            raw = self._pwi4_raw()
            if (self.pwi4_state.derotate.get(port) is not None and not self.pwi4_state.resume_derotate.get(port)
                    and self._pwi4_true(raw, 'rotator.is_slewing')):
                return pwi4.legacy_status(raw, {}, self.pwi4_state)
            if self._pwi4_true(raw, 'rotator.is_slewing'):
                # let a goto_mech in progress finish so we lock the intended angle
                raw = self._pwi4_wait(lambda r: pwi4._bool(r, 'rotator.is_slewing') == 'False', 60.0,
                                      'rotator %s goto to finish before derotating' % port)
                if raw is None:
                    return False
            field = pwi4._float(raw, 'rotator.field_angle_degs')
            if field is None:
                self.logger.error('PWI4 reports no rotator field angle; cannot start derotation')
                return False
        except PWI4Error as e:
            self.logger.error('PWI4 failure starting derotation: %s' % e)
            return False
        status = self._pwi4_cmd('/rotator/goto_field', degs=field)
        if status is not False:
            self.pwi4_state.derotate[port] = field
            self.pwi4_state.resume_derotate[port] = False
        return status

    def _pwi4_rotatorStopDerotating(self, m3port):
        port = str(m3port)
        try:
            on_port = pwi4.m3_port(self._pwi4_raw()) == port
        except PWI4Error as e:
            self.logger.error('PWI4 status unavailable: %s' % e)
            return False
        if port in self.pwi4_state.derotate:
            self._pwi4_clear_derotation(port)
        if not on_port:
            return True
        return self._pwi4_cmd('/rotator/stop')

    def _pwi4_rotatorHome(self, m3port):
        port = self._pwi4_valid_port(m3port)
        if port is None:
            return False
        self._pwi4_clear_derotation(port)
        return self._pwi4_cmd('/rotator/find_home', index=int(port) - 1)

    def _pwi4_rotatorHomeAndWait(self, m3port, timeout=400.0):
        return self._pwi4_home_device('rotator', m3port, timeout)

    # ------------------------------------------------------------------
    # higher level
    # ------------------------------------------------------------------
    def _pwi4_isMoving(self, timeout=15.0):
        try:
            raw = self._pwi4_wait(lambda r: pwi4._bool(r, 'mount.is_slewing') == 'False', timeout,
                                  'mount to stop slewing')
        except PWI4Error as e:
            self.logger.error('PWI4 status unavailable; assuming the mount may be moving: %s' % e)
            return True
        return raw is None

    def _pwi4_inPosition(self, m3port=None, alt=None, az=None, ra=None, dec=None,
                         pointingTolerance=60.0, tracking=True, derotate=True):
        try:
            return self._pwi4_inPosition_body(m3port, alt, az, ra, dec, pointingTolerance, tracking, derotate)
        except PWI4Error as e:
            self.logger.error('PWI4 failure while waiting for the telescope: %s' % e)
            return False
        except (KeyError, ValueError) as e:
            self.logger.error('PWI4 status lacks a usable position (%s: %s)' % (e.__class__.__name__, e))
            return False

    def _pwi4_inPosition_body(self, m3port, alt, az, ra, dec, pointingTolerance, tracking, derotate):
        start = time.time()
        time.sleep(0.5)
        raw = self._pwi4_raw()

        if str(m3port) in ('1', '2'):
            m3port = str(m3port)
            self.logger.info('Ensuring m3 port is at port ' + m3port)
            raw = self._pwi4_wait(lambda r: pwi4.m3_port(r) == m3port, self.pwi4_m3_timeout,
                                  'M3 port ' + m3port)
            if raw is None:
                self.logger.error('Failed to select correct M3 port (' + m3port + ')')
                return False
        else:
            m3port = pwi4.m3_port(raw)
            self.logger.info('No M3 port specified or bad, using current port (' + m3port + ')')

        def mount_ok(r):
            for key, name in (('mount.is_connected', 'mount connection'),
                              ('mount.axis0.is_enabled', 'azimuth drive'),
                              ('mount.axis1.is_enabled', 'altitude drive')):
                if not self._pwi4_true(r, key):
                    self.logger.error('Error with %s: PWI4 reports %s=%s' % (name, key, r.get(key)))
                    return False
            return True

        # wait for the slew: two not-slewing readings 1 s apart (wind shake can
        # end a slew early, see the PWI2 comment), with a real timeout
        slew_timeout = 60.0
        self.logger.info('Waiting for telescope to finish slew; slewing = ' + str(raw.get('mount.is_slewing')))
        while True:
            if not mount_ok(raw):
                return False
            if not self._pwi4_true(raw, 'mount.is_slewing'):
                time.sleep(1.0)
                raw = self._pwi4_raw()
                if not self._pwi4_true(raw, 'mount.is_slewing'):
                    break
                self.logger.error('Telescope moving after it said it was done')
            if time.time() - start > slew_timeout:
                self.logger.error('Failed to slew within timeout (' + str(slew_timeout) + ')')
                return False
            time.sleep(0.25)
            raw = self._pwi4_raw()
        if not mount_ok(raw):
            return False

        if tracking and not self._pwi4_true(raw, 'mount.is_tracking'):
            self.mountTrackingOn()
            self.logger.error('Tracking was off, turned tracking on')

        # focuser (only the current port's focuser is visible in PWI4)
        focus_timeout = 300.0
        raw = self._pwi4_wait(lambda r: pwi4._bool(r, 'focuser.is_moving') != 'True',
                              max(0.0, focus_timeout - (time.time() - start)), 'focuser to stop')
        if raw is None:
            self.logger.error('Failed to get to focus position within timeout (' + str(focus_timeout) + ')')
            return False

        if alt is not None and az is not None:
            actual_alt = math.radians(float(raw['mount.altitude_degs']))
            actual_az = math.radians(float(raw['mount.azimuth_degs']))
            cosd = (math.sin(actual_alt) * math.sin(math.radians(alt)) +
                    math.cos(actual_alt) * math.cos(math.radians(alt)) * math.cos(actual_az - math.radians(az)))
            delta = math.degrees(math.acos(max(-1.0, min(1.0, cosd)))) * 3600.0
            if delta > pointingTolerance:
                self.logger.error('Telescope reports it is ' + str(delta) + ' arcsec away from the requested postion (ActualAlt=' +
                                  str(math.degrees(actual_alt)) + ' degrees, Requested Alt=' + str(alt) + ', ActualAz=' +
                                  str(math.degrees(actual_az)) + ' degrees, Requested Az=' + str(az))
                self.nfailed += 1
                return False

        if ra is not None and dec is not None:
            actual_ra = float(raw['mount.ra_j2000_hours']) * math.pi / 12.0
            actual_dec = math.radians(float(raw['mount.dec_j2000_degs']))
            cosd = (math.sin(actual_dec) * math.sin(math.radians(dec)) +
                    math.cos(actual_dec) * math.cos(math.radians(dec)) * math.cos(actual_ra - ra * math.pi / 12.0))
            delta = math.degrees(math.acos(max(-1.0, min(1.0, cosd)))) * 3600.0
            if delta > pointingTolerance:
                self.logger.error('Telescope reports it is ' + str(delta) + ' arcsec away from the target postion (Dec=' +
                                  str(math.degrees(actual_dec)) + ' degrees, Requested Dec=' + str(dec) + ', RA=' +
                                  str(actual_ra * 12.0 / math.pi) + ' hours, Requested Ra=' + str(ra))
                self.nfailed += 1
                return False

        if derotate:
            if self.rotatorStartDerotating(m3port) is False:
                self.logger.error('Could not start derotation on port ' + m3port)
                return False
            rot_timeout = 360.0
            remaining = max(0.0, rot_timeout - (time.time() - start))
            raw = self._pwi4_wait(lambda r: getattr(pwi4.legacy_status(r, {}, self.pwi4_state),
                                                    'rotator' + m3port).goto_complete == 'True',
                                  remaining, 'rotator on port ' + m3port)
            if raw is None:
                self.logger.error('Failed to get to rotator position within timeout (' + str(rot_timeout) + ')')
                return False
        else:
            if self.pwi4_state.derotate.get(m3port) is not None or self.pwi4_state.resume_derotate.get(m3port):
                self.rotatorStopDerotating(m3port)
                self.logger.error('Derotating was on, turned off')

        self.nfailed = 0
        return True

    def _pwi4_home(self, timeout=600):
        self.logger.info('Homing Telescope')
        state = self.pwi4_state
        try:
            raw = self._pwi4_raw()
            if not self._pwi4_true(raw, 'mount.is_connected'):
                self.logger.warning('Home requested but not connected; reconnecting telescope')
                if not self.initialize(tracking=False, derotate=False):
                    self.logger.error('Cannot connect to mount')
                    return False
            elif not (self._pwi4_true(raw, 'mount.axis0.is_enabled') and self._pwi4_true(raw, 'mount.axis1.is_enabled')):
                if not self.mountEnableMotors():
                    return False
            state.homing = True
            if self.mountHome() is False:
                return False
            time.sleep(5.0)
            t0 = time.time()
            quiet = 0
            while True:
                raw = self._pwi4_raw()
                if not (self._pwi4_true(raw, 'mount.is_connected') and
                        self._pwi4_true(raw, 'mount.axis0.is_enabled') and
                        self._pwi4_true(raw, 'mount.axis1.is_enabled')):
                    self.logger.error('Motors no longer enabled while homing. Commutation problem?')
                    return False
                quiet = quiet + 1 if pwi4.mount_motion_stopped(raw) else 0
                if quiet >= 3:
                    break
                elapsed = time.time() - t0
                if elapsed > timeout:
                    self.logger.error('Error homing telescope: still moving after ' + str(elapsed) + ' s')
                    return False
                self.logger.info('Homing Telescope (elapsed time = ' + str(elapsed) + ')')
                time.sleep(2.0)
            if 'mount.axis0.is_homed' in raw and 'mount.axis1.is_homed' in raw:
                if not (self._pwi4_true(raw, 'mount.axis0.is_homed') and self._pwi4_true(raw, 'mount.axis1.is_homed')):
                    self.logger.error('Homing finished but PWI4 reports the axes are not homed')
                    return False
            state.homed = True
            self.logger.info('Done homing telescope (elapsed time = ' + str(time.time() - t0) + ')')
            return True
        except PWI4Error as e:
            self.logger.error('PWI4 failure while homing: %s' % e)
            return False
        finally:
            state.homing = False

    def _pwi4_shutdown(self, m3port=None):
        if m3port is not None:
            self.logger.info('Shutting down focusing rotator on port ' + str(m3port))
            self.focuserStop(m3port)
            self.rotatorStopDerotating(m3port)
        self.logger.info('Turning off tracking')
        self.mountTrackingOff()
        self.logger.info('Disabling motors')
        self.mountDisableMotors()
        self.logger.info('Disconnecting from the mount')
        self.mountDisconnect()

    def _pwi4_quietly(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.logger.warning('%s failed during recovery: %s' % (getattr(func, '__name__', func), e))
            return False

    def _pwi4_recover(self, tracking=True, derotate=True):
        """Same escalation ladder as the PWI2 recover(), with PWI4 process control."""
        self.nfailed += 1
        self.logger.warning('failed ' + str(self.nfailed) + ' times; trying to reconnect')

        def init():
            return self.initialize(tracking=tracking, derotate=derotate, extra_sleep=self.nfailed * 10)

        if self.nfailed <= 1:
            self._pwi4_quietly(self.shutdown)
            if init():
                self.logger.info('recovered after reconnecting')
                return True
            self.nfailed += 1

        for level, message in ((2, 'reconnecting failed; restarting PWI4'),
                               (3, 'restarting PWI4 failed; restarting PWI4 again')):
            if self.nfailed <= level:
                self.logger.warning(message)
                self._pwi4_quietly(self.shutdown)
                self.restartPWI()
                if init():
                    self.logger.info('recovered after restarting PWI4')
                    return True
                self.nfailed += 1

        if self.nfailed <= 5:
            try:
                homed = self.getStatus().mount.encoders_have_been_set == 'True'
            except PWI4Error:
                homed = False
            if not homed:
                self.logger.warning('restarting PWI4 failed, homing telescope')
                self.home()
                time.sleep(0.25)
                if init():
                    self.logger.info('recovered after homing')
                    return True
            else:
                self.logger.warning('Telescope already home')
            self.nfailed += 1

        if self.nfailed <= 6:
            self.logger.info('Homing failed, power cycling the mount')
            self._pwi4_quietly(self.shutdown)
            self.killPWI()
            self.powercycle()
            self.startPWI()
            time.sleep(10)
            if self.initialize(tracking=False, derotate=derotate, extra_sleep=self.nfailed * 10):
                self.logger.info('recovered after power cycling the mount')
                self.logger.info('homing telescope')
                self.home()
                if self.initialize(tracking=tracking, derotate=derotate):
                    return True
                self.logger.info('could not initialize telescope after power cycling and homing :(')
            self.nfailed += 1

        filename = "telescope." + self.id + '.error'
        body = "Dear benevolent humans,\n\n" + \
            "I have failed to recover automatially. Please recover me, then delete " + filename + " to restart operations.\n\n" + \
            "Love,\n" + \
            "MINERVA"
        while not self.initialize(tracking=tracking, derotate=derotate):
            self.logger.error('Telescope has failed to automatically recover; intervention required')
            mail.send(self.id + " has failed", body, level='serious', directory=self.directory)
            fh = open(filename, 'w')
            fh.close()
            while os.path.isfile(filename):
                time.sleep(1)
        return True

    # ------------------------------------------------------------------
    # PWI4 process control on the Windows telcom PC
    # ------------------------------------------------------------------
    def _pwi4_forget_state(self):
        for port in ('1', '2'):
            self._pwi4_clear_derotation(port)
        self.pwi4_state.homed = False

    def _pwi4_killPWI(self):
        self._pwi4_forget_state()
        return self.kill_remote_task(self.pwi4_exe)

    def _pwi4_startPWI(self, email=True, extra_sleep=0.0):
        self._pwi4_forget_state()
        self.send_to_computer('schtasks /Run /TN "%s"' % self.pwi4_start_task)
        t0 = time.time()
        timeout = self.pwi4_start_timeout + extra_sleep
        while True:
            try:
                raw = self._pwi4_raw()
                break
            except PWI4Error as e:
                if time.time() - t0 > timeout:
                    self.logger.error('PWI4 did not answer within %.0f s of starting it: %s' % (timeout, e))
                    return False
                time.sleep(2.0)
        self.logger.info('PWI4 %s is answering' % raw.get('pwi4.version'))
        port = pwi4.m3_port(raw)
        if port in ('1', '2'):
            self.logger.info('changing model file')
            self._pwi4_load_model_file(self.pwi4_model.get(port, ''), port)
        return True

    def _pwi4_restartPWI(self, email=True, extra_sleep=0.0):
        self.killPWI()
        time.sleep(5.0 + extra_sleep)
        return self.startPWI(email=email)

    def _pwi4_send_to_computer(self, cmd):
        """Run cmd on the telcom PC (ssh for WIN10 hosts, winexe otherwise).

        Same credentials file as the PWI2 path, but: argv instead of a shell
        string, a timeout, the real exit code, and the password never logged.
        """
        f = open(self.base_directory + '/credentials/authentication.txt', 'r')
        username = f.readline().strip()
        password = f.readline().strip()
        f.close()
        if self.win10:
            argv = ['sshpass', '-p', password, 'ssh', '-o', 'ConnectTimeout=20', username + '@' + self.HOST, cmd]
        else:
            argv = ['winexe', '-U', 'HOME/' + username + '%' + password, '//' + self.HOST, cmd]

        def redact(text):
            return text.replace(password, '****') if password else text
        shown = redact(' '.join(argv[:-1])) + " '" + cmd + "'"
        self.logger.info('remote: ' + shown)
        try:
            devnull = open(os.devnull, 'r')
            proc = subprocess.Popen(argv, stdin=devnull, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as e:
            self.logger.error('could not run %s: %s' % (shown, e))
            return False
        t0 = time.time()
        while proc.poll() is None:
            if time.time() - t0 > self.pwi4_remote_timeout:
                try:
                    proc.kill()
                except OSError:
                    pass
                self.logger.error('remote command timed out after %.0f s: %s' % (self.pwi4_remote_timeout, shown))
                return False
            time.sleep(0.2)
        out, err = proc.communicate()
        out = redact(out or '')
        err = redact(err or '')
        self.logger.info('cmd=' + cmd + ', rc=' + str(proc.returncode) + ', out=' + out.strip() + ', err=' + err.strip())
        if proc.returncode == 0:
            return True
        text = out + err
        if 'not found' in text and 'taskkill' in cmd:
            self.logger.info('task already dead')
            return True
        if 'NT_STATUS_HOST_UNREACHABLE' in text or 'No route to host' in text or 'timed out' in text:
            self.logger.error('the host is not reachable')
        elif 'NT_STATUS_LOGON_FAILURE' in text or 'Permission denied' in text:
            self.logger.error('invalid credentials in ' + self.base_directory + '/credentials/authentication.txt')
        return False

