import sys
import os
sys.dont_write_bytecode = True
from minerva_library import control
from minerva_library import utils
import ipdb, datetime, time, socket
import threading
from minerva_library import mail

if __name__ == '__main__':


	utils.killmain()

	base_directory = '/home/minerva/minerva-control'
	if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	minerva = control.control('control_day.ini',base_directory)

	# stop at 2:30 pm local (so calibrations can finish before daily reboot at 3:30 pm)
	endtime = datetime.datetime(datetime.datetime.utcnow().year, datetime.datetime.utcnow().month, datetime.datetime.utcnow().day, 21, 30, 0)

	# home all telescopes (make sure they're pointing north)
	# ***not in danger of pointing at the Sun***
	minerva.telescope_park(parkAlt=45.0)

	for telescope in minerva.telescopes:
		if not telescope.inPosition(alt=45.0,az=0.0, pointingTolerance=3600.0, tracking=False, derotate=False):
			mail.send("T" + telescope.num + " failed to home; skipping daytime sky spectra",
				  "Dear Benevolent Humans,\n\n"
				  "T" + telescope.num + " failed to home properly and I fear it could "
				  "point at the Sun if I opened the dome. Can you please investigate "
				  "and restart daytimespec.py when it's all clear?\n\n"
				  "Love,\nMINERVA",level='serious')
			sys.exit()

	# only do calibrations if it was started by the cron job (or within 30 minutes of the nominal start time)
	if datetime.datetime.now().hour == 8:
		# change to the imaging port for calibrations
		for telescope in minerva.telescopes:
			telescope.m3port_switch(telescope.port['IMAGER'])

		minerva.specCalib(darkexptime=150.0)

	# change to the spectrograph port
	for telescope in minerva.telescopes:
		telescope.m3port_switch(telescope.port['FAU'])


	if datetime.datetime.utcnow() < endtime:
		# create the sunOverride.txt file
		# force manual creation of this file??
		for dome in minerva.domes:
			with open(minerva.base_directory + '/minerva_library/sunOverride.' + dome.id + '.txt','w') as fh:
				fh.write(str(datetime.datetime.utcnow()))

			with open(minerva.base_directory + '/minerva_library/' + dome.id + '.request.txt','w') as fh:
				fh.write(str(datetime.datetime.utcnow()))
		
	# wait for domes to open
	t0 = datetime.datetime.utcnow()
	for dome in minerva.domes:
		status = dome.status()
		while status['Shutter1'] <> 'OPEN' and datetime.datetime.utcnow() < endtime:
			minerva.logger.info('Enclosure closed; waiting for dome to open (status["Shutter1"] = ' + status['Shutter1'] + ")")
			timeelapsed = (datetime.datetime.utcnow()-t0).total_seconds()
			time.sleep(30)
			status = dome.status()

       	target = {
		"name" : "daytimeSkyExpmeter",
		"ra" : 0.0, 
		"dec" : 0.0,
		"starttime" : "2015-01-01 00:00:00", 
		"endtime" : "2018-01-01 00:00:00", 
		"spectroscopy": True, 
		"filter": ["rp"], 
		"num": [10], 
		"exptime": [600],
		"expmeter": 2.5e8,
		#"expmeter": 3.8e5,
		#"expmeter": 2e9,
		"fauexptime": 1, 
		"defocus": 0.0, 
		"bstar": True, 
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
	

	'''
	# take several exposures with the iodine stage in various positions
	while (datetime.datetime.utcnow() - endtime).total_seconds() < 0:
		status = minerva.domes[0].status()
		isOpen = status['Shutter1'] == 'OPEN'
		while isOpen and (datetime.datetime.utcnow() - endtime).total_seconds() < 0:
			target['exptime'] = [150]
			for i in range(10):
				target['i2manualpos'] = 140 + i
				minerva.takeSpectrum(target)
				if (datetime.datetime.utcnow() - endtime).total_seconds() > 0: break
				
	try: del target['i2manualpos']
	except: pass
	'''

	while datetime.datetime.utcnow() < endtime:

		status = minerva.domes[0].status()
		isOpen = status['Shutter1'] == 'OPEN'
		while isOpen and (datetime.datetime.utcnow() - endtime).total_seconds() < 0:
			minerva.logger.info("Beginning daytimesky spectrum with iodine")
			minerva.takeSpectrum(target)
			
			'''
			# alternate between with and without iodine
			target['i2'] = True
			for i in range(target['num'][0]): 
				print 'this is before the break'
				if (datetime.datetime.utcnow() - endtime).total_seconds() > 0: break
				minerva.logger.info("Beginning daytimesky spectrum with iodine")
				minerva.takeSpectrum(target)
			
			target['i2'] = False
			for i in range(target['num'][0]): 
				print 'this is before the break'
				if (datetime.datetime.utcnow() - endtime).total_seconds() > 0: break
				minerva.logger.info("Beginning daytimesky spectrum without iodine")
				minerva.takeSpectrum(target)
			'''

			status = minerva.domes[0].status()
			isOpen = status['Shutter1'] == 'OPEN'

		if not minerva.domes[0].isOpen:
			minerva.logger.info("Dome not open, waiting for conditions to improve")
			time.sleep(60)

	# all done; close the dome
	if os.path.exists(minerva.base_directory + '/minerva_library/aqawan1.request.txt'): os.remove(minerva.base_directory + '/minerva_library/aqawan1.request.txt')
	if os.path.exists(minerva.base_directory + '/minerva_library/aqawan2.request.txt'): os.remove(minerva.base_directory + '/minerva_library/aqawan2.request.txt')

	# wait for domes to close
	t0 = datetime.datetime.utcnow()
	for dome in minerva.domes:
		while dome.isOpen():
			minerva.logger.info('Enclosure open; waiting for dome to close')
			timeelapsed = (datetime.datetime.utcnow()-t0).total_seconds()
			if timeelapsed > 600:
				minerva.logger.info('Enclosure still closed after 10 minutes; exiting')
				sys.exit()
			time.sleep(30)
			status = dome.status()

	# remove the sun override
	for dome in minerva.domes:
		sunfile = minerva.base_directory + '/minverva_library/sunOverride.' + dome.id + '.txt'
		if os.path.exists(sunfile): os.remove(sunfile)

	# change to the spectrograph imaging port for calibrations
	for telescope in minerva.telescopes:
		telescope.m3port_switch(telescope.port['IMAGER'])
	minerva.specCalib(darkexptime=150.0)

	
	
	
	
