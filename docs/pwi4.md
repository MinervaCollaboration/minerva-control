# PWI4 support for the CDK700 driver (`minerva_library/cdk700.py`)

PlaneWave's PWI2 (`PWI.exe`, XML over `http://HOST:NETWORKPORT/?device=...&cmd=...`)
and PWI4 (`PWI4.exe`, `key=value` text over `http://HOST:8220/<device>/<command>`)
can now be used side by side, chosen per telescope in `config/telescope_N.ini`.

* PWI2 telescopes (the default) run the original code in `cdk700.py`; the
  requests they send are byte-for-byte unchanged (checked by
  `tests/test_cdk700_pwi2_unchanged.py` against a record made from the
  unmodified code).
* PWI4 telescopes run `minerva_library/cdk700_pwi4.py` (the `PWI4Mixin` that
  `CDK700` now inherits from) on top of `minerva_library/pwi4.py` (HTTP client
  plus a translator from PWI4 `/status` to the PWI2-shaped status object that
  callers use, e.g. `getStatus().mount.ra_2000`, `.focuser1.position`,
  `.m3.port`, `.temperature.primary`).

Each public `CDK700` method that talks to PWI begins with
`if self.pwi_version == 4: return self._pwi4_<name>(...)`.

## Selecting PWI4 for one telescope

In `config/telescope_N.ini`, `[Setup]`:

```
	PWI_VERSION = 4          # absent or 2 = PWI2 (unchanged behaviour)
```

Rolling back is the same line set to `2` (or commented out) and a restart of
the control code.  `HOST` stays the telcom PC; PWI2's `NETWORKPORT` is ignored
in PWI4 mode.

Optional PWI4 keys (defaults shown; all ignored when `PWI_VERSION` is 2):

| key (in `[Setup]`) | default | meaning |
|---|---|---|
| `PWI4_PORT` | 8220 | PWI4 HTTP server port |
| `PWI4_TIMEOUT` | 10 | seconds per HTTP request |
| `PWI4_EXE` | `PWI4.exe` | process name for `taskkill /IM ... /f` |
| `PWI4_START_TASK` | `Start PWI4` | Windows scheduled task that starts PWI4 |
| `PWI4_START_TIMEOUT` | 90 | seconds for PWI4 to answer after the start task |
| `PWI4_REMOTE_TIMEOUT` | 60 | seconds allowed for one ssh/winexe command |
| `PWI4_M3_TIMEOUT` | 30 | seconds allowed for an M3 port change |
| `PWI4_M3_SETTLE` | 2 | seconds after the M3 arrives, for PWI4's GUI to re-select that port's focuser/rotator |
| `PWI4_POLL` | 0.5 | status polling interval (s) |
| `PWI4_ROTATOR_STATUS_PORT` | 1 | M3 port that PWI4's Rotator1 is on |

Sections:

```
[PWI4_MODEL]                  # PWI4 pointing model file per M3 port
	1 = ''                    # e.g. 'T1_port1.dat' -- letters, digits, '.', '_' only
	2 = ''
[PWI4_ROTATOR_FIELD_OFFSET]   # only if PWI4's rotator "position angle offset" is not 0
	1 = 0.0
	2 = 0.0
```

## How the PWI4 API was verified

Primary sources:

1. PlaneWave's reference client `pwi4_client.py` (distributed with PWI4; eight
   copies in public repositories were compared and agree on every endpoint used
   here).
2. The PWI4 4.1.4 Linux release (`PWI4.exe`, Feb 2024, mirrored by
   `rockit-astro/pwi4-packaging`): the route table and the CIL of the HTTP
   handlers in `PWI4.MainModule` were disassembled to confirm the endpoint names,
   parameter names, `/status` keys, units, and which focuser/rotator each command
   acts on.

### Endpoints used, with verification

| cdk700 method | PWI4 request | verified in |
|---|---|---|
| getStatus | `GET /status` | client + binary |
| getStatus (temperatures) | `GET /temperatures/pw1000` | binary only (not in client) |
| mountConnect / Disconnect | `/mount/connect`, `/mount/disconnect` | client + binary |
| mountEnableMotors / DisableMotors | `/mount/enable?axis=0`, `axis=1` (and `/mount/disable`) | client + binary (`axis=-1` is rejected by 4.1.4) |
| mountHome | `/mount/find_home` | client + binary |
| mountGotoRaDecJ2000 / Apparent | `/mount/goto_ra_dec_j2000` / `_apparent` `?ra_hours=&dec_degs=` (decimal only) | client + binary |
| mountGotoAltAz | `/mount/goto_alt_az?alt_degs=&az_degs=` | client + binary |
| mountStop | `/mount/stop` | client + binary |
| mountTrackingOn / Off | `/mount/tracking_on`, `/mount/tracking_off` | client + binary |
| mountOffsetRaDec | `/mount/offset?ra_add_arcsec=&dec_add_arcsec=` | client + binary |
| mountOffsetAltAz / AltAzFixed | `/mount/offset?axis0_add_arcsec=(az)&axis1_add_arcsec=(alt)` | client + binary |
| mountSetTrackingRateOffsets | `/mount/offset?ra_set_rate_arcsec_per_sec=&dec_set_rate_arcsec_per_sec=` | client + binary |
| mountSetPointingModel | `/mount/model/load?filename=` | client + binary |
| mountSaveModel | `/mount/model/save?filename=` | client + binary |
| mountAddToModel | `/mount/model/add_point?ra_j2000_hours=&dec_j2000_degs=` | client + binary |
| m3SelectPort / m3Stop | `/m3/goto?port=1\|2`, `/m3/stop` | client + binary |
| focuserConnect / Disconnect | `/focuser/connect`, `/focuser/disconnect` (Focuser1 only) | client + binary |
| focuser enable (initialize) | `/focuser/enable` | client + binary |
| focuserMove | `/focuser/goto?target=` | client + binary |
| focuserStop | `/focuser/stop` | client + binary |
| focuserHome | `/focuser/find_home?index=0\|1` | binary only (not in client) |
| rotatorMove | `/rotator/goto_mech?degs=` | client + binary |
| rotatorStartDerotating | `/rotator/goto_field?degs=<current field angle>` | client + binary |
| rotatorStop / StopDerotating | `/rotator/stop` | client + binary |
| rotatorIncrement | `/rotator/offset?degs=` | client + binary (semantics: see risks) |
| rotator connect / enable (initialize) | `/rotator/connect`, `/rotator/enable` (Rotator1 only) | client + binary |
| rotatorHome | `/rotator/find_home?index=0\|1` | binary only (not in client) |
| startAutoFocus | `/autofocus/start` | binary (route exists; parameters not checked) |

Not used: `/fans/on|off` (verified, but cdk700 never switched fans), `/mount/park`
(cdk700's `park()` slews to alt/az as before).

**Could not verify** (needs the real telescope):

* whether a later PWI4 release than 4.1.4 changes any of the above (the
  Windows installer on site will be newer);
* that PWI4 supports MINERVA's CDK700 hardware: Parker drives (ACR
  controller; PWI2 2.2.0.34 runs `ComACRServer.exe`), EFA focuser/rotator/fan
  controller, two focusers and two rotators (one per port), M3.  **PlaneWave must
  confirm this** before cutover.  The 4.1.4 binary does contain `ACR.CDK700v1/v2`
  mount drivers, an EFA controller service, `EfaIRF90Focuser`/`Focuser2`,
  `EfaIRF90Rotator`/`Rotator2` and "Ambient (EFA)" temperature code, so the
  support looks intended;
* the sign conventions of `/mount/offset` (positive `ra_add_arcsec` increases RA;
  positive `axis0`/`axis1` increase azimuth/altitude) relative to PWI2's
  `incrementra`/`incrementazm`/`incrementalt`;
* `/rotator/offset` semantics (cdk700 uses it only for the AO rotator trim);
* whether `/mount/find_home` reports `mount.is_slewing` while homing (cdk700
  instead waits for both axes' setpoint velocities to be zero for three
  consecutive polls);
* whether `/temperatures/pw1000` returns real values on this hardware (it returns
  -999 when there is no PW1000/ACR temperature controller);
* whether `/focuser/connect` brings up Focuser2 too, or only Focuser1.

## Status-field mapping (PWI4 → what callers read)

All values are strings, as PWI2's XML gave.  Anything PWI4 does not report is
the string `UNKNOWN` (callers' `try: float(...)` then falls back), never a
made-up number.

| caller field | PWI4 source | conversion / notes |
|---|---|---|
| `mount.connected` | `mount.is_connected` | `true`→`'True'` |
| `mount.azm_enabled` / `alt_enabled` | `mount.axis0.is_enabled` / `axis1.is_enabled` | axis0 = azimuth, axis1 = altitude |
| `mount.*_motor_error_code` / `_message` | (none) | `'0'`/`'No error'` if the axis is enabled, else `'-1'`/`'Axis not enabled'`; PWI4 reports no drive error codes |
| `mount.tracking` | `mount.is_tracking` | |
| `mount.moving` | `mount.is_slewing` | PWI2 also said "moving" when not tracking; PWI4 does not |
| `mount.on_target` | derived | connected and not slewing and tracking |
| `mount.ra`, `mount.dec` | `mount.ra_apparent_hours`, `dec_apparent_degs` | hours / degrees → `'HH MM SS.SSS'` / `'+DD MM SS.SS'` (parse with `utils.ten`) |
| `mount.ra_2000`, `mount.dec_2000` | `mount.ra_j2000_hours`, `dec_j2000_degs` | same formatting; RA stays in **hours** |
| `mount.ra_target`, `dec_target` | `mount.target_ra_apparent_hours`, `target_dec_apparent_degs` | same |
| `mount.ra_radian`, `dec_radian` | apparent RA/Dec | radians |
| `mount.alt_radian`, `azm_radian` | `mount.altitude_degs`, `azimuth_degs` | degrees → **radians** (focus model gravity term, FITS ALT/AZ) |
| `mount.alt_rms_error_arcsec` / `azm_` | `mount.axis1.rms_error_arcsec` / `axis0` | |
| `mount.pointing_model` | `mount.model.filename` | |
| `mount.is_finding_home` | cdk700 | `'True'` while cdk700 waits on `/mount/find_home` |
| `mount.encoders_have_been_set` | `mount.axis0/1.is_homed` if present (not in stock 4.1.4), else cdk700 | `'True'` after a successful `home()` in this process |
| `status.lst` | `site.lmst_hours` | `'HH MM SS.SSS'` |
| `status.utc`, `status.jd` | `response.timestamp_utc`, `mount.julian_date` | |
| `m3.port` | `m3.port` | int → `'1'`/`'2'`; `'0'` = between ports / no M3 (same numbering as PWI2) |
| `m3.moving_rotate` | derived | `'True'` while `m3.port` is 0 |
| `focuser.*` | `focuser.*` | the **GUI-selected** focuser (= current M3 port with "Select from M3") |
| `focuserN.position` (N = M3 port) | `focuser.position` | **microns** (as PWI2), rounded to an integer string so `int()` works |
| `focuserN.moving` / `goto_complete` | `focuser.is_moving` | `goto_complete = not moving` |
| `focuserN.*` (N ≠ M3 port) | cdk700 | last position seen on that port, else `UNKNOWN`; other fields `UNKNOWN` |
| `focuserN.finding_home` | cdk700 | while cdk700 waits on `/focuser/find_home` |
| `rotator1.position` (Rotator1's port) | `rotator.mech_position_degs` | **mechanical** angle, degrees; PWI4 always reports Rotator1 here |
| `rotator2.position` (other port, M3 on it) | `mount.field_angle_at_target_degs + offset − rotator.field_angle_degs` | inverts PWI4's own mech→field formula; assumes the PWI4 rotator settings "reverse direction" and "altitude compensation" are off (see risks) |
| `rotatorN.position` (M3 elsewhere) | cdk700 | last seen/commanded value, else `UNKNOWN` |
| `rotatorN.goto_complete` (M3 port) | `rotator.is_slewing`, `rotator.field_angle_degs` | not derotating: `not is_slewing`; derotating: field angle within 0.5° of the derotation target |
| `rotator.altaz_derotate` | cdk700 + `rotator.is_slewing` | `'True'` when cdk700 started field tracking on this port and PWI4 still reports it (is_slewing) |
| `rotator.connected` | `rotator.is_connected` | Rotator1 only |
| `temperature.primary/secondary/m3/ambient` | `/temperatures/pw1000` | °C; -999 or other values ≤ -99 → `UNKNOWN`, so `guessFocus` uses T0/dT0 instead of a sentinel |
| `temperature.backplate` | (none) | `UNKNOWN` |
| `fans.on` | (none) | `UNKNOWN` |

## Behaviour differences in PWI4 mode (by design)

* **No fake status.** `getStatus()` raises `pwi4.PWI4Error` when PWI4 cannot be
  read (timeout, refused, garbage, HTTP error).  `initialize`, `isInitialized`,
  `inPosition`, `home`, `m3port_switch`, `isMoving` (returns True) and the
  focuser/rotator `*AndWait` methods catch it and return False, so `recover()`'s
  ladder (reconnect → restart PWI4 → home → power cycle → email) still runs.
  Shared routines that call `getStatus()` directly (e.g. `acquireTarget`'s
  status read, `parangle`) propagate the error instead of acting on made-up
  data.  `guessFocus` falls back to the model at T0.
* Every HTTP request has a timeout; every wait loop has a timeout; focuser and
  rotator locks are released in `try/finally`; `m3port_switch` sends `/m3/goto`
  once and gives up after `PWI4_M3_TIMEOUT` (sending `/m3/stop`), returning False.
* **One port at a time.** PWI4 commands only the focuser/rotator of the current
  M3 port.  `focuserMove*`, `focuserIncrement`, `rotatorMove`, `rotatorIncrement`,
  `rotatorStartDerotating` and the `*HomeAndWait` methods first switch the M3
  to the requested port with `m3port_switch` (which also loads that port's PWI4
  model).  `focuserStop`/`rotatorStop` on a port the M3 is not on do nothing and
  return False.  `focuserDisconnect('2')` is refused, because PWI4's
  `/focuser/disconnect` would disconnect Focuser1.  Before the M3 leaves a
  port, derotation there is stopped, since PWI4 can no longer address that rotator.
* Derotation: PWI2's `derotatestart` becomes `/rotator/goto_field` at the
  rotator's current field angle (after waiting for any `goto_mech` to finish);
  `derotatestop` becomes `/rotator/stop`.  PWI4's `goto_mech` ends field tracking,
  whereas PWI2 kept derotating across a mechanical move.  So when `rotatorMove`
  interrupts derotation, cdk700 keeps reporting `altaz_derotate = 'True'` and
  restarts field tracking from the new angle at the next `rotatorStartDerotating`
  (which `inPosition(derotate=True)` calls; `rotatorMove(..., wait=True)` restarts
  it itself).  This keeps `acquireTarget`'s sequence (initialize → rotatorMove →
  slew → inPosition) working as before.
* After an M3 port change, cdk700 waits `PWI4_M3_SETTLE` seconds.  PWI4's GUI
  re-selects the new port's focuser/rotator on a refresh timer, and commands
  sent before that go to the old port's device.
* `mountOffsetAltAzFixed` applies the axis offsets directly instead of PWI2's
  2-second jogs followed by `mount stop`.
* `mountSync` is not available in PWI4 (returns False, logs an error).
* `shutdown()` disables the motors before disconnecting (PWI2's order was disconnect, then disable).
* Remote process control (`killPWI`, `startPWI`, `restartPWI`, `reboot_telcom`)
  uses the same credentials file and ssh/winexe as before, but runs them via
  argv with a timeout, checks the exit code, and **never logs the password**.
  `startPWI` waits until PWI4 answers `/status` (`PWI4_START_TIMEOUT`) before
  loading the model, instead of sleeping a fixed 10 s.
* `reboot.py` (runs on the telcom PC) also recognizes `PWI4.exe`.

## Pointing models

PWI2 `.PXP` files cannot be loaded by PWI4.  In PWI4 mode cdk700 never sends a
`.PXP` name: `m3port_switch` and `startPWI` load `[PWI4_MODEL]` for the port
when one is configured, and otherwise log a warning and keep whatever model
PWI4 has loaded.  New models must be built on-sky **per M3 port** (PWI4 holds
one active model; cdk700 swaps the file on port changes), then saved under the
names given in `[PWI4_MODEL]`.  `makePointingModel` works in PWI4 mode
(`/mount/model/add_point` + `/mount/model/save` under the configured PWI4 name).

## Main risks to check on site

1. **"Select from M3" must be ticked** on PWI4's Focuser and Rotator tabs.
   Without it, focuser/rotator commands and readings go to whichever device the
   GUI shows, regardless of port.  Nothing in the HTTP API can detect this.
2. **Port-2 rotator position** is derived from the field angle (PWI4 4.1.4
   reports only Rotator1's mechanical angle).  This matters for guiding on
   T1, whose FAU is on port 2 and whose PA = parallactic − mech + ROTATOROFFSET.
   cdk700 logs a warning once if the same formula does not reproduce Rotator1's
   reported angle.  Check on site: `rotatorMove(100,'2',wait=True)`, then
   `getRotatorStatus('2').position` must read 100.
3. Focuser2/Rotator2 must be auto-connected by PWI4: the HTTP connect calls
   reach only device #1.
4. Temperatures: with no PW1000 temperature controller, the focus model runs at
   T0 (the same as missing temperatures).  The FITS M1TEMP and similar keywords
   become UNKNOWN.
5. Offset signs (guiding!) and alt/az offset axes: verify with a star on the
   guider before using the telescope for science.

## On-site cutover checklist (one telescope)

Do this for one telescope first (e.g. T1), with the other telescopes on PWI2.

1. **Prerequisites.** PlaneWave confirms PWI4 supports this CDK700
   (Parker/ACR drives, EFA focusers/rotators/fans, M3).  Note the PWI2 version and
   settings (`Focuser\config1.xml`, `config2.xml`, `M3\config3.xml`, mount
   limits, home/park positions, rotator offsets) and copy the PWI2 `.PXP`
   models somewhere safe.
2. **Install PWI4 on the telcom PC** next to PWI2 (do not uninstall PWI2).  Only
   one of them may own the hardware at a time, so never run both.  Create a
   scheduled task named **`Start PWI4`** (or set `PWI4_START_TASK`) that starts
   `PWI4.exe`.  Allow TCP 8220 from the gateway through the Windows firewall.
3. **Daytime, simulated mount.** With PWI2 stopped, start PWI4 with the
   mount/focuser/rotator/M3 drivers set to *simulator*.  On the gateway, make a
   *copy* of the telescope's ini with `PWI_VERSION = 4` (e.g.
   `telescope_1_pwi4test.ini`) and, in `python2`:
   `t = cdk700.CDK700('telescope_1_pwi4test.ini', base)`; then `t.initialize()`,
   `t.getStatus()` (check the mapping), `t.m3port_switch('2')`,
   `t.focuserMoveAndWait(...)` on both ports, `t.rotatorMove(..., wait=True)`,
   `t.inPosition(...)`, `t.killPWI()`, `t.startPWI()` (this exercises the scheduled task).
   (`python2 tests/fake_pwi4_server.py` gives the same API without Windows.)
4. **Real hardware, daytime, dome closed.** Switch the PWI4 drivers to the
   real mount (CDK700 driver), EFA focusers/rotators and M3.  In the PWI4 GUI:
   connect, enable, **find home**, set the altitude/azimuth limits and the park
   position to match PWI2's, tick **Select from M3** on the Focuser and
   Rotator tabs, and turn on auto-connect for both focusers and rotators.  Set
   the rotators' "reverse direction" and "altitude compensation" as PlaneWave
   recommends.  If either is on, re-check risk 2.  Check both M3 ports, both
   focusers (positions in microns match PWI2's scale) and both rotators
   (mechanical angles match PWI2's).
5. **Night: pointing models per M3 port.** For each port: select the port, clear
   the model, build a model on-sky (PWI4's own model builder, or
   `makePointingModel` once a `[PWI4_MODEL]` name is set), save it under the
   `[PWI4_MODEL]` name.  Verify the offset signs and the rotator/PA convention
   with a guide star on the FAU.  If rotator offsets differ from PWI2's,
   recalibrate `[ROTATOROFFSET]` with `calibrateRotator`.
6. **Flip.** In `config/telescope_N.ini`: `PWI_VERSION = 4`, fill
   `[PWI4_MODEL]`, set `PWI4_START_TASK`/`PWI4_EXE` if they differ from the
   defaults.  Make sure PWI2 is not running (and that its "Start PWI" task is
   not triggered by anything else), then restart the control code.  Watch the
   first night: slews, autofocus, FAU acquisition and guiding.
7. **Roll back** (any time): stop PWI4 (`taskkill /IM PWI4.exe /f`), set
   `PWI_VERSION = 2` (or comment it out), start PWI2 (`Start PWI` task), and
   restart the control code.  PWI2's settings and `.PXP` models are untouched
   by PWI4.  After hardware has been driven by PWI4, home the mount in PWI2
   before observing.

## Tests

`python2 -m unittest discover -s tests` (from the repository root; stdlib only,
no hardware).  See `tests/README.md`.
