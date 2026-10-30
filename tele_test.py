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
        time.sleep(5)
        
#        minerva.spectrograph.get_vacuum_pressure()
#        ipdb.set_trace()
        #S This is throwing due to the calling of undenfined funnction
        #S in spectrograph.py I think. In the funciton expose(), if an
        #S expmeter exists (e.g. number of counts to terminate after, it calls
        #S imager.interrupt(), which doesn't exist anywhere as far as I know.
        #S This may be the source of our problems, but we'll see. I'm adding
        #S a TODO to make sure it's looked at again.
        #TODO
        #ipdb.set_trace()
	minerva.telescope_initialize()
	ipdb.set_trace()

