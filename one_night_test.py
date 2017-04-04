###This is meant to script one night of opening up!

import ephem, time
from win32com.client import Dispatch 
import should_be_open

hopkins = ephem.Observer()
hopkins.lon='-110:52:43.5'
hopkins.lat='31:40:49.4'
hopkins.elevation=3000.

Sun=ephem.Sun(hopkins)

sunalt=(float(repr(Sun.alt)))*57.3

isgood = should_be_open.should_be_open()

while sunalt < (-10.) and isgood == True:
    print 'Sun Altitude is ', sunalt
    print 'Weather is good ', isgood
    hopkins.date=ephem.now()
    Sun=ephem.Sun(hopkins)
    sunalt=(float(repr(Sun.alt)))*57.3
    isgood = should_be_open.should_be_open()
    time.sleep(30)
    
        
dome= Dispatch("ascom.astrohavenpw.dome")
dome.Connected=True
dome.CloseShutter()
time.sleep(60)
dome.CloseShutter()
time.sleep(30)





