#Minerva system main routine
#create master control object and run one of the observing scripts
import sys
sys.dont_write_bytecode = True
from minerva_library import control
import ipdb, datetime, time, socket
#from si.client import SIClient
#from si.imager import Imager

if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
	if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	minerva = control.control('control.ini',base_directory)

	print minerva.spectrograph.i2stage_get_pos()
	ipdb.set_trace() 
       # minerva.spec_equipment_check('HD12121')
        
       
