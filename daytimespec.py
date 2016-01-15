import sys
import os
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

	# home all telescopes (make sure they're pointing north)
	# ***not in danger of pointing at the Sun***
	minerva.telescope_park()

	'''
	# change to the imaging port for calibrations
	for telescope in minerva.telescopes:
		telescope.m3port_switch(telescope.port['IMAGER'])
	minerva.specCalib()

	ipdb.set_trace()

	# change to the spectrograph port
	for telescope in minerva.telescopes:
		telescope.m3port_switch(telescope.port['FAU'])

	# create the sunOverride.txt file
	# force manual creation of this file??
	with open('sunOverride.txt','w') as fh:
		fh.write(str(datetime.datetime.utcnow()))

	# open the north roof segment only if the weather is ok
	minerva.domeControlThread(day=True)

	# wait for domes to open
	t0 = datetime.datetime.utcnow()
	for dome in minerva.domes:
		status = dome.status()
		while status['Shutter1'] <> 'OPEN':
			print 'Enclosure closed; waiting for dome to open (status["Shutter1"] = ' + status['Shutter1'] + ")"
			timeelapsed = (datetime.datetime.utcnow()-t0).total_seconds()
			if timeelapsed > 600:
				print 'Enclosure still closed after 10 minutes; exiting'
				sys.exit()
			time.sleep(30)
			status = dome.status()
	'''
       	target = {
		"name" : "daytimeSky",
		"ra" : 0.0, 
		"dec" : 0.0,
		"starttime" : "2015-01-01 00:00:00", 
		"endtime" : "2018-01-01 00:00:00", 
		"spectroscopy": True, 
		"filter": ["rp"], 
		"num": [10], 
		"exptime": [150], 
		"fauexptime": 1, 
		"defocus": 0.0, 
		"selfguide": True, 
		"guide": False, 
		"cycleFilter": True, 
		"positionAngle": 0.0, 
		"pmra": 0.0, 
		"pmdec" : 0.0, 
		"parallax" : 0.0, 
		"template" : False, 
		"i2": True,
		"comment":"daytime sky spectrum"}
	

	target['exptime'] = [150]
	for i in range(target['num'][0]): minerva.takeSpectrum(target)

	target['i2'] = False
	for i in range(target['num'][0]): minerva.takeSpectrum(target)

	# all done; close the dome
	minerva.observing=False

	# wait for domes to close
	t0 = datetime.datetime.utcnow()
	for dome in minerva.domes:
		status = dome.status()
		while status['Shutter1'] <> 'CLOSED':
			print 'Enclosure open; waiting for dome to close (status["Shutter1"] = ' + status['Shutter1'] + ")"
			timeelapsed = (datetime.datetime.utcnow()-t0).total_seconds()
			if timeelapsed > 600:
				print 'Enclosure still closed after 10 minutes; exiting'
				sys.exit()
			time.sleep(30)
			status = dome.status()

	# change to the spectrograph imaging port for calibrations
	for telescope in minerva.telescopes:
		telescope.m3port_switch(telescope.port['IMAGER'])
	minerva.specCalib()

	# remove the sun override
	if os.path.exists('sunOverride.txt'): os.remove('sunOverride.txt')

	sys.exit()

	ipdb.set_trace()


	'''
	target = {
		"name" : "HR398", 
		"ra" : 1.42958611111,
		"dec" : 70.9798869722, 
		"starttime" : "2015-01-01 00:00:00", 
		"endtime" : "2018-01-01 00:00:00", 
		"spectroscopy": True, 
		"filter": ["rp"], 
		"num": [1], 
		"exptime": [300], 
		"fauexptime": 1, 
		"defocus": 0.0, 
		"selfguide": True, 
		"guide": False, 
		"cycleFilter": True, 
		"positionAngle": 0.0, 
		"pmra": 9.31, 
		"pmdec" : -14.19, 
		"parallax" : 6.89, 
		"template" : False, 
		"i2": True}
	'''

	minerva.doSpectra(target,[1,2,4])
#	ipdb.set_trace()


#	target['name'] = 'HD19373'
#	minerva.takeSpectrum(target)
#	ipdb.set_trace()

#	minerva.specCalib(nbias=1,ndark=1,nflat=1)


#	ipdb.set_trace()

#	minerva.takeSpectrum(target)
#	ipdb.set_trace()



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
	
	
	
	
