import get_dome_temp_rh as dt
import time
#This is a little code that will get called by the Scheduled Task to udpate
#a file called dome_metrology.dat with update info about the dome conditions


data = dt.get_dome_temp_rh()

f = open('C:\\minerva-control\dome_metrology.dat','a')

f.write(time.strftime('%x %X')+'  '+str(data['rh'])+'    '+str(data['temp'])+'    '+str(data['dewp']))
f.write("\n")

f.close()