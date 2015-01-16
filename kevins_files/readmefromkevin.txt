pwi2control.py: provides a wrapper around the HTTP requests and XML responses used for PWI2. I think I sent Mike an early version of this awhile back. The latest version includes wrapper functions for all of the commands that can be sent via HTTP, and includes some sample code at the beginning to show how to use it.

maxim_take_data.py: shows how to use some basic features in Maxim (launching the app, connecting, taking an exposure, saving an image). This particular script is actually one that I use to take pairs of flats when measuring the gain of a camera. Depends on the "pywin32" package for talking to Maxim's COM server.

sbigapi.py: can be used to talk to your SBIG cameras directly via Python. This uses the "ctypes" library, which comes with Python, to call the SBIG library which is normally available to C/C++.  NOTE: I haven't tested the subframing code, so there may still be some work to be done here.

caltech_guider.py: I wrote this awhile back to show how to use Maxim and the guide camera to center a bright star on an arbitrary pixel. You might find some of this to be useful.

landolts.py: This is a script I wrote with Jon Swift when we were commissioning T3 and T4 here at PlaneWave. It uses the ASCOM driver for PWI2 to slew to a series of targets (loaded from MountPosition.csv; sample file attached), take images, and save them. Note that this as a minor dependency on TheSky6 (for precessing from J2000 to Apparent coordinates since ASCOM expects Apparent). This could be replaced with the NOVAS module that now comes with ASCOM, or a native Python precession/nutation function.

