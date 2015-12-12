#Minerva system main routine
#create master control object and run one of the observing scripts
import sys
sys.dont_write_bytecode = True
from minerva_library import control
import ipdb, datetime, time, socket
#from si.client import SIClient
#from si.imager import Imager
import threading

if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
	if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	minerva = control.control('control.ini',base_directory)

	target = {
		"name" : "test", 
		"ra" : 3.15111666667, 
		"dec" : 49.6132777778, 
		"starttime" : "2015-01-01 00:00:00", 
		"endtime" : "2018-01-01 00:00:00", 
		"spectroscopy": True, 
		"filter": ["rp"], 
		"num": [100], 
		"exptime": [0.01], 
		"fauexptime": 1, 
		"defocus": 0.0, 
		"selfguide": True, 
		"guide": False, 
		"cycleFilter": True, 
		"positionAngle": 0.0, 
		"pmra": 1262.41, 
		"pmdec" : -91.5, 
		"parallax" : 94.87, 
		"template" : False, 
		"i2": False}

	minerva.takeSpectrum(target)
	ipdb.set_trace()

#	minerva.takeSpectrum(target)
#	ipdb.set_trace()

	minerva.doSpectra(target,[3])
	ipdb.set_trace()


	minerva.cameras[2].fau.guiding = True
	minerva.guideallfaus(target)
	time.sleep(60)
	minerva.cameras[2].fau.guiding = False
	time.sleep(30)
	

	

#	minerva.endNight(num=2,email=True)
	ipdb.set_trace()
	print minerva.telescopes[0].getStatus()
	minerva.telescope_initialize(1,tracking=True)
	minerva.telescope_mountGotoAltAz(25,0,tele_list=1)
	status = minerva.telescopes[0].getStatus()
	while minerva.telescopes[0].getStatus().rotator.goto_complete == 'False':
		print minerva.telescopes[0].getStatus().rotator.position
		time.sleep(.5)
	ipdb.set_trace()
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
	minerva.telescope_initialize(tele_list = [3,4])
	
        minerva.takeSpectrum(60.0,'test',expmeter=1000000.0)

        ipdb.set_trace()
	tel = 4
	
	minerva.telescopes[tel-1].home()
	minerva.telescopes[tel-1].home_rotator()
	minerva.telescopes[tel-1].initialize_autofocus()
	sys.exit()

	for telescope in minerva.telescopes:
		telescope.initialize()
	for imager in minerva.cameras:
		imager.cool()


	for i in range(0,4):
		minerva.endNight(i+1,email=False)

#	minerva.telescopes[1].initialize()
#	minerva.telescopes[1].park()
#	filename = '/Data/t2/n20150621/n20150621.T2.EPIC2015.V.0044.fits'
#	reference = minerva.guide(filename, None)
#	reference = minerva.guide(filename, reference)
#	ipdb.set_trace()

#	telescope_num = 3
#	minerva.prepNight(telescope_num,email=False)
#	filename = minerva.takeImage(1,'V','test',camera_num=telescope_num)



	

#	minerva.cameras[2].cool()

#	minerva.getPA('/Data/t' + str(telescope_num) + '/' + minerva.site.night + '/' + filename)
#	minerva.getPA('/Data/t2/n20150618/n20150618.T2.OB150941.ip.0083.fits')
#	minerva.getPA('/Data/t2/n20150618/n20150618.T2.OB150572.ip.0082.fits')
#	minerva.getPA('./n20150618.T2.OB150572.ip.0082.fits')

	sys.exit()

	ipdb.set_trace()
	
	
	#run observing script on all telescopes with their own schedule file
	minerva.observingScript_all()
	
	
	# minerva.telcom_enable()
	# minerva.telescope_mountGotoAltAz(30,90)
	
	
	# minerva.doBias(11,2)
	
	
	
	
