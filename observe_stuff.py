from pwi2control import PWI2 as PWI2
from win32com.client import Dispatch


def observe_stuff(ra, dec, exptimecdk, exptc11):
    pwi2 = PWI2(host="192.168.1.70", port=8080)
    
#first, we want to make sure that the telescope is connected, etc.
#RA DEC can be strings in HH MM SS or decimal
        pwi2.mountConnect()
        pwi2.mountTrackingOn()    
        pwi2.mountGotoRaDecJ2000(ra, dec)
        
    