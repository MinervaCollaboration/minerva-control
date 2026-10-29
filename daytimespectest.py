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
	minerva.telescope_park()

	for telescope in minerva.telescopes:
		if not telescope.inPosition(alt=45.0,az=0.0, pointingTolerance=3600.0, tracking=False, derotate=False):
			mail.send("T" + telescope.num + " failed to home; skipping daytime sky spectra",
				  "Dear Benevolent Humans,\n\n"
				  "T" + telescope.num + " failed to home properly and I fear it could "
				  "point at the Sun if I opened the dome. Can you please investigate "
				  "and restart daytimespec.py when it's all clear?\n\n"
				  "Love,\nMINERVA",level='serious')
			sys.exit()

	# change to the spectrograph port
	for telescope in minerva.telescopes:
		telescope.m3port_switch(telescope.port['FAU'])


       	target = {
		"name" : "daytimeSkyExpmeter",
		"ra" : 0.0, 
		"dec" : 0.0,
		"starttime" : "2015-01-01 00:00:00", 
		"endtime" : "2018-01-01 00:00:00", 
		"spectroscopy": True, 
		"filter": ["rp"], 
		"num": [10], 
		"exptime": [1],
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
	
	while True:
		status = minerva.domes[0].status()
		while True:
			minerva.logger.info("Beginning daytimesky spectrum with iodine")
			minerva.takeSpectrum(target)


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

	
	
	
	
