import matplotlib
#matplotlib.use('Agg')
import sys
sys.dont_write_bytecode = True
from minerva_library import control
import ipdb, datetime, time, socket
#from si.client import SIClient
#from si.imager import Imager
import threading
import math
import numpy as np
from minerva_library import rv_control
from minerva_library import newauto
from minerva_library import utils

if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
	if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	minerva = control.control('control.ini',base_directory)

#	ipdb.set_trace()
#	minerva.telescopes[0].makePointingModel(minerva,npoints=50,exptime=2.0)
#	minerva.endNight(num=3,email=False,kiwispec=False)
	
	ipdb.set_trace()
#	ipdb.set_trace()

#	ipdb.set_trace()
	"""
	target = {'name':'newexpmetertest',
		  'exptime':[15],
		  'fauexptime':1,#.1,
		  'filter':["V"],
		  'expmeter':300,
		  'tracking':False,
		  'spectroscopy':True,
		  'i2': True,
		  }
	minerva.takeSpectrum(target)
	"""
	ipdb.set_trace()
#	minerva.night = 'n20160422'
	target = {
		"name": "HD62613", 
#		"ra": 7.9381193, 
#		"dec": 80.26554, 
		"starttime": datetime.datetime(2016,1,1),
		"endtime": datetime.datetime(2017,1,1),
		"spectroscopy": True, 
		"filter": ["rp"], 
		"num": [3], 
		"exptime": [1800.0], 
		"fauexptime": 1,#5.0, 
		"defocus": 0.0, 
		"positionAngle": 0.0, 
		"pmra": 0.0, 
		"pmdec": 0.0, 
		"parallax": 0.0, 
		"rv": 0.0, 
		"i2": True,
		}
	newauto.autofocus(minerva,1,target=target)
	ipdb.set_trace()
#	rv_control.acquireFocusGuide(minerva,target,1)
#	minerva.takeFauImage(target,telescope_num=1)
#	ipdb.set_trace()

	rv_control.doSpectra(minerva, target, [1,2,3,4], test=True)

	ipdb.set_trace()

#	minerva.telescopes[0].initialize()
#	minerva.spectrograph.connect_si_imager()
#	minerva.spectrograph.take_image(exptime=5)

#	minerva.spectrograph.si_imager_set_format_params()

#	ipdb.set_trace()
#	t1 = datetime.datetime.utcnow()
#	t0 = datetime.datetime(year=2016,month=04,day=22,hour=5)
#	tf = datetime.datetime(year=2016,month=04,day=22,hour=5,minute=30)
#	minerva.spectrograph.getexpflux(t0,tf=tf)
#	print (datetime.datetime.utcnow()-t1).total_seconds()
#	minerva.telescopes[1].makePointingModel(minerva,npoints=100,exptime=2.0)

	ipdb.set_trace()

	target = {'name':'newexpmetertest',
		  'exptime':[3],
		  'fauexptime':1,#.1,
		  'filter':["V"],
		  'expmeter':3000,
		  'tracking':False,
		  'spectroscopy':True,
		  'i2': True,
		  }
	minerva.takeSpectrum(target)
	ipdb.set_trace()
	newauto.autofocus(minerva,1,target=target,defocus_step=0.03,num_steps=3,dome_override=True)
	ipdb.set_trace()
	minerva.takeSpectrum(target,[1,2,3,4])
	
	
#	minerva.telescopes[0].m3port_switch('2',force=True)
#	newauto.autofocus(minerva,1,target=target)
#	newauto.autofocus(minerva,3,target=target)
#	minerva.telescopes[3].calibrateRotator(minerva.cameras[3])
#	minerva.telescopes[0].makePointingModel(minerva.cameras[0],npoints=1)


	exptime = 1.0
#	minerva.telescopes[0].makePointingModel(minerva.cameras[0],npoints=1)
#	ipdb.set_trace()
#	rv_control.backlight(minerva,tele_list=[4],exptime=exptime)
#	x,y = rv_control.find_fiber('/Data/t4/' + minerva.night + '/' + minerva.cameras[3].file_name, minerva.cameras[3])


#	minerva.night1 = 'n20160401'

	rv_control.backlight(minerva,exptime=exptime,tele_list=[2])
	x,y = rv_control.find_fiber('/Data/t2/' + minerva.night + '/' + minerva.cameras[1].file_name, minerva.cameras[1])
	
	ipdb.set_trace()
	for ind in [3]:
		path = '/Data/t%s/%s/%s'\
		    %(str(ind+1),minerva.night,\
                              minerva.cameras[ind].file_name)
		rv_control.find_fiber(path, minerva.cameras[ind],control=minerva)



#	x,y = rv_control.find_fiber('/Data/t1/' + minerva.night1 + '/' + minerva.cameras[0].file_name, minerva.cameras[0],control=minerva)
#	x,y = rv_control.find_fiber('/Data/t2/' + minerva.night1 + '/' + minerva.cameras[1].file_name, minerva.cameras[1],control=minerva)
#	x,y = rv_control.find_fiber('/Data/t3/' + minerva.night1 + '/' + minerva.cameras[2].file_name, minerva.cameras[2],control=minerva)
#	x,y = rv_control.find_fiber('/Data/t4/' + minerva.night1 + '/' + minerva.cameras[3].file_name, minerva.cameras[3],control=minerva)

#	minerva.endNight(num=1,email=False)
	ipdb.set_trace()


	target = {
		"name": "HD62613", 
		"ra": 7.9381193, 
		"dec": 80.26554, 
		"starttime": datetime.datetime(2016,3,18,2,54,33), 
		"endtime": datetime.datetime(2016,3,18,12,8,2), 
		"spectroscopy": True, 
		"filter": ["rp"], 
		"num": [3], 
		"exptime": [1800.0], 
		"fauexptime": 5.0, 
		"defocus": 0.0, 
		"positionAngle": 0.0, 
		"pmra": 0.0, 
		"pmdec": 0.0, 
		"parallax": 0.0, 
		"rv": 0.0, 
		"i2": True,
		}

	target = {
		"name": "HR4828", 
		"ra": 12.6980833, 
		"dec": 10.2355556, 
		"starttime": datetime.datetime(2016,3,18,3,34,30),
		"endtime": datetime.datetime(2016,3,18,12,8,2), 
		"spectroscopy": True, 
		"filter": ["rp"], 
		"num": [3], 
		"exptime": [1800.0], 
		"fauexptime": 5.0, 
		"defocus": 0.0, 
		"selfguide": True, 
		"guide": False, 
		"cycleFilter": True, 
		"positionAngle": 0.0, 
		"pmra": 0.0, 
		"pmdec": 0.0, 
		"parallax": 0.0, 
		"rv": 0.0, 
		"i2": True, 
		"vmag": 4.88, 
		"comment": "", 
		"expectedStart": "2016-03-18 04:30:39.042731", 
		"expectedEnd": "2016-03-18 06:06:44.142731",
		}

#	minerva.telescopes[0].radectoaltaz(target['ra'],target['dec'],date=datetime.datetime(2016,3,19,9,19,43))
#	ipdb.set_trace()

	minerva.telescopes[0].acquireTarget(target,tracking=False,derotate=False)

	ipdb.set_trace()

	

#	minerva.cameras[0].take_image(5,'V','testexp')

	minerva.endNight(night='n20160314',kiwispec=True)
	sys.exit()

	ipdb.set_trace()
#	minerva.spectrograph.i2stage_move('flat')
#	ipdb.set_trace()

	'''
#	ipdb.set_trace()
#	target = {'name':'fiberflat_T3','ra':0,'dec':0,'i2':True,'exptime':[15]}
#	minerva.takeSpectrum(target)
#	target = {'name':'fiberflat_T3','ra':0,'dec':0,'i2':False,'exptime':[15]}
#	minerva.takeSpectrum(target)
#	ipdb.set_trace()
	target = {'name':'thar_T4_i2test','ra':0,'dec':0,'i2':True,'exptime':[30]}
	minerva.takeSpectrum(target)
	target = {'name':'thar_T4_i2test','ra':0,'dec':0,'i2':False,'exptime':[30]}
	minerva.takeSpectrum(target)

	ipdb.set_trace()
#	for i in np.arange(20):
#		i2pos = 150 + i
#		target = {'name':'i2test02_T3','ra':0,'dec':0,'i2manualpos':i2pos,'exptime':[30]}	
	target = {'name':'thar_T3_i2test','ra':0,'dec':0,'i2':True,'exptime':[300]}
#	target = {'name':'fiberflat_T1','ra':0,'dec':0,'i2':False,'exptime':[30]}
	minerva.takeSpectrum(target)
	
	target = {'name':'thar_T3_i2test','ra':0,'dec':0,'i2':False,'exptime':[300]}
	minerva.takeSpectrum(target)
#	target = {'name':'fiberflat_T1','ra':0,'dec':0,'i2':True,'exptime':[30]}
#	minerva.takeSpectrum(target)
	ipdb.set_trace()


	status = minerva.telescopes[3].getStatus()
	ra = minerva.ten(status.mount.ra_2000)
	dec = minerva.ten(status.mount.dec_2000)
	telalt = float(status.mount.alt_radian)*180.0/math.pi
	telaz = float(status.mount.azm_radian)*180.0/math.pi
	alt,az = minerva.telescopes[3].radectoaltaz(ra,dec)
	
	sep = math.acos( math.sin(telalt*math.pi/180.0)*math.sin(alt*math.pi/180.0)+math.cos(telalt*math.pi/180.0)*math.cos(alt*math.pi/180.0)\
				 *math.cos((telaz-az)*math.pi/180.0) )*(180.0/math.pi)*3600.0

	print telalt, alt
	print telaz, az
	print sep

	ipdb.set_trace()

	if False:
		target = {
			"name" : "HD19373", 
			"ra" : 3.15111666667, 
			"dec" : 49.6132777778, 
			"fauexptime" : 1,
			"spectroscopy" : True
			}

		telnum = 2
#		minerva.telescopes[telnum-1].acquireTarget(target)
		minerva.cameras[telnum-1].fau.guiding=True
		minerva.cameras[telnum-1].fau.acquisition_tolerance=1.5
		minerva.fauguide(target,telnum,acquireonly=False)
		ipdb.set_trace()
#	'''	
	"""
	target = {
		"name" : "HD19373", 
		"ra" : 3.15111666667, 
		"dec" : 49.6132777778, 
		"starttime" : datetime.datetime(2015,01,01,0,0,0), 
		"endtime" : datetime.datetime(2018,01,01,0,0,0), 
		"spectroscopy": True, 
		"filter": ["rp"], 
		"num": [1], 
		"exptime": [10], 
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
		"i2": False,
		"comment":"RV standard star"}

	minerva.autofocus(4,fau=True,target=target)
	"""
	target = {
		"name" : "HD125455", 
		"ra" : 20.5,#14.3263513,
		"dec" : -5.15119,
		"starttime" : datetime.datetime(2015,01,01,0,0,0), 
		"endtime" : datetime.datetime(2018,01,01,0,0,0), 
		"spectroscopy": True, 
		"filter": ["rp"], 
		"num": [1], 
		"exptime": [10], 
		"fauexptime": 20, 
		"defocus": 0.0, 
		"selfguide": True, 
		"guide": False, 
		"cycleFilter": True, 
		"positionAngle": 0.0, 
		"template" : False, 
		"i2": False,
		"comment":"RV standard star"}
	ipdb.set_trace()
	newauto.autofocus(minerva,3,target=target)
	rv_control.doSpectra(minerva,target,[1,2,3,4])
	ipdb.set_trace()

#	target['name'] = 'ThAr_T1'
#	target['exptime'] = [60]
#	minerva.takeSpectrum(target)
#	ipdb.set_trace()

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
	
	
	
	
