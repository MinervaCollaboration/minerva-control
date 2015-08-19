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
        for i in range(3):
            print 'Taking arc '+str(i)
            minerva.takeSpectrum(1.0,'arc')

        

        minerva.spectrograph.thar_turn_off()

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
