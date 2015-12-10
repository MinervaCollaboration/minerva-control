import aqawan
import ipdb
import time

base_directory = '/home/minerva/minerva-control'
aqawans = []
aqawans.append(aqawan.aqawan('aqawan_1.ini',base_directory))
aqawans.append(aqawan.aqawan('aqawan_2.ini',base_directory))

while True:

    for aqawan in aqawans:

        response = aqawan.send('CLEAR_FAULTS')
        if "Estop" in response:
            aqawan.send('SON_ALERT_ON')
        else:
            aqawan.send('SON_ALERT_OFF')
            
    time.sleep(1)
