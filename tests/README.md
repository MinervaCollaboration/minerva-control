# Tests

Offline tests for the telescope driver (`minerva_library/cdk700.py`) and its
PWI4 support (`minerva_library/pwi4.py`, `minerva_library/cdk700_pwi4.py`).
They use only the Python 2.7 standard library.  They never contact a
telescope or the observatory network: PWI4 is replaced by a fake HTTP server on
127.0.0.1, and PWI2 HTTP and ssh/winexe calls are replaced by recorders.

Run from the repository root:

    python2 -m unittest discover -s tests

Add `-v` to list the tests.  The whole suite takes a minute or two, because
some tests wait out real (short) timeouts.

| file | what it checks |
|---|---|
| `test_cdk700_pwi2_unchanged.py` | a PWI2 telescope sends exactly the same HTTP requests and remote commands as the original code (`data/pwi2_golden_requests.golden`, recorded from master ace883b) and is the default |
| `test_pwi4_client.py` | PWI4 HTTP client: URLs, parameters, timeouts on a hung server, connection refused, garbage replies, HTTP errors |
| `test_pwi4_status_mapping.py` | PWI4 `/status` → PWI2-shaped status fields (units, formats, M3 ports, per-port focusers/rotators, temperatures) |
| `test_cdk700_pwi4.py` | `CDK700` with `PWI_VERSION = 4` against the fake server: connect/enable/home, slews and `inPosition`, tracking, offsets, focuser moves and lock release on errors, rotator moves and derotation, M3 switching with timeout, pointing models, failures, PWI4 process control (no password in logs) |

`support.py` installs small stand-ins for the heavy imports of `cdk700.py`
(numpy, astropy, ephem, matplotlib, mail, pdu, ...) and builds a throw-away
`base_directory` with a test `telescope_9.ini`.  If `configobj` is installed,
the real package is used.

`fake_pwi4_server.py` can also be run on its own:
`python2 tests/fake_pwi4_server.py --port 8220`.  This gives a PWI4-like API
for trying cdk700 by hand (point a copy of a telescope ini at 127.0.0.1 with
`PWI_VERSION = 4`).

To re-record the PWI2 golden file (do this only for an intended PWI2 change):
`python2 tests/test_cdk700_pwi2_unchanged.py --write`.
