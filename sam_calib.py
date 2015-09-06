#Minerva system main routine
#create master control object and run one of the observing scripts
import sys
sys.dont_write_bytecode = True
from minerva_library import control
import ipdb, datetime, time, socket
import os
#from si.client import SIClient
#from si.imager import Imager

if __name__ == '__main__':
        #S Start server stuff in seperate terminals
        os.system('start cmd /c python minerva_library\PT100.py')
        os.system('start cmd /c python minerva_library\spectrograph_server.py')
        time.sleep(15)

	base_directory = '/home/minerva/minerva_control'
	#S testing
	base_directory  = 'C:/minerva-control'
	if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	minerva = control.control('control.ini',base_directory)
       # minerva.config_calib()
        pred_time = minerva.spec_calib_time()/60.
        start = time.time()
        minerva.spec_calibration()
        end = time.time()
        print 'Calib took '+str((end-start)/60.)+' versus '+str(pred_time)

##        minerva.spectrograph.white_turn_on()
##        for i in range(3):
##            print 'Taking flat '+str(i)
##            minerva.takeSpectrum(1.0,'flat')
##        minerva.spectrograph.white_turn_off()
##
##        for i in range(3):
##            print 'Taking dark '+str(i)
##            minerva.takeSpectrum(1.0,'dark')
##
##        for i in range(3):
##            print 'Taking bias '+str(i)
##            minerva.takeSpectrum(0.0,'bias')
##
##        for i in range(3):
##            print 'Taking test '+str(i)
##            minerva.takeSpectrum(1.0,'test')
