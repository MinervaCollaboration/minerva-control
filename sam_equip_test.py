#Minerva system main routine
#create master control object and run one of the observing scripts
import sys
sys.dont_write_bytecode = True
from minerva_library import control
import ipdb, datetime, time, socket
#from si.client import SIClient
#from si.imager import Imager

if __name__ == '__main__':

	base_directory = '/home/minerva/minerva_control'
	if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	minerva = control.control('control.ini',base_directory)

        minerva.spectrograph.thar_turn_on()
        minerva.spectrograph.thar_turn_on()

        time.sleep(3)
        print minerva.spectrograph.time_tracker_check(minerva.spectrograph.thar_file)
        time.sleep(3)
        minerva.spectrograph.thar_turn_off()
        
        print 'thar on'
        
       # minerva.spec_equipment_check('HD12121')
        
       
