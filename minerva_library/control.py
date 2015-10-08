
# master control class for Minerva telescope array,
# most methods operate all instruments in the array in parallel

import sys
import os
import datetime
import logging
import json
import threading 
import time
import math
import ephem
import pyfits
import shutil
import re
import collections
import subprocess
import socket
from configobj import ConfigObj
sys.dont_write_bytecode = True

#Minerva library dependency
import env
import aqawan
import cdk700 
import imager
import spectrograph
import powerswitch
import mail
import ephem
from get_all_centroids import *
import segments

class control:
	
#============Initialize class===============#
	#S The standard init
	def __init__(self,config,base):
                #S This config file literally only contains the logger name I think.
		self.config_file = config
		self.base_directory = base
		#S Only sets logger name right now
		self.load_config()

		self.setup_logger()

		#S See below, lots of new objects created here. 
		self.create_class_objects()
		
		self.logger_lock = threading.Lock()
		self.setup_loggers()
		self.telcom_enable()
		
	#create class objects needed to control Minerva system
	def create_class_objects(self):
		#S Commenting put for operation on minervaMain
		if socket.gethostname() == 'Kiwispec-PC':
                        #S Give some time for the spec_server to start up, get settled.
                        time.sleep(20)
			self.spectrograph = spectrograph.spectrograph('spectrograph.ini',self.base_directory)
			self.site = env.site('site_Wellington.ini',self.base_directory)
			#imager.imager('si_imager.ini',self.base_directory)
                self.domes = []
                self.telescopes = []
                self.cameras = []
		self.npss = []
                if socket.gethostname() == 'Main':

                        self.site = env.site('site_mtHopkins.ini',self.base_directory)

                        for i in range(2):
				aqawanob = aqawan.aqawan('aqawan_' + str(i+1) + '.ini',self.base_directory)
				if aqawanob.heartbeat(): self.domes.append(aqawanob)
				else: self.logger.error("Failed to initialize Aqawan " + str(i+1))

			# initialize the 4 telescopes
			for i in range(4):
				try: 
					self.cameras.append(imager.imager('imager_t' + str(i+1) + '.ini',self.base_directory))
					self.telescopes.append(cdk700.CDK700('telescope_' + str(i+1) + '.ini',self.base_directory))
					self.npss.append(powerswitch.powerswitch('powerswitch_' + str(i+1) + '.ini',self.base_directory))
				except: 
					self.logger.exception("Failed to initialize the imager on T" + str(i+1))

	def load_config(self):

		try:
			config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.logger_name = config['LOGNAME']
			self.calib_dict = config['CALIB_DICT']
			for key in self.calib_dict.keys():
                                self.calib_dict[key] = [int(x) for x in self.calib_dict[key]]
			self.observing = False
		except:
			print("ERROR accessing configuration file: " + self.config_file)
			sys.exit() 

	#? What happens here if this isn't called between 10:00AM and 4:00PM?
	#create logger object and link to log file, if night is not specified, log files will go into /log/dump directory
	def setup_logger(self):

		# reset the night at 10 am local                                                                                                 
		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
		self.night = 'n' + today.strftime('%Y%m%d')
		
		log_path = self.base_directory + '/log/' + self.night
		if os.path.exists(log_path) == False:os.mkdir(log_path)

		fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
		datefmt = "%Y-%m-%dT%H:%M:%S"

		self.logger = logging.getLogger(self.logger_name)
		self.logger.setLevel(logging.DEBUG)
		formatter = logging.Formatter(fmt,datefmt=datefmt)
		formatter.converter = time.gmtime
        
		#clear handlers before setting new ones
		self.logger.handlers = []

		fileHandler = logging.FileHandler(log_path + '/' + self.logger_name + '.log', mode='a')
		fileHandler.setFormatter(formatter)
		self.logger.addHandler(fileHandler)

		# add a separate logger for the terminal (don't display debug-level messages)
		console = logging.StreamHandler()
		console.setFormatter(formatter)
		console.setLevel(logging.INFO)
		self.logger.setLevel(logging.DEBUG)
		self.logger.addHandler(console)

		'''
		self.logger = logging.getLogger(self.logger_name)
		self.logger.setLevel(logging.DEBUG)

		fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
		datefmt = "%Y-%m-%dT%H:%M:%S"
		formatter = logging.Formatter(fmt,datefmt=datefmt)
		formatter.converter = time.gmtime
		
		#clear handlers before setting new ones
		self.logger.handlers = []
		
		fileHandler = logging.FileHandler(log_path + '/' + self.logger_name + '.log', mode='a+')
		fileHandler.setFormatter(formatter)
		self.logger.addHandler(fileHandler)
		
		streamHandler = logging.StreamHandler()
		streamHandler.setFormatter(formatter)
		self.logger.addHandler(streamHandler)
		'''

	#set logger path for all control objects
	def setup_loggers(self):
	
		self.logger_lock.acquire()
		for a in self.domes:
			a.setup_logger()
		for t in self.telescopes:
			t.setup_logger()
		for c in self.cameras:
			c.setup_logger()
		self.site.setup_logger()
		if socket.gethostname() == 'KiwiSpec':
			self.spectrograph.setup_logger()
		self.logger_lock.release()
		
	#enable sending commands to telcom
	#TODO what does this do?
	def telcom_enable(self,num=0):
		if num >= 1 and num <= len(self.telescopes):
			self.telcom_enabled[num-1] = True
		else:
			self.telcom_enabled = [True]*len(self.telescopes)
	
	#disable sending command to telcom
	def telcom_disable(self,num=0):
		if num >= 1 and num <= len(self.telescopes):
			self.telcom_enabled[num-1] = False
		else:
			self.telcom_enabled = [False]*len(self.telescopes)

	#S Hmmmmm
	def telecom_shutdown(self):
		pass
		
	def telecom_startup(self):
		pass
		
	def telecom_restart(self):
		pass

#============Dome control===============#
#block until command is complete
#operate dome specified by num arguments
#if no argument or num outside of array command all domes

	def dome_initialize(self,num):
		if num >= 1 and num <= len(self.domes):
			self.domes[num-1].initialize()
		else:
			threads = [None]*len(self.domes)
			for t in range(len(self.domes)):
				threads[t] = threading.Thread(target = self.domes[t].initialize)
				threads[t].start()
			for t in range(len(self.domes)):
				threads[t].join()
				
	def dome_open(self,num=0):
		if num >= 1 and num <= len(self.domes):
			self.domes[num-1].open_both()
		else:
			threads = [None]*len(self.domes)
			for t in range(len(self.domes)):
				threads[t] = threading.Thread(target = self.domes[t].open_both)
				threads[t].start()
			for t in range(len(self.domes)):
				threads[t].join()
		for t in self.domes:
			if t.isOpen == False:
				return False
		return True
	def dome_close(self,num=0):
		if num >= 1 and num <= len(self.domes):
			self.domes[num-1].close_both()
		else:
			threads = [None]*len(self.domes)
			for t in range(len(self.domes)):
				threads[t] = threading.Thread(target = self.domes[t].close_both)
				threads[t].start()
			for t in range(len(self.domes)):
				threads[t].join()
		return
		
#==================Telescope control==================#
#block until command is complete
#operate telescope specified by list of numbers
#if number(s) is/are not specified or outside of array range, 
#all enabled telescopes will execute command in parallel
#S I left an old version of the command to be an example of changes

#TODO What if we only create fewer than four self.cdk700 objects??
#TODO For now, saving all old versions of functions incase such an
#S instance occurs.
#=====================================================#

	#S New command format, which allows for incomplete lists of telescopes				
	def telescope_initialize(self,tele_list = 0, tracking = False):
                #S check if tele_list is only an int
                if type(tele_list) is int:
                        #S Catch to default a zero arguement or outside array range tele_list
			#S and if so make it default to controling all telescopes.
			if (tele_list < 1) or (tele_list > len(self.telescopes)):
                                #S This is a list of numbers fron 1 to the number scopes
				tele_list = [x+1 for x in range(len(self.telescopes))]
			#S If it is in the range of telescopes, we'll put in a list to 
			#S avoid accessing issues later on.
			else:
				tele_list = [tele_list]
				
                #S Zero index the tele_list
                tele_list = [x-1 for x in tele_list]
                #S The number of threads we'll have will be number of scopes
                threads = [None] * len(tele_list)
                #S So for each scope, this index is a bit tricky. We have a zero indexed reference to the
                #S the number corresponding to each scope. So this is really saying
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                kwargs={}
				kwargs['tracking']=tracking
				threads[t] = threading.Thread(target = self.telescopes[tele_list[t]].initialize,kwargs=kwargs)
                                threads[t].start()
                #S Join all the threads together
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                threads[t].join()
                return


	def telescope_autoFocus(self,tele_list = 0):
                if type(tele_list) is int:
			if (tele_list < 1) or (tele_list > len(self.telescopes)):
				tele_list = [x+1 for x in range(len(self.telescopes))]
			else:
				tele_list = [tele_list]
                tele_list = [x-1 for x in tele_list]
                threads = [None] * len(tele_list)
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                threads[t] = threading.Thread(target = self.telescopes[tele_list[t]].autoFocus)
                                threads[t].start()
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                threads[t].join()
                return

        #TODOACQUIRETARGET Needs to be switched to take dictionary arguement
	def telescope_acquireTarget(self,ra,dec,tele_list = 0):
                if type(tele_list) is int:
			if (tele_list < 1) or (tele_list > len(self.telescopes)):
				tele_list = [x+1 for x in range(len(self.telescopes))]
			else:
				tele_list = [tele_list]
                tele_list = [x-1 for x in tele_list]
                threads = [None] * len(tele_list)
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                #TODOACQUIRETARGET Needs to be switched to take dictionary arguement
                                threads[t] = threading.Thread(target = self.telescopes[tele_list[t]].acquireTarget,args=(ra,dec))
                                threads[t].start()
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                threads[t].join()
                return

	def telescope_mountGotoAltAz(self,alt,az,tele_list = 0):
                if type(tele_list) is int:
			if (tele_list < 1) or (tele_list > len(self.telescopes)):
				tele_list = [x+1 for x in range(len(self.telescopes))]
			else:
				tele_list = [tele_list]
                tele_list = [x-1 for x in tele_list]
                threads = [None] * len(tele_list)
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                threads[t] = threading.Thread(target = self.telescopes[tele_list[t]].mountGotoAltAz,args=(alt,az))
                                threads[t].start()
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                threads[t].join()
                return

	def telescope_park(self,tele_list = 0):
                if type(tele_list) is int:
			if (tele_list < 1) or (tele_list > len(self.telescopes)):
				tele_list = [x+1 for x in range(len(self.telescopes))]
			else:
				tele_list = [tele_list]
                tele_list = [x-1 for x in tele_list]
                threads = [None] * len(tele_list)
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                threads[t] = threading.Thread(target = self.telescopes[tele_list[t]].park)
                                threads[t].start()
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                threads[t].join()
                return


                
                                                               

                        
                        
	#S Old functions
	def telescope_initialize_old(self,num=0):
                #? Why is there no telecom check for the single case?
		if num >= 1 and num <= len(self.telescopes):
			self.telescopes[num-1].initialize()
		else:
			threads = [None]*len(self.telescopes)
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t] = threading.Thread(target = self.telescopes[t].initialize)
					threads[t].start()
			#? why are there two seperate loops?
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t].join()
				
	def telescope_autoFocus_old(self,num=0):
		if num >= 1 and num <= len(self.telescopes):
			self.telescopes[num-1].autoFocus()
		else:
			threads = [None]*len(self.telescopes)
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t] = threading.Thread(target = self.telescopes[t].autoFocus)
					threads[t].start()
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t].join()
					
	def telescope_acquireTarget_old(self,ra,dec,num=0):
		if num >= 1 and num <= len(self.telescopes):
			self.telescopes[num-1].acquireTarget(ra,dec)
		else:
			threads = [None]*len(self.telescopes)
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t] = threading.Thread(target = self.telescopes[t].acquireTarget,args = (ra,dec))
					threads[t].start()
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t].join()
					
	def telescope_mountGotoAltAz_old(self,Alt,Az,num=0):
		if num >= 1 and num <= len(self.telescopes):
			self.telescopes[num-1].mountGotoAltAz(Alt,Az)
		else:
			threads = [None]*len(self.telescopes)
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t] = threading.Thread(target = self.telescopes[t].mountGotoAltAz,args=(Alt,Az))
					threads[t].start()
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t].join()
					
	def telescope_park_old(self,num=0):
		if num >= 1 and num <= len(self.telescopes):
			self.telescopes[num-1].park()
		else:
			threads = [None]*len(self.telescopes)
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t] = threading.Thread(target = self.telescopes[t].park)
					threads[t].start()
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t].join()
					
#============Imager control===============#
#block until command is complete
#operate on imagre specified by num
#if num is not specified or outside of array range,
#operate all imagers.

	def imager_initialize(self,num=0):
		if num >= 1 and num <= len(self.cameras):
			self.cameras[num-1].initialize()
		else:
			threads = [None]*len(self.cameras)
			for t in range(len(self.cameras)):
				threads[t] = threading.Thread(target = self.cameras[t].initialize)
				threads[t].start()
			for t in range(len(self.cameras)):
				threads[t].join()
				
	def imager_connect(self,num=0):
		if num >= 1 and num <= len(self.cameras):
			self.cameras[num-1].connect_camera()
		else:
			threads = [None]*len(self.cameras)
			for t in range(len(self.cameras)):
				threads[t] = threading.Thread(target = self.cameras[t].connect_camera)
				threads[t].start()
			for t in range(len(self.cameras)):
				threads[t].join()
			
	def imager_setDatapath(self,night,num=0):
	
		if num >= 1 and num <= len(self.cameras):
			self.cameras[num-1].set_dataPath()
		else:
			threads = [None]*len(self.cameras)
			for t in range(len(self.cameras)):
				threads[t] = threading.Thread(target = self.cameras[t].set_dataPath)
				threads[t].start()
			for t in range(len(self.cameras)):
				threads[t].join()
				
	def imager_compressData(self,num=0):
	
		if num >= 1 and num <= len(self.cameras):
			self.cameras[num-1].compress_data()
		else:
			threads = [None]*len(self.cameras)
			for t in range(len(self.cameras)):
				threads[t] = threading.Thread(target = self.cameras[t].compress_data)
				threads[t].start()
			for t in range(len(self.cameras)):
				threads[t].join()

#======================High level stuff===========================#
#more complex operations 

	#load calibration file
	def loadCalibInfo(self,num):

		telescope_name = 'T' + str(num) +': '

		file = self.site.night + '.T' + str(num) + '.txt'
		self.logger.info(telescope_name + 'loading calib file: ' + file)
		try:
			with open(self.base_directory + '/schedule/' + file, 'r') as calibfile:
				calibline = calibfile.readline()
				calibendline = calibfile.readline()
			
				calibinfo = json.loads(calibline)
				calibendinfo = json.loads(calibendline)
				self.logger.info(telescope_name + 'calib info loaded: ' + self.site.night + '.T' + str(num) + '.txt')
				return [calibinfo,calibendinfo]
		except:
			self.logger.info(telescope_name + 'error loading calib info: ' + self.site.night + '.T' + str(num) + '.txt')
			sys.exit()
		
	# check weather condition; close if bad, open and send heartbeat if good; update dome status
	def domeControl(self):
		while self.observing:
			t0 = datetime.datetime.utcnow()

			if not self.site.oktoopen(open=self.domes[0].isOpen):
				if self.site.sunalt() < 0.0:
					self.logger.info('Weather not ok to open; resetting timeout')
					self.site.lastClose = datetime.datetime.utcnow()
					self.dome_close()
			elif (datetime.datetime.utcnow() - self.site.lastClose).total_seconds() < (20.0*60.0):
				self.logger.info('Conditions must be favorable for 20 minutes before opening; last bad weather at ' + str(self.site.lastClose))
				self.dome_close() # should already be closed, but for good measure...
			else:
				self.logger.debug('Weather is good; opening dome')				
				openthread = threading.Thread(target=self.dome_open)
				openthread.start()

				# only send heartbeats when it's ok to open
				for i in range(len(self.domes)):
					self.domes[i].heartbeat()

			# does this create a problem if domes[*].isOpen changes as other threads access it?
			for i in range(len(self.domes)):
				status = self.domes[i].status()
				if status['Shutter1'] == 'OPEN' and status['Shutter2'] == 'OPEN': self.domes[i].isOpen = True
				else: self.domes[i].isOpen = False

			# ensure 4 hearbeats before timeout
			sleeptime = max(14.0-(datetime.datetime.utcnow() - t0).total_seconds(),0)
			time.sleep(sleeptime)
		self.dome_close()
		
	def domeControlThread(self):
		self.observing = True
		threading.Thread(target = self.domeControl).start()

	def ten(self,string):
		array = string.split()
		if "-" in array[0]:
			return float(array[0]) - float(array[1])/60.0 - float(array[2])/3600.0
		return float(array[0]) + float(array[1])/60.0 + float(array[2])/3600.0

	def astrometry(self,imageName):

		hdr = pyfits.getheader(imageName)
		try: pixscale = float(hdr['PIXSCALE'])
		except: pixscale = 0.61
		
		try: ra = float(hdr['RA'])
		except: ra = self.ten(hdr['RA'])*15.0
    
		try: dec = float(hdr['DEC'])
		except: dec = self.ten(hdr['DEC'])
		if dec > 90.0: dec = dec - 360.0

		radius = 3.0*pixscale*float(hdr['NAXIS1'])/3600.0

		cmd = 'solve-field --scale-units arcsecperpix' + \
		    ' --scale-low ' + str(0.99*pixscale) + \
		    ' --scale-high ' + str(1.01*pixscale) + \
		    ' --ra ' + str(ra) + \
		    ' --dec ' + str(dec) + \
		    ' --radius ' + str(radius) +\
		    ' --quad-size-min 0.4' + \
		    ' --quad-size-max 0.6' + \
		    ' --cpulimit 600' + \
		    ' --no-verify' + \
		    ' --crpix-center' + \
		    ' --no-fits2fits' + \
		    ' --no-plots' + \
		    ' --overwrite ' + \
		    imageName
#		' --use-sextractor' + \ #need to install sextractor

		cmd = r'/usr/local/astrometry/bin/' + cmd + ' >/dev/null 2>&1' 
		os.system(cmd)

	def getPA(self,imageName, email=True):

		telescope_name = 'T' + os.path.splitext(imageName)[0].split('.')[1][1] + ': '
		
		self.logger.info(telescope_name + 'Finding PA for ' + imageName)
		self.astrometry(imageName)
		
		baseName = os.path.splitext(imageName)[0]
		f = pyfits.open(imageName, mode='update')
		if os.path.exists(baseName + '.new'):

			
			self.logger.info(telescope_name + 'Astrometry successful for ' + imageName)

			# is it close to what we thought?
			orighdr = pyfits.getheader(imageName)
			origcd11 = float(f[0].header['CD1_1'])
			origcd12 = float(f[0].header['CD1_2'])
			origPA = 180.0/math.pi*math.atan2(origcd12,-origcd11)
			origracen = float(f[0].header['CRVAL1'])*math.pi/180.0
			origdeccen = float(f[0].header['CRVAL2'])*math.pi/180.0

			f[0].header['WCSSOLVE'] = 'True'
			PA = None

			# copy the WCS solution to the file
			newhdr = pyfits.getheader(baseName + '.new')
			f[0].header['WCSAXES'] = newhdr['WCSAXES']
			f[0].header['CTYPE1'] = newhdr['CTYPE1']
			f[0].header['CTYPE2'] = newhdr['CTYPE2']
			f[0].header['EQUINOX'] = newhdr['EQUINOX']
			f[0].header['LONPOLE'] = newhdr['LONPOLE']
			f[0].header['LATPOLE'] = newhdr['LATPOLE']
			f[0].header['CRVAL1'] = newhdr['CRVAL1']
			f[0].header['CRVAL2'] = newhdr['CRVAL2']
			f[0].header['CRPIX1'] = newhdr['CRPIX1']
			f[0].header['CRPIX2'] = newhdr['CRPIX2']
			f[0].header['CUNIT1'] = newhdr['CUNIT1']
			f[0].header['CUNIT2'] = newhdr['CUNIT2']
			f[0].header['CD1_1'] = newhdr['CD1_1']
			f[0].header['CD1_2'] = newhdr['CD1_2']
			f[0].header['CD2_1'] = newhdr['CD2_1']
			f[0].header['CD2_2'] = newhdr['CD2_2']
			f[0].header['IMAGEW'] = newhdr['IMAGEW']
			f[0].header['IMAGEH'] = newhdr['IMAGEH']
			f[0].header['A_ORDER'] = newhdr['A_ORDER']
			f[0].header['A_0_2'] = newhdr['A_0_2']
			f[0].header['A_1_1'] = newhdr['A_1_1']
			f[0].header['A_2_0'] = newhdr['A_2_0']
			f[0].header['B_ORDER'] = newhdr['B_ORDER']
			f[0].header['B_0_2'] = newhdr['B_0_2']
			f[0].header['B_1_1'] = newhdr['B_1_1']
			f[0].header['B_2_0'] = newhdr['B_2_0']
			f[0].header['AP_ORDER'] = newhdr['AP_ORDER']			
			f[0].header['AP_0_1'] = newhdr['AP_0_1']
			f[0].header['AP_0_2'] = newhdr['AP_0_2']
			f[0].header['AP_1_0'] = newhdr['AP_1_0']
			f[0].header['AP_1_1'] = newhdr['AP_1_1']
			f[0].header['AP_2_0'] = newhdr['AP_2_0']
			f[0].header['BP_ORDER'] = newhdr['BP_ORDER']
			f[0].header['BP_0_1'] = newhdr['BP_0_1']
			f[0].header['BP_0_2'] = newhdr['BP_0_2']
			f[0].header['BP_1_0'] = newhdr['BP_1_0']
			f[0].header['BP_1_1'] = newhdr['BP_1_1']
			f[0].header['BP_2_0'] = newhdr['BP_2_0']
			
			cd11 = float(newhdr['CD1_1'])
			cd12 = float(newhdr['CD1_2'])
			racen = float(newhdr['CRVAL1'])*math.pi/180.0
			deccen = float(newhdr['CRVAL2'])*math.pi/180.0       
			#PA = 180.0/math.pi*math.atan2(-cd12,-cd11) # this one?
			PA = 180.0/math.pi*math.atan2(cd12,-cd11) # or this one?
			
			dPA = 180.0/math.pi*math.atan2(math.sin((PA-origPA)*math.pi/180.0), math.cos((PA-origPA)*math.pi/180.0))
			dRA = 648000.0/math.pi*(racen-origracen)/math.cos(deccen)
			dDec = 648000.0/math.pi*(deccen-origdeccen)
			dtheta = 648000.0/math.pi*math.acos(math.sin(deccen)*math.sin(origdeccen) + math.cos(deccen)*math.cos(origdeccen)*math.cos(racen-origracen))
			self.logger.info(telescope_name + "Telescope PA = " + str(origPA) + '; solved PA = ' + str(PA) + '; offset = ' + str(dPA) + ' degrees')
			self.logger.info(telescope_name + "Telescope RA = " + str(origracen) + '; solved RA = ' + str(racen) + '; offset = ' + str(dRA) + ' arcsec')
			self.logger.info(telescope_name + "Telescope Dec = " + str(origdeccen) + '; solved Dec = ' + str(deccen) + '; offset = ' + str(dDec) + ' arcsec')
			self.logger.info(telescope_name + "Total pointing error = " + str(dtheta) + ' arcsec')
			
			telname = f[0].header['TELESCOP']
			guideFile = "disableGuiding." + telname + ".txt"
			if abs(dPA) > 5:
				self.logger.error(telescope_name + "PA out of range")
				if not os.path.exists(guideFile):
					with open(guideFile,"w") as fh:
						fh.write(str(datetime.datetime.utcnow()))
					if email:
						body = "Dear benevolent humans,\n\n" + \
						    "The PA error (" + str(dPA) + " deg) is too large for " + imageName + ". " + \
						    "I have disabled the guiding, but I require your assistance to re-home the rotator. Please:\n\n" + \
						    "1) In the PWI rotate tab, make sure the 'alt az derotate' box is unchecked\n" + \
						    "2) Click home in the 'comands' pull down menu\n" + \
						    "3) Wait for it to complete and move back to 359.0\n" + \
						    "4) If it stalls, press stop and start the procedure over again (it'll go faster this time)\n" + \
						    "5) Delete 'minerva-control/" + guideFile + "\n\n" + \
						    "Love,\n" + \
						    "MINERVA"
						mail.send("PA error too large",body,level='serious')
			else:
				if os.path.exists(guideFile):
					self.logger.error(telescope_name + "PA in range, re-enabling guiding")
					os.remove(guideFile)
					if email:
						body = "Dear benevolent humans,\n\n" + \
						    "The PA error is within range again. Re-enabling guiding.\n\n" + \
						    "Love,\n" + \
						    "MINERVA"
						mail.send("PA error fixed",body,level='serious')
					                            
			if dtheta > 600:
				body =  "Dear benevolent humans,\n\n" + \
				    "My pointing error (" + str(dtheta) + " arcsec) is too large for " + imageName + ". " + \
				    "A new pointing model must be created. Please:\n\n" + \
				    "1) Power up the telescope and enable the axes\n" + \
				    "2) From the Commands menu under the Mount tab, click Edit Location and verify that the latitude and longitude are correct\n" + \
				    "3) Go to http://time.is/ and make sure the computer clock is correct\n" + \
				    "4) From the Commands menu, home the telescope\n" + \
				    "5) From the Commands menu, Remove all cal points (to delete the old mount model)\n" + \
				    "6) In the Mount tab, scroll down to Auto Mount and click the 'START' button next to Auto Mount\n" + \
				    "7) When complete, from the Commands menu, click 'Save Model as Default'\n" + \
				    "8) From the Commands menu, click 'Calibrate Home Sensors'\n\n" + \
				    "Love,\n" + \
				    "MINERVA"
				
				try: self.logger.error(telescope_name + "Pointing error too large")
				except: pass
				if email: mail.send("Pointing error too large",body,level='serious')

		else:
			# insert keyword to indicated WCS failed
			f[0].header['WCSSOLVE'] = 'False'
			PA = None

		# if we add too many header cards, we can't save in place and we get a permision denied error
		f.flush()
		f.close()

		# clean up extra files
		extstodelete = ['-indx.png','-indx.xyls','-ngc.png','-objs.png','.axy','.corr','.match','.new','.rdls','.solved','.wcs']
		for ext in extstodelete:
			if os.path.exists(baseName + ext):
				os.remove(baseName + ext)
				
		return PA

	def getstars(self,imageName):
    
		d = getfitsdata(imageName)
		th = threshold_pyguide(d, level = 4)

		if np.max(d*th) == 0.0:
			return np.zeros((1,3))
    
		imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
		cc = centroid_all_blobs(imtofeed)

		return cc

	def guide(self,filename, reference):

		threshhold = 60.0 # maximum offset in X or Y (larger corrections will be ignored)
		maxangle = 5.0 # maximum offset in theta (larger corrections will be ignored)

		# which telescope is this?
		match = False
		for telescope in self.telescopes:
			if telescope.logger_name.split('_')[-1] == filename.split('.')[1][1]:
				match = True
				break
		if not match: 
			self.logger.error("Could not match filename to telescope name: filename=" + filename)
			return

		num = telescope.logger_name.split('_')[-1]
		telname = "T" + num
		
		telescope_name = 'T' + str(num) +': '


		if os.path.exists("disableGuiding." + telname + ".txt"):
			self.logger.info(telescope_name + "Guiding disabled")
			return None

		if reference == None:
			self.logger.info(telescope_name + "No reference frame defined yet; using " + filename)
			reference = self.getstars(filename)
			if len(reference[:,0]) < 6:
				self.logger.error(telescope_name + "Not enough stars in reference frame")
				return None
			return reference

		self.logger.info(telescope_name + "Extracting stars for " + filename)
		stars = self.getstars(filename)
		if len(stars[:,0]) < 6:
			self.logger.error(telescope_name + "Not enough stars in frame")
			return reference

		# proportional servo gain (apply this fraction of the offset)
		gain = 0.66

		# get the platescale from the header
		hdr = pyfits.getheader(filename)
		platescale = float(hdr['PIXSCALE'])
		dec = float(hdr['CRVAL2'])*math.pi/180.0 # declination in radians

		arg = max(min(-float(hdr['CD1_1'])*3600.0/platescale,1.0),-1.0)
		PA = math.acos(arg) # position angle in radians
		self.logger.info(telescope_name + "Image PA=" + str(PA))

		m0 = 22
		x = stars[:,0]
		y = stars[:,1]
		mag = -2.5*np.log10(stars[:,2])+m0
		
		xref = reference[:,0]
		yref = reference[:,1]
		magref = -2.5*np.log10(reference[:,2])+m0

		self.logger.info(telescope_name + "Getting offset for " + filename)
		dx,dy,scale,rot,flag,rmsf,nstf = self.findoffset(x, y, mag, xref, yref, magref)

		self.logger.info(telescope_name + "dx=" + str(dx) + ", dy=" + str(dy) + ", scale=" + str(scale) +
			    ", rot=" + str(rot) + ", flag=" + str(flag) +
			    ", rmsf=" + str(rmsf) + ", nstf=" + str(nstf))
    
		if abs(dx) > threshhold or abs(dy) > threshhold or abs(rot) > maxangle:
			self.logger.error(telescope_name + "Offset too large; ignoring")
			return reference

		# adjust the rotator angle (sign?)
		self.logger.info(telescope_name + "Adjusting the rotator by " + str(rot*gain) + " degrees")
		telescope.rotatorIncrement(rot*gain)

		# adjust RA/Dec (need to calibrate PA)
		deltaRA = -(dx*math.cos(PA) - dy*math.sin(PA))*math.cos(dec)*platescale*gain
		deltaDec = (dx*math.sin(PA) + dy*math.cos(PA))*platescale*gain
		self.logger.info(telescope_name + "Adjusting the RA,Dec by " + str(deltaRA) + "," + str(deltaDec))
		telescope.mountOffsetRaDec(deltaRA,deltaDec)

		# correction sent
		telescope.rotatorMailsent=False

		return reference

	# finds the offset (x, y, theta) between two star lists)
	def findoffset(self, x, y, mag, xref, yref, magref):

		MAXSTARS = 50 # only consider MAXSTARS brightest stars
		thet=0.0 # thet +/- dthet (deg)
		dthet=3.0 # maximum allowed rotation between images (deg)
		
		# allowed change in scale from image to image
		scl = 0.0 # 1 + scl +/- dscl
		dscl = 0.01

		# size of the image (should be dynamic)
		# actually, twice the center pixel of the rotator
		naxis1 = 2048
		naxis2 = 2048

		maxstars = min(MAXSTARS,len(xref))
		sortndx = np.argsort(magref)
       
		xreftrunc = xref[sortndx[0:maxstars]]
		yreftrunc = yref[sortndx[0:maxstars]]
		magreftrunc = magref[sortndx[0:maxstars]]
		lindx1,lparm1 = segments.listseg(xreftrunc, yreftrunc, magreftrunc)

		maxstars = min(MAXSTARS,len(x))
		
		sortndx = np.argsort(mag)
		xtrunc = x[sortndx[0:maxstars]]
		ytrunc = y[sortndx[0:maxstars]]
		magtrunc = mag[sortndx[0:maxstars]]
		lindx2,lparm2 = segments.listseg(xtrunc, ytrunc, magtrunc)
    
		# magic
		dx,dy,scale,rot,mat,flag,rmsf,nstf = \
		    segments.fitlists4(naxis1,naxis2,lindx1,lparm1,lindx2,lparm2,\
					       xreftrunc,yreftrunc,xtrunc,ytrunc,scl,dscl,thet,dthet)

		return dx,dy,scale,rot,flag,rmsf,nstf

        ###
	# EXPOSURES
	###

        #S A function to put moving the i2stage in it's own thread, which will check status of the stage,
	#S run trouble shooting, and ultimately handle the timeout.
        def ctrl_i2stage_move(self,locationstr = 'out'):
                #S Sends command to begin i2stage movement, whcih will start
                #S a thread in the spectrograph server to move the stage to the
                #S corresponding location string.
                self.spectrograph.i2stage_move(locationstr)
                #S Time out to wait for the stage to get to destination.
                timeout  = 60
                #S Start time to measure elapsed time of movement.
                start = datetime.datetime.utcnow()
                #S Just priming elapsed time for first time through 'while'
                elapsed_time = 0
                #S If we aren't at our target string AND elapsed time is less than the timeout.
                #S Note that this queries the position string, and compares to the requested. 
                while (self.spectrograph.i2stage_get_pos()[1] <> locationstr) and (elapsed_time < timeout):
                        #S Giver her a second
                        time.sleep(1)
                        #S Update elapsed time
                        elapsed_time = (datetime.datetime.utcnow() - start).total_seconds()
                #S We exited the 'while' above, meaning one of the conditions became false.
                #S If the target string is our current string, we made it where we want to go. 
                if self.spectrograph.i2stage_get_pos()[1] == locationstr:
                        #S Log some info dog
                        self.logger.info('I2 stage successfully moved to '+locationstr+' after first attempt.')
                        #S Returns nothing right now, and i think that's all we want.
                        return
                #S If we get here, the timeout was surpassed, and we need to try some troubleshooting.
                #S Our first action will be to send the move command again. no harm here.
                #S First, we'l log an error saying we're trying again.
                self.logger.error('I2 stage did not make it to destination, trying to move again')
                #S Tell it to move
                self.spectrograph.i2stage_move(locationstr)
                #S Reset start and elapsed time. This uses same logic above.
                start = datetime.datetime.utcnow()
                elapsed_time = 0
                while (self.spectrograph.i2stage_get_pos()[1] <> locationstr) and (elapsed_time < timeout):
                        time.sleep(1)
                        elapsed_time = (datetime.datetime.utcnow() - start).total_seconds()
                        
                if self.spectrograph.i2stage_get_pos()[1] == locationstr:
                        self.logger.info('I2 stage successfully moved to '+locationstr+' after second attempt.')
                        return
                self.logger.error('I2 stage did not move to destination, cycling power then trying again')
                #S This is a little unituitive. We first disconnect. Then we reconnect. The unintuitive part is
                #S that there is also a power cycle hidden in there. The way that PYAPT works, if there is ever a problem
                #S with disconnecting to an APT device (e.g. not cleaned up), it crashes python.exe from a .dll command , BUT a power cycle
                #S cleans this up. That's why a powercycle is hidden in here. So effectively, this is a power cycle. There is also
                #S some sleep time hidden here (~seconds) to give the stage some time to start up. 
                self.spectrograph.i2stage_disconnect()
                self.spectrograph.i2stage_connect()
                #S Same logic as above.
                self.spectrograph.i2stage_move(locationstr)
                start = datetime.datetime.utcnow()
                elapsed_time = 0
                while (self.spectrograph.i2stage_get_pos()[1] <> locationstr) and (elapsed_time < timeout):
                        time.sleep(1)
                        elapsed_time = (datetime.datetime.utcnow() - start).total_seconds()
                if self.spectrograph.i2stage_get_pos()[1] == locationstr:
                        self.logger.info('I2 stage successfully moved to '+locationstr+' after third attempt.')
                        return
                #S Exhausted all known solutions so far, so let's send an email.
                self.logger.error("I2 stage did not move to destination after three attempts, sending email.")
                body = 'Dear humans,\n\n'\
                       'For some reason I cannot move my i2stage. I have tried moving it again. I even tried power cycling THEN moving it again. Something weird went '\
                       'wrong, and I could be stuck. Please investigate. \n\n'\
                       'Love,\nMINERVA'
                       
                mail.send("The iodine stage is not moving.",body,level='serious')
                
                        
        #S Here is the general spectrograph equipment check function.
	#S Somethings, like turning lamps on, need to be called before. More
	#S to develop on this
	#TODO TODO
        def spec_equipment_check(self,objname,filterwheel=None,template = False):
                #S Desired warmup time for lamps, in minutes
                #? Do we want seperate times for each lamp, both need to warm for the same rightnow
                WARMUPMINUTES = .5#10.
                #S Convert to lowercase, just in case.
                objname = objname.lower()
                #S Some logic to see what type of spectrum we'll be taking.

                #S Decided it would be best to include a saftey to make sure the lamps
                #S were turned on.
                #S LAMPS NEED TO BE SHUT DOWN MANUALLY THOUGH.
                if (objname == 'arc'):
                        self.spectrograph.thar_turn_on()
                if (objname == 'flat'):
                        self.spectrograph.flat_turn_on()
                
                #S These factors are necessary for all types of exposures,
                #S so we'll put them in the equipment check

                #TODO Thermocube within 0.2C?
                #TODO Configure the camera
                #TODO Thermal enclosure with 0.1C?
                #TODO Camera with in 0.1C?
                #TODO How is the vacuum?

                #S For ThAr exposures, we'll need the lamp on for at least ten
                #S minutes prior. This init only checks whether the lamp has been on
                #S for that long. We could have it default to turn on the lamp,
                #S but for now it doesn't.
                if (objname == 'arc'):
                        #S Move the I2 stage out of the way of the slit.
                        i2stage_move_thread = threading.Thread(target = self.ctrl_i2stage_move,args=('out',))
                        i2stage_move_thread.start()
                        
                        #self.spectrograph.i2stage_move('out')
                        #S Ensure that the flat lamp is off
                        self.spectrograph.flat_turn_off()
                        #S Move filter wheel where we want it.
                        #TODO A move filterwheel function
                        #S Make sure the calibration shutter is open
                        #TODO Calibrtoin shutter open.
                        #S Time left for warm up
                        warm_time = WARMUPMINUTES*60. - self.spectrograph.time_tracker_check(self.spectrograph.thar_file)
                        print '\t\t\t\tWARM TIME IS '+str(warm_time)
                        #S Determine if the lamp has been on long enough, or sleep until it has.
                        if (warm_time > 0.):
                                time.sleep(warm_time)
                                print 'Sleeping for '+str(warm_time) + ' for '+objname+' lamp.'
                        else:
                                time.sleep(0)
                        self.logger.info('Waiting on i2stage_move_thread')
                        i2stage_move_thread.join()
                            
                #S Flat exposures require the flat lamp to be on for ten minutes too.
                #S Same questions as for thar specs.
                elif (objname == 'flat'):
                        #S Move the I2 stage out of the way of the slit.
                        i2stage_move_thread = threading.Thread(target = self.ctrl_i2stage_move,args=('flat',))
                        i2stage_move_thread.start()
                        #self.spectrograph.i2stage_move('flat')
                        #S Ensure that the thar lamp is off
                        self.spectrograph.thar_turn_off()
                        
                                
                        #S Move filter wheel where we want it.
                        #TODO A move filterwheel function
                        #S Make sure the calibration shutter is open
                        #TODO Calibrtoin shutter open.

                        #S Time left for warm up
                        warm_time = WARMUPMINUTES*60. - self.spectrograph.time_tracker_check(self.spectrograph.flat_file)
                        print '\t\t\t\t WARM TIME IS '+str(warm_time)
                        #S Make sure the lamp has been on long enough, or sleep until it has.
                        if (warm_time > 0):
                                time.sleep(warm_time)
                                print 'Sleeping for '+str(warm_time) + ' for '+objname+' lamp.'
                        else:
                                time.sleep(0)
                        self.logger.info('Waiting on i2stage_move_thread')
                        i2stage_move_thread.join()

                #S Conditions for both bias and dark.
                elif (objname == 'bias') or (objname == 'dark'):
                        #S Make sure the lamps are off
                        self.spectrograph.thar_turn_off()
                        self.spectrograph.flat_turn_off()
                        #S Make sure the calibrations shutter is closed.
                        #S Move the I2 stage out of the way of the slit.
                        #S Not sure if we need to move it out necessarily, but I think
                        #S this is better than having it randomly in 'flat' or 'in',
                        #S and will at least make things orderly.
                        i2stage_move_thread = threading.Thread(target = self.ctrl_i2stage_move,args=('out',))
                        i2stage_move_thread.start()
                        #TODO Calibration shutter closed
                        self.logger.info('Waiting on i2stage_move_thread')
                        i2stage_move_thread.join()


                #S Conditions for template images, just in case we need them might
                #S as well have it programmed in.
                elif template:
                        #S Get that iodine out of my face!
                        i2stage_move_thread = threading.Thread(target = self.ctrl_i2stage_move,args=('out',))
                        i2stage_move_thread.start()
                        #S Make sure the lamps are off
                        self.spectrograph.thar_turn_off()
                        self.spectrograph.flat_turn_off()
                        #S Make sure the calibrations shutter is closed.
                        #TODO Calibration shutter closed
                        self.logger.info('Waiting on i2stage_move_thread')
                        i2stage_move_thread.join()

                #S Let's do some science!
                #S The cell heater should be turned on before starting this, to give
                #S it time to warm up. It should really be turned on at the beginning
                #S of the night, but just a reminder.
                else :
                        #S Define the temperature tolerance
                        self.spectrograph.cell_heater_on()
                        #TODO Find a better cellheater temptolerance.
                        TEMPTOLERANCE = 0.501
                        #S Here we need the i2stage in
                        i2stage_move_thread = threading.Thread(target = self.ctrl_i2stage_move,args=('in',))
                        i2stage_move_thread.start()
                        #S Make sure the lamps are off
                        self.spectrograph.thar_turn_off()
                        self.spectrograph.flat_turn_off()
                        #S Let's query the cellheater's setpoint for checks onthe temperature
                        
                        self.spectrograph.cell_heater_set_temp(55.00)
                        set_temp = self.spectrograph.cell_heater_get_set_temp()
                        #S This loop is a hold for the cell heater to be within a set tolerance
                        #S for the iodine stage's temperature. The least sigfig returned from the
                        #S heater is actually tenthes, so this may be a little tight ofa restriction.
                        #TODO revise tolerance of heater temp?
                        while (abs(set_temp - self.spectrograph.cell_heater_temp()) > TEMPTOLERANCE):
                                #S Give her some time to get there.
                                time.sleep(1)
                                #TODO We should track iterations, throw after a certain amount.
                                #TODO Do a timeout, myimager.py for example for image cooler to work
                                #TODO Error
               
                        
                        self.logger.info('Waiting on i2stage_move_thread')
                        i2stage_move_thread.join()       

                        

                self.logger.info('Equipment check passed, continuing with '+objname+' exposure.')
                return
                        
                                
                        
                        
                        
                                

	
	
        def takeSpectrum(self,exptime,objname,template=False, expmeter=None,filterwheel=None):
                #S This is a check to ensure that everything is where/how it's supposed to be
                #S based on objname.
                self.spec_equipment_check(objname)
                #start imaging process in a different thread
                kwargs = {'expmeter':expmeter}
		imaging_thread = threading.Thread(target = self.spectrograph.take_image, args = (exptime, objname), kwargs=kwargs)
		imaging_thread.start()
                        
                # Get status info for headers while exposing/reading out
                # (needs error handling)
                while self.site.getWeather() == -1: pass

                #S Get facts about the moon, used for avoidance later I'm assuming.
                moonpos = self.site.moonpos()
                moonra = moonpos[0]
                moondec = moonpos[1]
                moonphase = self.site.moonphase()

                #S Path for good stuff online
                gitPath = "C:/Users/Kiwispec/AppData/Local/GitHub/PortableGit_c2ba306e536fdf878271f7fe636a147ff37326ad/bin/git.exe"
                gitNum = subprocess.check_output([gitPath, "rev-list", "HEAD", "--count"]).strip()

                # emulate MaximDL header for consistency
		f = collections.OrderedDict()


                #S I'm guessing this is the dictionary definition for the header.
		
#                f['SIMPLE'] = 'True'
#                f['BITPIX'] = (16,'8 unsigned int, 16 & 32 int, -32 & -64 real')
#                f['NAXIS'] = (2,'number of axes')
#                f['NAXIS1'] = (0,'Length of Axis 1 (Columns)')
#                f['NAXIS2'] = (0,'Length of Axis 2 (Rows)')
#                f['BSCALE'] = (1,'physical = BZERO + BSCALE*array_value')
#                f['BZERO'] = (0,'physical = BZERO + BSCALE*array_value')
#                f['DATE-OBS'] = ("","UTC at exposure start")
                f['EXPTIME'] = ("","Exposure time in seconds")                  # PARAM24/1000
#                f['EXPSTOP'] = ("","UTC at exposure end")
                f['SET-TEMP'] = ("",'CCD temperature setpoint in C')            # PARAM62 (in comments!)
                f['CCD-TEMP'] = ("",'CCD temperature at start of exposure in C')# PARAM0
                f['BACKTEMP'] = ("","Backplace Temperature in C")               # PARAM1
                f['XPIXSZ'] = ("",'Pixel Width in microns (after binning)')
                f['YPIXSZ'] = ("",'Pixel Height in microns (after binning)')
                f['XBINNING'] = ("","Binning factor in width")                  # PARAM18
                f['YBINNING'] = ("","Binning factor in height")                 # PARAM22
                f['XORGSUBF'] = (0,'Subframe X position in binned pixels')      # PARAM16
                f['YORGSUBF'] = (0,'Subframe Y position in binned pixels')      # PARAM20
                f['IMAGETYP'] = ("",'Type of image')
                f['SITELAT'] = (str(self.site.obs.lat),"Site Latitude")
                f['SITELONG'] = (str(self.site.obs.lon),"East Longitude of the imaging location")
                f['SITEALT'] = (self.site.obs.elevation,"Site Altitude (m)")
                f['JD'] = (0.0,"Julian Date at the start of exposure")
                f['FOCALLEN'] = (4560.0,"Focal length of the telescope in mm")
                f['APTDIA'] = ("700","")
                f['APTAREA'] = ("490000","")
                f['SWCREATE'] = ("SI2479E 2011-12-02","Name of the software that created the image")
                f['INSTRUME'] = ('KiwiSpec','Name of the instrument')
                f['OBSERVER'] = ('MINERVA Robot',"Observer")
                f['SHUTTER'] = ("","Shuter Status")             # PARAM8
                f['XIRQA'] = ("",'XIRQA status')                # PARAM9
                f['COOLER'] = ("","Cooler Status")              # PARAM10
                f['CONCLEAR'] = ("","Continuous Clear")         # PARAM25
                f['DSISAMP'] = ("","DSI Sample Time")           # PARAM26
                f['ANLGATT'] = ("","Analog Attenuation")        # PARAM27
                f['PORT1OFF'] = ("","Port 1 Offset")            # PARAM28
                f['PORT2OFF'] = ("","Port 2 Offset")            # PARAM29
                f['TDIDELAY'] = ("","TDI Delay,us")             # PARAM32
                f['CMDTRIG'] = ("","Command on Trigger")        # PARAM39
                f['ADCOFF1'] = ("","Port 1 ADC Offset")         # PARAM44
                f['ADCOFF2'] = ("","Port 2 ADC Offset")         # PARAM45
                f['MODEL'] = ("","Instrument Model")            # PARAM48
                f['SN'] = ("","Instrument SN")                  # PARAM49
                f['HWREV'] = ("","Hardware Revision")           # PARAM50
                f['SERIALP'] =("","Serial Phasing")             # PARAM51
                f['SERIALSP'] = ("","Serial Split")             # PARAM52
                f['SERIALS'] = ("","Serial Size,Pixels")        # PARAM53
                f['PARALP'] = ("","Parallel Phasing")           # PARAM54
                f['PARALSP'] = ("","Parallel Split")            # PARAM55
                f['PARALS'] = ("","Parallel Size,Pixels")       # PARAM56
                f['PARDLY'] = ("","Parallel Shift Delay, ns")   # PARAM57
                f['NPORTS'] = ("","Number of Ports")            # PARAM58
                f['SHUTDLY'] = ("","Shutter Close Delay, ms")   # PARAM59
                f['ROBOVER'] = (gitNum,"Git commit number for robotic control software")
                f['MOONRA'] = (moonra,"Moon RA (J2000)")
                f['MOONDEC'] = (moondec,"Moon DEC (J2000)")
                f['MOONPHAS'] = (moonphase, "Moon Phase (Fraction)")
                                        
        #PARAM60 =                   74 / CCD Temp. Setpoint Offset,0.1 C               
        #PARAM61 =               1730.0 / Low Temp Limit,(-100.0 C)                      
        #PARAM62 =               1830.0 / CCD Temperature Setpoint,(-90.0 C)             
        #PARAM63 =               1880.0 / Operational Temp,(-85.0 C)                     
        #PARAM65 =                    0 / Port Select,(A)                                
        #PARAM73 =                    0 / Acquisition Mode,(Normal)                      
        #PARAM76 =                    0 / UART 100 byte Ack,(Off)                        
        #PARAM79 =                  900 / Pixel Clear,ns                                 
        #COMMENT  Temperature is above set limit, Light Exposure, Exp Time= 10, Saved as:
        #COMMENT   overscan.FIT                                
                                     
                                         
                # need object for each telescope

                # loop over each telescope and insert the appropriate keywords
                for telescope in self.telescopes:
                    #? What? What is this concat?
                    telescop += telescope.name
                    #S the telescope number, striped of the chararray that is the string telescope.name[-1]
                    #S Not wure where self.telescope[x].name comes from though. Not in config files that I can find.
                    telnum = telescope.name[-1]
                    #S Getting this mysterious status dict (I believe).
                    telescopeStatus = telescope.getStatus()
                    #S The telescopes current ra.
                    #S NOTE: telescopestatus.mount.ra_2000 in hours. 
                    telra = ten(telescopeStatus.mount.ra_2000)*15.0
                    #S Telescopes mounts current dec from status
                    teldec = ten(telescopeStatus.mount.dec_2000)
                    #S The targets current ra, hours again
                    ra = ten(telescopeStatus.mount.ra_target)*15.0
                    #S the targets dec, degrees
                    dec = ten(telescopeStatus.mount.dec_target)
                    #S Fixes an unforetold but legendary bug in PWI. You probably have heard about it. Wait, you haven't?! Get with the picture, dammit!
                    #S My guess is that PWI will return a wrap arund for declination sometimes. 
                    if dec > 90.0: dec = dec-360 # fixes bug in PWI
                    #S Fill out header information based on each telescope.
                    f['TELRA' + telnum] = (telra,"Telescope RA (J2000 deg)")
                    f['TELDEC' + telnum] = (teldec,"Telescope Dec (J2000 deg)")
                    f['RA' + telnum] = (ra, "Target RA (J2000 deg)")
                    f['DEC'+ telnum] = (dec,"Target Dec (J2000 deg)")
                    #S Get that moon seperation, put in in a header
                    moonsep = ephem.separation((telra*math.pi/180.0,teldec*math.pi/180.0),moonpos)*180.0/math.pi
                    f['MOONDIS' + telnum] = (moonsep, "Distance between pointing and moon (deg)")
                    #TODO Now this, where are we storing pointing model? How is it set?
                    #TODO Obviously it's in status, but where does status get it? Is it just
                    #TODO not on this computer?
                    f['PMODEL' + telnum] = (telescopeStatus.mount.pointing_model,"Pointing Model File")
                    #S Focus stuff
                    f['FOCPOS' + telnum] = (telescopeStatus.focuser.position,"Focus Position (microns)")
                    #S Rotator stuff, only needed for photometry?
                    f['ROTPOS' + telnum] = (telescopeStatus.rotator.position,"Rotator Position (degrees)")
                    #S So we do have access to port info, keep this in mind!!!
                    #SNOTE 
                    # M3 Specific
                    f['PORT' + telnum] = (telescopeStatus.m3.port,"Selected port for " + telescope.name)
                    #S Ahh, the otafan. Obtuse telescope ass fan, obviously.
                    f['OTAFAN' + telnum] = (telescopeStatus.fans.on,"OTA Fans on?")
                    #S Get mirror temps
                    try: m1temp = telescopeStatus.temperature.primary
                    except: m1temp = 'UNKNOWN'
                    f['M1TEMP'+telnum] = (m1temp,"Primary Mirror Temp (C)")

                    try: m2temp = telescopeStatus.temperature.secondary
                    except: m2temp = 'UNKNOWN'
                    f['M2TEMP'+telnum] = (m2temp,"Secondary Mirror Temp (C)")

                    try: m3temp = telescopeStatus.temperature.m3
                    except: m3temp = 'UNKNOWN'
                    f['M3TEMP'+telnum] = (m3temp,"Tertiary Mirror Temp (C)")
                    #S Outside temp
                    try: ambtemp = telescopeStatus.temperature.ambient
                    except: ambtemp = 'UNKNOWN'
                    f['AMBTEMP'+telnum] = (ambtemp,"Ambient Temp (C)")
                    #S Whats the backplate?           
                    try: bcktemp = telescopeStatus.temperature.backplate
                    except: bcktemp = 'UNKNOWN'
                    f['BCKTEMP'+telnum] = (bcktemp,"Backplate Temp (C)")

                # loop over each aqawan and insert the appropriate keywords
                for aqawan in self.domes:
                    aqStatus = aqawan.status()
                    aqnum = aqawan.name[-1]

                    f['AQSOFTV'+aqnum] = (aqStatus['SWVersion'],"Aqawan software version number")
                    f['AQSHUT1'+aqnum] = (aqStatus['Shutter1'],"Aqawan shutter 1 state")
                    f['AQSHUT2'+aqnum] = (aqStatus['Shutter2'],"Aqawan shutter 2 state")
                    f['INHUMID'+aqnum] = (aqStatus['EnclHumidity'],"Humidity inside enclosure")
                    f['DOOR1'  +aqnum] = (aqStatus['EntryDoor1'],"Door 1 into aqawan state")
                    f['DOOR2'  +aqnum] = (aqStatus['EntryDoor2'],"Door 2 into aqawan state")
                    f['PANELDR'+aqnum] = (aqStatus['PanelDoor'],"Aqawan control panel door state")
                    f['HRTBEAT'+aqnum] = (aqStatus['Heartbeat'],"Heartbeat timer")
                    f['AQPACUP'+aqnum] = (aqStatus['SystemUpTime'],"PAC uptime (seconds)")
                    f['AQFAULT'+aqnum] = (aqStatus['Fault'],"Aqawan fault present?")
                    f['AQERROR'+aqnum] = (aqStatus['Error'],"Aqawan error present?")
                    f['PANLTMP'+aqnum] = (aqStatus['PanelExhaustTemp'],"Aqawan control panel exhaust temp (C)")
                    f['AQTEMP' +aqnum] = (aqStatus['EnclTemp'],"Enclosure temperature (C)")
                    f['AQEXTMP'+aqnum] = (aqStatus['EnclExhaustTemp'],"Enclosure exhaust temperature (C)")
                    f['AQINTMP'+aqnum] = (aqStatus['EnclIntakeTemp'],"Enclosure intake temperature (C)")
                    f['AQLITON'+aqnum] = (aqStatus['LightsOn'],"Aqawan lights on?")

                # Weather station
                f['WJD'] = (str(self.site.weather['date']),"Last update of weather (UTC)")
                f['RAIN'] = (self.site.weather['wxt510Rain'],"Current Rain (mm?)")
                f['TOTRAIN'] = (self.site.weather['totalRain'],"Total rain since ?? (mm?)")
                f['OUTTEMP'] = (self.site.weather['outsideTemp'], "Outside Temperature (C)")
                f['MCLOUD'] = (str(self.site.weather['MearthCloud']),"Mearth Cloud Sensor (C)")
                f['HCLOUD'] = (str(self.site.weather['HATCloud']),"HAT Cloud Sensor (C)")
                f['ACLOUD'] = (str(self.site.weather['AuroraCloud']),"Aurora Cloud Sensor (C)")
                f['DEWPOINT'] = (self.site.weather['outsideDewPt'],"Dewpoint (C)")
                f['WINDSPD'] = (self.site.weather['windSpeed'],"Wind Speed (mph)")
                f['WINDGUST'] = (self.site.weather['windGustSpeed'],"Wind Gust Speed (mph)")
                f['WINDIR'] = (self.site.weather['windDirectionDegrees'],"Wind Direction (Deg E of N)")
                f['PRESSURE'] = (self.site.weather['barometer'],"Outside Pressure (mmHg?)")
                f['SUNALT'] = (self.site.weather['sunAltitude'],"Sun Altitude (deg)")

                '''
                # spectrograph information
                EXPTYPE = 'Time-Based'         / Exposure Type                                  
                DETECTOR= 'SI850'              / Detector Name                                  
                '''

                f['CCDMODE'] = (0,'CCD Readout Mode')
                f['FIBER'] = ('','Fiber Bundle Used')
                f['ATM_PRES'] = ('UNKNOWN','Atmospheric Pressure (mbar)')
                #TODOTDOTDO
                #S TESTING trying to isolate errors, need to remove
                f['VAC_PRES'] = (0.0,"Vac pretture TEMPORARY")#(self.spectrograph.get_vacuum_pressure(),"Vacuum Tank Pressure (mbar)")
                f['SPECHMID'] = ('UNKNOWN','Spectrograph Room Humidity (%)')
                for i in range(16):
                        filename = self.base_directory + '/log/' + self.night + '/temp' + str(i+1) + '.log'
                        with open(filename,'r') as fh:
                                lineList = fh.readlines()
                                temps = lineList[-1].split(',')
                                if temps[1] == "None" : temp = 'UNKNOWN'
                                else: temp = float(temps[1])
                        f['TEMP' + str(i+1)] = (temp,temps[2].strip() + ' Temperature (C)')
                f['I2TEMPA'] = (self.spectrograph.cell_heater_temp(),'Iodine Cell Actual Temperature (C)')
                f['I2TEMPS'] = (self.spectrograph.cell_heater_get_set_temp(),'Iodine Cell Set Temperature (C)')
                f['I2POSAF'] = (self.spectrograph.i2stage_get_pos()[0],'Iodine Stage Actual Position [cm]')
                f['I2POSAS'] = (self.spectrograph.i2stage_get_pos()[1],'Iodine Stage Actual Position [string]')
                f['I2POSSS'] = (self.spectrograph.lastI2MotorLocation,'Iodine Stage Set Position [string]')
                f['SFOCPOS'] = ('UNKNOWN','KiwiSpec Focus Stage Position')
                #S PDU Header info
                self.spectrograph.update_dynapower1()
                self.spectrograph.update_dynapower2()
                dyna1keys  = ['tharLamp','flatLamp','expmeter','i2heater']
                for key in dyna1keys:
                        f[key] = (self.spectrograph.dynapower1_status[key],"Outlet for "+key)
                dyna2keys = ['i2stage']
                for key in dyna2keys:
                        f[key] = (self.spectrograph.dynapower2_status[key],"Outlet for "+key)

                
		header = json.dumps(f)
		self.logger.info('Waiting for spectrograph imaging thread')
		# wait for imaging process to complete
		imaging_thread.join()
		
		# write header for image
		if self.spectrograph.write_header(header):
			self.logger.info('Finished writing spectrograph header')
			return self.spectrograph.file_name
                #ipdb.set_trace()

		self.logger.error('takeSpectrum failed: ' + self.spectrograph.file_name)
		return 'error'

	#take one image based on parameter given, return name of the image, return 'error' if fail
	#image is saved on remote computer's data directory set by imager.set_data_path()
	def takeImage(self, exptime, filterInd, objname, camera_num=0, defocus=0.0):

		telescope_name = 'T' + str(camera_num) +': '
		#check camera number is valid
		if camera_num > len(self.cameras) or camera_num < 0:
			return 'error'
		if camera_num > 2:
			dome = self.domes[1]
		elif camera_num > 0:
			dome = self.domes[0]
			
		telescope = self.telescopes[camera_num-1]
		imager = self.cameras[camera_num-1]
		self.logger.info(telescope_name + 'starting imaging thread')
		#start imaging process in a different thread
		imaging_thread = threading.Thread(target = imager.take_image, args = (exptime, filterInd, objname))
		imaging_thread.start()
		
		#Prepare header while waiting for imager to finish taking image
		while self.site.getWeather() == -1: pass
		telescopeStatus = telescope.getStatus()
		domeStatus = dome.status()

		
		telra = str(self.ten(telescopeStatus.mount.ra_2000)*15.0)
		teldec = str(self.ten(telescopeStatus.mount.dec_2000))
		ra = str(self.ten(telescopeStatus.mount.ra_target)*15.0)
		dec = self.ten(telescopeStatus.mount.dec_target)
		if dec > 90.0: dec = dec-360 # fixes bug in PWI
		dec = str(dec)

		az = str(float(telescopeStatus.mount.azm_radian)*180.0/math.pi)
		alt = str(float(telescopeStatus.mount.alt_radian)*180.0/math.pi)
		airmass = str(1.0/math.cos((90.0 - float(alt))*math.pi/180.0))

		moonpos = self.site.moonpos()
		moonra = str(moonpos[0])
		moondec = str(moonpos[1])
		moonsep = str(ephem.separation((float(telra)*math.pi/180.0,float(teldec)*math.pi/180.0),moonpos)*180.0/math.pi)
		moonphase = str(self.site.moonphase())

		#get header info into json format and pass it to imager's write_header method
		f = collections.OrderedDict()

		# Static Keywords
		f['SITELAT'] = str(self.site.obs.lat)
		f['SITELONG'] = (str(self.site.obs.lon),"East Longitude of the imaging location")
		f['SITEALT'] = (str(self.site.obs.elevation),"Site Altitude (m)")
		f['OBSERVER'] = ('MINERVA Robot',"Observer")
		f['TELESCOP'] = "T" + str(camera_num)
		f['OBJECT'] = objname
		f['APTDIA'] = "700"
		f['APTAREA'] = "490000"
		gitNum = "100" #for testing purpose
		f['ROBOVER'] = (gitNum,"Git commit number for robotic control software")

		# Site Specific
		f['LST'] = (telescopeStatus.status.lst,"Local Sidereal Time")

		# Enclosure Specific
		f['AQSOFTV'] = (domeStatus['SWVersion'],"Aqawan software version number")
		f['AQSHUT1'] = (domeStatus['Shutter1'],"Aqawan shutter 1 state")
		f['AQSHUT2'] = (domeStatus['Shutter2'],"Aqawan shutter 2 state")
		f['INHUMID'] = (domeStatus['EnclHumidity'],"Humidity inside enclosure")
		f['DOOR1'] = (domeStatus['EntryDoor1'],"Door 1 into aqawan state")
		f['DOOR2'] = (domeStatus['EntryDoor2'],"Door 2 into aqawan state")
		f['PANELDR'] = (domeStatus['PanelDoor'],"Aqawan control panel door state")
		f['HRTBEAT'] = (domeStatus['Heartbeat'],"Heartbeat timer")
		f['AQPACUP'] = (domeStatus['SystemUpTime'],"PAC uptime (seconds)")
		f['AQFAULT'] = (domeStatus['Fault'],"Aqawan fault present?")
		f['AQERROR'] = (domeStatus['Error'],"Aqawan error present?")
		f['PANLTMP'] = (domeStatus['PanelExhaustTemp'],"Aqawan control panel exhaust temp (C)")
		f['AQTEMP'] = (domeStatus['EnclTemp'],"Enclosure temperature (C)")
		f['AQEXTMP'] = (domeStatus['EnclExhaustTemp'],"Enclosure exhaust temperature (C)")
		f['AQINTMP'] = (domeStatus['EnclIntakeTemp'],"Enclosure intake temperature (C)")
		f['AQLITON'] = (domeStatus['LightsOn'],"Aqawan lights on?")

		# Mount specific
		f['TELRA'] = (telra,"Telescope RA (J2000)")
		f['TELDEC'] = (teldec,"Telescope Dec (J2000)")
		f['RA'] = (ra, "Solved RA (J2000)") # this will be overwritten by astrometry.net
		f['DEC'] =  (dec, "Solved Dec (J2000)") # this will be overwritten by astrometry.net
		f['TARGRA'] = (ra, "Target RA (J2000)")
		f['TARGDEC'] =  (dec, "Target Dec (J2000)")
		f['ALT'] = (alt,'Telescope altitude (deg)')
		f['AZ'] = (az,'Telescope azimuth (deg E of N)')
#		print airmass
#		ipdb.set_trace()
		f['AIRMASS'] = (airmass,"airmass (plane approximation)")

		f['MOONRA'] = (moonra, "Moon RA (J2000)")    
		f['MOONDEC'] =  (moondec, "Moon Dec (J2000)")
		f['MOONPHAS'] = (moonphase, "Moon Phase (Fraction)")    
		f['MOONDIST'] =  (moonsep, "Distance between pointing and moon (deg)")
		f['PMODEL'] = (telescopeStatus.mount.pointing_model,"Pointing Model File")

		# Focuser Specific
		f['FOCPOS'] = (telescopeStatus.focuser.position,"Focus Position (microns)")
		f['DEFOCUS'] = (str(defocus),"Intentional defocus (mm)")

		# Rotator Specific
		f['ROTPOS'] = (telescopeStatus.rotator.position,"Rotator Position (degrees)")

		# WCS
		platescale = imager.platescale/3600.0*imager.xbin # deg/pix
		PA = 0.0#float(telescopeStatus.rotator.position)*math.pi/180.0
		f['PIXSCALE'] = str(platescale*3600.0)
		f['CTYPE1'] = ("RA---TAN","TAN projection")
		f['CTYPE2'] = ("DEC--TAN","TAN projection")
		f['CUNIT1'] = ("deg","X pixel scale units")
		f['CUNIT2'] = ("deg","Y pixel scale units")
		f['CRVAL1'] = (telra,"RA of reference point")
		f['CRVAL2'] = (teldec,"DEC of reference point")
		f['CRPIX1'] = (str(imager.xcenter),"X reference pixel")
		f['CRPIX2'] = (str(imager.ycenter),"Y reference pixel")
		f['CD1_1'] = str(-platescale*math.cos(PA))
		f['CD1_2'] = str(platescale*math.sin(PA))
		f['CD2_1'] = str(platescale*math.sin(PA))
		f['CD2_2'] = str(platescale*math.cos(PA))
		'''
		f['WCSAXES'] = 2
		f['EQUINOX'] = 2000.0
		f['LONPOLE'] = 180.0
		f['LATPOLE'] = 0.0
		f['IMAGEW'] = 0.0
		f['IMAGEH'] = 0.0
		f['A_ORDER'] = 2
		f['A_0_2'] = 0.0
		f['A_1_1'] = 0.0
		f['A_2_0'] = 0.0
		f['B_ORDER'] = 2
		f['B_0_2'] = 0.0
		f['B_1_1'] = 0.0
		f['B_2_0'] = 0.0
		f['AP_ORDER'] = 2
		f['AP_0_1'] = 0.0
		f['AP_0_2'] = 0.0
		f['AP_1_0'] = 0.0
		f['AP_1_1'] = 0.0
		f['AP_2_0'] = 0.0
		f['BP_ORDER'] = 2
		f['BP_0_1'] = 0.0
		f['BP_0_2'] = 0.0
		f['BP_1_0'] = 0.0
		f['BP_1_1'] = 0.0
		f['BP_2_0'] = 0.0
		f['WCSSOLVE'] = ''
		'''

		# M3 Specific
		f['PORT'] = (telescopeStatus.m3.port,"Selected port")
		
		# Fans
		f['OTAFAN'] = (telescopeStatus.fans.on,"OTA Fans on?")    

		# Telemetry
		try: f['M1TEMP'] = (telescopeStatus.temperature.primary,"Primary Mirror Temp (C)")
		except: f['M1TEMP'] = ("UNKNOWN","Primary Mirror Temp (C)")
		try: f['M2TEMP'] = (telescopeStatus.temperature.secondary,"Secondary Mirror Temp (C)")
		except: f['M2TEMP'] = ("UNKNOWN","Secondary Mirror Temp (C)")
		try: f['M3TEMP'] = (telescopeStatus.temperature.m3,"Tertiary Mirror Temp (C)")
		except: f['M3TEMP'] = ("UNKNOWN","Tertiary Mirror Temp (C)")
		try: f['AMBTMP'] = (telescopeStatus.temperature.ambient,"Ambient Temp (C)")
		except: f['AMBTMP'] = ("UNKNOWN","Ambient Temp (C)")
		try: f['BCKTMP'] = (telescopeStatus.temperature.backplate,"Backplate Temp (C)")
		except: f['BCKTMP'] = ("UNKNOWN","Backplate Temp (C)")

		if self.site.weather != -1:
			# Weather station
			f['WJD'] = (str(self.site.weather['date']),"Last update of weather (UTC)")
			f['RAIN'] = (str(self.site.weather['wxt510Rain']),"Current Rain (mm?)")
			f['TOTRAIN'] = (str(self.site.weather['totalRain']),"Total rain since ?? (mm?)")
			f['OUTTEMP'] = (str(self.site.weather['outsideTemp']),"Outside Temperature (C)")
			f['MCLOUD'] = (str(self.site.weather['MearthCloud']),"Mearth Cloud Sensor (C)")
			f['HCLOUD'] = (str(self.site.weather['HATCloud']),"HAT Cloud Sensor (C)")
			f['ACLOUD'] = (str(self.site.weather['AuroraCloud']),"Aurora Cloud Sensor (C)")
			f['DEWPOINT'] = (str(self.site.weather['outsideDewPt']),"Dewpoint (C)")
			f['WINDSPD'] = (str(self.site.weather['windSpeed']),"Wind Speed (mph)")
			f['WINDGUST'] = (str(self.site.weather['windGustSpeed']),"Wind Gust Speed (mph)")
			f['WINDIR'] = (str(self.site.weather['windDirectionDegrees']),"Wind Direction (Deg E of N)")
			f['PRESSURE'] = (str(self.site.weather['barometer']),"Outside Pressure (mmHg?)")
			f['SUNALT'] = (str(self.site.weather['sunAltitude']),"Sun Altitude (deg)")
		
		header = json.dumps(f)
		
		self.logger.info(telescope_name + 'waiting for imaging thread')
		# wait for imaging process to complete
		imaging_thread.join()
		
		# write header for image 
		if imager.write_header(header):
			self.logger.info(telescope_name + 'finish writing image header')

			if objname <> "Bias" and objname <> "Dark" and objname <> "SkyFlat": 
				# run astrometry asynchronously
				self.logger.info(telescope_name + "Running astrometry to find PA on " + imager.image_name())
				dataPath = '/Data/t' + str(camera_num) + '/' + self.site.night + '/'
				astrometryThread = threading.Thread(target=self.getPA, args=(dataPath + imager.image_name(),), kwargs={})
				astrometryThread.start()
			return imager.image_name()

		self.logger.error(telescope_name + 'takeImage failed: ' + imager.image_name())
		return 'error'
		
	def doBias(self,num=11,camera_num=0):
		telescope_name = 'T' + str(camera_num) +': '
		objectName = 'Bias'
		for x in range(num):
			filename = 'error'
			while filename =='error':
				self.logger.info(telescope_name + 'Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + '0' + ')')
				filename = self.takeImage(0,'V',objectName,camera_num)
			
	def doDark(self,num=11, exptime=60,camera_num=0):
		telescope_name = 'T' + str(camera_num) +': '
		objectName = 'Dark'
		for time in exptime:
			for x in range(num):
				filename = 'error'
				while filename == 'error':
					self.logger.info(telescope_name + 'Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + str(time) + ')')
					filename = self.takeImage(time,'V',objectName,camera_num)
		
	#doSkyFlat for specified telescope
	def doSkyFlat(self,filters,morning=False,num=11,telescope_num=0):

		telescope_name = 'T' + str(telescope_num) +': '
		if telescope_num < 1 or telescope_num > len(self.telescopes):
			self.logger.error(telescope_name + 'invalid telescope index')
			return
			
		if telescope_num > 2:
			dome = self.domes[1]
		else:
			dome = self.domes[0]
		telescope = self.telescopes[telescope_num-1]
		imager = self.cameras[telescope_num-1]
		
		minSunAlt = -12
		maxSunAlt = -2

		targetCounts = 30000
		biasLevel = imager.biaslevel
		saturation = imager.saturation
		maxExpTime = 60
		minExpTime = 10
	   
		# can we actually do flats right now?
		if datetime.datetime.now().hour > 12:
			# Sun setting (evening)
			if morning:
				self.logger.info(telescope_name + 'Sun setting and morning flats requested; skipping')
				return
			if self.site.sunalt() < minSunAlt:
				self.logger.info(telescope_name + 'Sun setting and already too low; skipping')
				return               
			self.site.obs.horizon = str(maxSunAlt)
			flatStartTime = self.site.obs.next_setting(ephem.Sun(),start=self.site.startNightTime, use_center=True).datetime()
			secondsUntilTwilight = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0
		else:
			# Sun rising (morning)
			if not morning:
				self.logger.info(telescope_name + 'Sun rising and evening flats requested; skipping')
				return
			if self.site.sunalt() > maxSunAlt:
				self.logger.info(telescope_name + 'Sun rising and already too high; skipping')
				return  
			self.site.obs.horizon = str(minSunAlt)
			flatStartTime = self.site.obs.next_rising(ephem.Sun(),start=self.site.startNightTime, use_center=True).datetime()
			secondsUntilTwilight = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0

		if secondsUntilTwilight > 7200:
			self.logger.info(telescope_name + 'Twilight too far away (' + str(secondsUntilTwilight) + " seconds)")
			return

		# wait for twilight
		if secondsUntilTwilight > 0 and (self.site.sunalt() < minSunAlt or self.site.sunalt() > maxSunAlt):
			self.logger.info(telescope_name + 'Waiting ' +  str(secondsUntilTwilight) + ' seconds until Twilight')
			time.sleep(secondsUntilTwilight)

		# wait for the dome to open
		while not dome.isOpen:
			# exit if outside of twilight
			if self.site.sunalt() > maxSunAlt or self.site.sunalt() < minSunAlt: return
			self.logger.info("Dome closed; waiting for conditions to improve")
			time.sleep(30)

		# Now it's within 5 minutes of twilight flats
		self.logger.info(telescope_name + 'Beginning twilight flats')

		# make sure the telescope/dome is ready for obs
		telescope.initialize()
		
		# start off with the extreme exposure times
		if morning: exptime = maxExpTime
		else: exptime = minExpTime
	  
		# filters ordered from least transmissive to most transmissive
		# flats will be taken in this order (or reverse order in the morning)
		masterfilters = ['H-Beta','H-Alpha','Ha','Y','U','up','zp','zs','B','I','ip','V','rp','R','gp','w','solar','air']
		if morning: masterfilters.reverse()  

		for filterInd in masterfilters:
			if filterInd in filters and filterInd in imager.filters:

				i = 0
				NotFirstImage = 0
				while i < num:

					# Slew to the optimally flat part of the sky (Chromey & Hasselbacher, 1996)
					Alt = 75.0 # degrees (somewhat site dependent)
					Az = self.site.sunaz() + 180.0 # degrees
					if Az > 360.0: Az = Az - 360.0
					
					# keep slewing to the optimally flat part of the sky (dithers too)
					# DeltaPos is here to check if we're within DeltaPosLimit of the target pos.
					DeltaPos = 90.
					DeltaPosLimit = 1.0
					SlewRepeat = 0
					while DeltaPos > DeltaPosLimit:
						self.logger.info(telescope_name + 'Slewing to the optimally flat part of the sky (alt=' + str(Alt) + ', az=' + str(Az) + ')')
						telescope.mountGotoAltAz(Alt,Az)

						if NotFirstImage == 0:
							if telescope.inPosition():
								self.logger.info(telescope_name + "Finished slew to alt=" + str(Alt) + ', az=' + str(Az) + ')')
								NotFirstImage = 1
							else:
								self.logger.error(telescope_name + "Slew failed to alt=" + str(Alt) + ', az=' + str(Az) + ')')
								# now what?  
						else:
							time.sleep(10)

						telescopeStatus = telescope.getStatus()
						ActualAz = float(telescopeStatus.mount.azm_radian)
						ActualAlt = float(telescopeStatus.mount.alt_radian)
						DeltaPos = math.acos( math.sin(ActualAlt)*math.sin(Alt*math.pi/180.0)+math.cos(ActualAlt)*math.cos(Alt*math.pi/180.0)*math.cos(ActualAz-Az*math.pi/180.0) )*(180./math.pi)
						if DeltaPos > DeltaPosLimit:
							self.logger.error(telescope_name + "Telescope reports it is " + str(DeltaPos) + " degrees away from the target postion; beginning telescope recovery (ActualAlt=" + str(ActualAlt*180.0/math.pi) + ", Requested Alt=" + str(Alt) + ", (ActualAz=" + str(ActualAz*180.0/math.pi) + ", Requested Az=" + str(Az))
							telescope.recover()
							SlewRepeat += 1
						if SlewRepeat>10:
							self.logger.error(telescope_name + "Repeated slewing is not getting us to the flat-field target position; skipping.")
							break
								
					# Take flat fields
					filename = 'error'
					while filename == 'error': filename = self.takeImage(exptime, filterInd, 'SkyFlat',telescope_num)
					
					# determine the mode of the image (mode requires scipy, use mean for now...)
					mode = imager.getMode()
					self.logger.info(telescope_name + "image " + str(i+1) + " of " + str(num) + " in filter " + filterInd + "; " + filename + ": mode = " + str(mode) + " exptime = " + str(exptime) + " sunalt = " + str(self.site.sunalt()))

					# if way too many counts, it can roll over and look dark
					supersaturated = imager.isSuperSaturated()
					
					if mode > saturation or supersaturated:
						# Too much signal
						self.logger.info(telescope_name + "Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) +
									'; sun altitude=' + str(self.site.sunalt()) +
									 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
						imager.remove()
						i-=1
						if exptime == minExpTime and morning:
							self.logger.info(telescope_name + "Exposure time at minimum, image saturated, and getting brighter; skipping remaining exposures in filter " + filterInd)
							break
							
					elif mode < 6.0*biasLevel:
						# Too little signal
						self.logger.info(telescope_name + "Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) + '; sun altitude=' + str(self.site.sunalt()) +
									 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
						imager.remove()
						i -= 1

						if exptime == maxExpTime and not morning:
							self.logger.info(telescope_name + "Exposure time at maximum, not enough counts, and getting darker; skipping remaining exposures in filter " + filterInd)
							break
					elif morning and self.site.sunalt() > maxSunAlt:
						self.logger.info(telescope_name + "Sun rising and greater than maxsunalt; skipping")
						break
					elif not morning and self.site.sunalt() < minSunAlt:
						self.logger.info(telescope_name + "Sun setting and less than minsunalt; skipping")
						break                    
	              # else:
	                  # just right...
			
					# Scale exptime to get a mode of targetCounts in next exposure
					if supersaturated:
						exptime = minExpTime
					elif mode-biasLevel <= 0:
						exptime = maxExpTime
					else:
						exptime = exptime*(targetCounts-biasLevel)/(mode-biasLevel)
						# do not exceed limits
						exptime = max([minExpTime,exptime])
						exptime = min([maxExpTime,exptime])
						self.logger.info(telescope_name + "Scaling exptime to " + str(exptime))
					i += 1


	def scheduleIsValid(self, num, night=None, email=True):

		if night == None:
			night = self.site.night

		targetFile = night + '.T' + str(num) + '.txt'
		telescope_name = 'T' + str(num) +': '


		if not os.path.exists(self.base_directory + '/schedule/' + targetFile):
			self.logger.error(telescope_name + 'No schedule file: ' + targetFile)
			if email: mail.send("No schedule file: " + targetFile,"Cannot observe!",level='serious')
			return False

		emailbody = ''
		with open(self.base_directory + '/schedule/' + targetFile, 'r') as targetfile:
			linenum = 1
			line = targetfile.readline()
			try: CalibInfo = json.loads(line)
			except: CalibInfo = -1
			# check for malformed JSON code
			if CalibInfo == -1:
				self.logger.error(telescope_name + 'Line ' + str(linenum) + ': malformed JSON: ' + line)
				emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
			else:
				requiredKeys = ['nbias','ndark','nflat','darkexptime','flatFilters','WaitForMorning']
				for key in requiredKeys:
					if key not in CalibInfo.keys():
						self.logger.error(telescope_name + 'Line 1: Required key (' + key + ') not present: ' + line)
						emailbody = emailbody + 'Line 1: Required key (' + key + ') not present: ' + line + '\n'

			linenum = 2
			line = targetfile.readline()
			try: CalibEndInfo = json.loads(line)
			except: CalibEndInfo = -1
			# check for malformed JSON code
			if CalibEndInfo == -1:
				self.logger.error(telescope_name + 'Line ' + str(linenum) + ': malformed JSON: ' + line)
				emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
			else:
				requiredKeys = ['nbiasEnd','ndarkEnd','nflatEnd']
				for key in requiredKeys:
					if key not in CalibEndInfo.keys():
						self.logger.error(telescope_name + 'Line 2: Required key (' + key + ') not present: ' + line)
						emailbody = emailbody + 'Line 2: Required key (' + key + ') not present: ' + line + '\n'
						
			linenum = 3
			for line in targetfile:
				target = self.parseTarget(line)
				
				# check for malformed JSON code
				if target == -1:
					self.logger.error(telescope_name + 'Line ' + str(linenum) + ': malformed JSON: ' + line)
					emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
				else:
					# check to make sure all required keys are present
					key = 'name'
					if key not in target.keys():
						self.logger.error(telescope_name + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line)
						emailbody = emailbody + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line + '\n'
					else:
						if target['name'] == 'autofocus':
							requiredKeys = ['starttime','endtime']
						else:
							requiredKeys = ['starttime','endtime','ra','dec','filter','num','exptime','defocus','selfguide','guide','cycleFilter']
							
						for key in requiredKeys:
							if key not in target.keys():
								self.logger.error(telescope_name + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line)
								emailbody = emailbody + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line + '\n'
									
						if target['name'] <> 'autofocus':
							try:
								nnum = len(target['num'])
								nexptime = len(target['exptime'])
								nfilter = len(target['filter'])
								if nnum <> nexptime or nnum <> nfilter:
									self.logger.error(telescope_name + 'Line ' + str(linenum) + ': Array size for num (' + str(nnum) + '), exptime (' + str(nexptime) + '), and filter (' + str(nfilter) + ') must agree')
									emailbody = emailbody + 'Line ' + str(linenum) + ': Array size for num (' + str(nnum) + '), exptime (' + str(nexptime) + '), and filter (' + str(nfilter) + ') must agree\n'                            
							except:
								pass            
				linenum = linenum + 1
				if emailbody <> '':
					if email: mail.send("Errors in target file: " + targetFile,emailbody,level='serious')
					return False
		return True


	#if telescope_num out of range or not specified, do science for all telescopes
	#S I don't think the above is true. Do we want to do something similar tp what
	#S telescope commands were switched to.
	def doScience(self,target,telescope_num = 0):

		telescope_name = 'T' + str(telescope_num) +': '
		
		if telescope_num < 1 or telescope_num > len(self.telescopes):
			self.logger.error('invalid telescope index')
			return
			
		if telescope_num > 2:
			dome = self.domes[1]
		else:
			dome = self.domes[0]

		#used for testing
#		dome.isOpen = True
		telescope = self.telescopes[telescope_num-1]
		
		# if after end time, return
		if datetime.datetime.utcnow() > target['endtime']:
			self.logger.info(telescope_name + "Target " + target['name'] + " past its endtime (" + str(target['endtime']) + "); skipping")
			return

		# if before start time, wait
		if datetime.datetime.utcnow() < target['starttime']:
			waittime = (target['starttime']-datetime.datetime.utcnow()).total_seconds()
			self.logger.info(telescope_name + "Target " + target['name'] + " is before its starttime (" + str(target['starttime']) + "); waiting " + str(waittime) + " seconds")
			time.sleep(waittime)

#		if 'positionAngle' in target.keys(): pa = target['positionAngle']
#		else: pa = None
		pa = None

		if target['name'] == 'autofocus':
                        #TODOACQUIRETARGET Needs to be switched to take dictionary arguement
			try: telescope.acquireTarget(target['ra'],target['dec'],pa=pa)
			except: pass
			telescope.inPosition()
			telescope.autoFocus()
			return

                #TODOACQUIRETARGET Needs to be switched to take dictionary arguement
		# slew to the target
		telescope.acquireTarget(target['ra'],target['dec'],pa=pa)


		newfocus = telescope.focus + target['defocus']*1000.0
		status = telescope.getStatus()
		if newfocus <> status.focuser.position:
			self.logger.info(telescope_name + "Defocusing Telescope by " + str(target['defocus']) + ' mm, to ' + str(newfocus))
			telescope.focuserMove(newfocus)

		status = telescope.getStatus()
		while status.focuser.moving == 'True':
			self.logger.info(telescope_name + 'Focuser moving (' + str(status.focuser.position) + ')')
			time.sleep(0.3)
			status = telescope.getStatus()

		reference = None

		# take one in each band, then loop over number (e.g., B,V,R,B,V,R,B,V,R)
		if target['cycleFilter']:
			for i in range(max(target['num'])):
				for j in range(len(target['filter'])):
					filename = 'error'
					while filename == 'error':
						if dome.isOpen == False:
							while dome.isOpen == False:
								self.logger.info(telescope_name + 'Enclosure closed; waiting for conditions to improve')
								time.sleep(30)
								if datetime.datetime.utcnow() > target['endtime']: return
							#TODOACQUIRETARGET Needs to be switched to take dictionary arguement
							#reacquire target after waiting for dome to open
							telescope.acquireTarget(target['ra'],target['dec'])
						if datetime.datetime.utcnow() > target['endtime']: return
						if i < target['num'][j]:
							self.logger.info(telescope_name + 'Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
							filename = self.takeImage(target['exptime'][j], target['filter'][j], target['name'],telescope_num, defocus=target['defocus'])
							if target['selfguide'] and filename <> 'error': reference = self.guide('/Data/t' + str(telescope_num) + '/' + self.site.night + '/' + filename,reference)
					
					
		else:
			# take all in each band, then loop over filters (e.g., B,B,B,V,V,V,R,R,R) 
			for j in range(len(target['filter'])):
				# cycle by number
				for i in range(target['num'][j]):
					filename = 'error'
					while filename == 'error':
						if dome.isOpen == False:
							while dome.isOpen == False:
								self.logger.info(telescope_name + 'Enclosure closed; waiting for conditions to improve')
								time.sleep(30)
								if datetime.datetime.utcnow() > target['endtime']: return

                                                        #TODOACQUIRETARGET Needs to be switched to take dictionary arguement
						        #reacquire target after waiting for dome to open
							telescope.acquireTarget(target['ra'],target['dec'])
						if datetime.datetime.utcnow() > target['endtime']: return
						self.logger.info(telescope_name + 'Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
						filename = self.takeImage(target['exptime'][j], target['filter'][j], target['name'],telescope_num, defocus=target['defocus'])
						if target['selfguide'] and filename <> 'error': reference = self.guide('/Data/t' + str(telescope_num) + '/' + self.site.night + '/' + filename,reference)

	#prepare logger and set imager data path
	def prepNight(self,num=0,email=True):

		# reset the night at 10 am local
		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
			today = today + datetime.timedelta(days=1.0)
		night = 'n' + today.strftime('%Y%m%d')

		#set correct path for the night
		self.logger.info("Setting up directories for " + night)
#		self.setup_loggers()
		self.imager_setDatapath(night,num)
	
		if email: mail.send('T' + str(num) + ' Starting observing','Love,\nMINERVA')

	def backup(self, num, night=None):
		
		if night == None:
			night = self.site.night


		dataPath = '/Data/t' + str(num) + '/' + night + '/'
		backupPath = '/home/minerva/backup/t' + str(num) + '/' + night + '/'
		if not os.path.exists(backupPath):
			os.mkdir(backupPath)
		self.logger.info('backing up files from ' + dataPath + ' to ' + backupPath)

		# wait for compression to complete
		files = [1]
		t0 = datetime.datetime.utcnow()
		elapsedTime = 0.0
		timeout = 300.0
		while len(files) <> 0 and elapsedTime < timeout:
			time.sleep(5.0)
			elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
			files = glob.glob(dataPath + '*.fits')

		files = glob.glob(dataPath + '*')
		for f in files:
			shutil.copyfile(f, backupPath + os.path.basename(f))


	def endNight(self, num=0, email=True):

		dataPath = '/Data/t' + str(num) + '/' + self.site.night + '/'

		# park the scope
		self.logger.info("Parking Telescope")
		self.telescope_park(num)
#		self.telescope_shutdown(num)

		# Compress the data
		self.logger.info("Compressing data")
		self.imager_compressData(num)

		# Turn off the camera cooler, disconnect
#		self.logger.info("Disconnecting imager")
#		self.imager_disconnect()

                #TODO: Back up the data
		self.backup(num)

		# copy schedule to data directory
		self.logger.info("Copying schedule file from " + self.base_directory + "/schedule/" + self.site.night + ".T" + str(num) + ".txt to " + dataPath)
		try: shutil.copyfile(self.base_directory + '/schedule/' + self.site.night + ".T" + str(num) + '.txt', dataPath)
		except: pass

		# copy logs to data directory
		logs = glob.glob(self.base_directory + "/log/" + self.site.night + "/*.log")
		for log in logs:
			self.logger.info("Copying log file " + log + " to " + dataPath)
			try: shutil.copyfile(log, dataPath + os.path.basename(log))
			except: pass

                #### create an observing report ####

		# summarize the observed targets
		filenames = glob.glob(dataPath + '/*.fits*')
		objects = {}
		for filename in filenames:
			obj = filename.split('.')[2]
			if obj <> 'Bias' and obj <> 'Dark':
				obj += ' ' + filename.split('.')[3]
			if obj not in objects.keys():
				objects[obj] = 1
			else: objects[obj] += 1

		# scrape the logs to summarize the weather and errors
		errors = {}
		weatherstats = {
			#'totalRain':[],
			'wxt510Rain':[],
			'barometer':[],
			'windGustSpeed':[],
			#        'cloudDate':[],
			'outsideHumidity':[],
			'outsideDewPt':[],
			'MearthCloud':[],
			'HATCloud':[],
			'AuroraCloud':[],
			'outsideTemp':[],
			'windSpeed':[],
			'windDirectionDegrees':[],
			#        'date':[],
			#        'sunAltitude':[],
			}
#		ipdb.set_trace()
		for log in logs:
			with open(log,'r') as f:
				for line in f:
					if re.search('WARNING: ',line) or re.search("ERROR: ",line):
						if re.search('WARNING: ',line): errmsg = line.split('WARNING: ')[1].strip()
						else: errmsg = line.split('ERROR: ')[1].strip()
						
						if len(errmsg.split('active ')) > 1:
							errmsg = errmsg.split('active')[0] + 'active'

						if errmsg not in errors.keys():
							errors[errmsg] = 1
						else: errors[errmsg] += 1
					elif re.search('=',line):
						try: key = line.split('=')[-2].split()[-1]
						except: key = 'fail'
						if key in weatherstats.keys():
							time = datetime.datetime.strptime(line.split()[0],"%Y-%m-%dT%H:%M:%S")
							try:
								value = float(line.split('=')[-1].strip())
								weatherstats[key].append((time,value))
							except: pass

		# compose the observing report
		body = "Dear humans,\n\n" + \
		    "While you were sleeping, I observed:\n\n"

		for key in objects.keys():
			body += key + ': '+ str(objects[key]) + '\n'

		body += '\nI encountered the following errors and warnings:\n\n'
		for key in errors.keys():
			body += key + ': ' + str(errors[key]) + '\n'

		body += '\nThe weather for tonight was:\n\n'
		for key in weatherstats:
			arr = [x[1] for x in weatherstats[key]]
			if len(arr) > 0:
				body += key + ': min=' + str(min(arr)) + \
				    ', max=' + str(max(arr)) + \
				    ', ave=' + str(sum(arr)/float(len(arr))) + '\n'

		body += "\nPlease see the webpage for movies and another diagnostics:\n" + \
		    "https://www.cfa.harvard.edu/minerva/site/" + self.site.night + "/movie.html\n\n" + \
		    "Love,\n" + \
		    "MINERVA"

		# email observing report
		if email: mail.send("T" + str(num) + ' done observing',body)

	def parseTarget(self,line):
		try:
			target = json.loads(line)
		except ValueError:
			self.logger.error('Not a valid JSON line: ' + line)
			return -1
		
		# convert strings to datetime objects
		target['starttime'] = datetime.datetime.strptime(target['starttime'],'%Y-%m-%d %H:%M:%S')
		target['endtime'] = datetime.datetime.strptime(target['endtime'],'%Y-%m-%d %H:%M:%S')
		return target
		
	#main observing routine, control one telescope
	def observingScript(self,telescope_num=0):
		
		telescope_name = 'T' + str(telescope_num) +': '

		if telescope_num < 1 or telescope_num > len(self.telescopes):
			self.logger.error(telescope_name + 'invalid telescope index')
			return
		
		#set up night's directory
		self.prepNight(telescope_num)
		self.scheduleIsValid(telescope_num)

		self.telescopes[telescope_num-1].shutdown()
		self.telescopes[telescope_num-1].killPWI()
		self.telescopes[telescope_num-1].initialize(tracking=False)
		self.telescopes[telescope_num-1].initialize_autofocus()

		#S Initialize, home, and park telescope. 
		#S Enable mount and connect to motors.
#		self.telescopes[telescope_num-1].initialize(tracking=False)

		'''
		#S Send her home, make sure everything is running right. 
		self.telescopes[telescope_num-1].home()
		time.sleep(300)
		#S Same for rotator
		self.telescopes[telescope_num-1].home_rotator()
		time.sleep(420)
		'''
		#S Do an initial connection to autofocus, this way we can use it later 
		#S without issue. For some reason, we can't autofocus unless we have started
		#S stopped it once.
#		self.telescopes[telescope_num-1].initialize_autofocus()
		#S Let her run?
#		time.sleep(60)
		

		#S Finally (re)park the telescope. 
		self.telescopes[telescope_num-1].park()

		# wait for the camera to cool down
		self.cameras[telescope_num-1].cool()

		CalibInfo,CalibEndInfo = self.loadCalibInfo(telescope_num)
		# Take biases and darks
		# wait until it's darker to take biases/darks
		readtime = 10.0

		# turn off both monitors
		self.logger.info('Turning off monitors')
		try: self.npss[0].off(8)
		except: self.logger.exception("Turning off monitor in aqawan 1 failed")
		try: self.npss[2].off(8)
		except: self.logger.exception("Turning off monitor in aqawan 2 failed")


		bias_seconds = CalibInfo['nbias']*readtime+CalibInfo['ndark']*sum(CalibInfo['darkexptime']) + CalibInfo['ndark']*readtime*len(CalibInfo['darkexptime']) + 600.0
		biastime = self.site.sunset() - datetime.timedelta(seconds=bias_seconds)
		waittime = (biastime - datetime.datetime.utcnow()).total_seconds()
		if waittime > 0:
			# Take biases and darks (skip if we don't have time before twilight)
			self.logger.info(telescope_name + 'Waiting until darker before biases/darks (' + str(waittime) + ' seconds)')

			time.sleep(waittime)
			#S Re-initialize, and turn tracking on. 
			self.doBias(CalibInfo['nbias'],telescope_num)
			self.doDark(CalibInfo['ndark'], CalibInfo['darkexptime'],telescope_num)

		# Take Evening Sky flats
		#S Initialize again, but with tracking on.
		self.telescopes[telescope_num-1].initialize(tracking=True)
		flatFilters = CalibInfo['flatFilters']
		self.doSkyFlat(flatFilters, False, CalibInfo['nflat'],telescope_num)
		
		
		# Wait until nautical twilight ends 
		timeUntilTwilEnd = (self.site.NautTwilEnd() - datetime.datetime.utcnow()).total_seconds()
		if timeUntilTwilEnd > 0:
			self.logger.info(telescope_name + 'Waiting for nautical twilight to end (' + str(timeUntilTwilEnd) + 'seconds)')
			time.sleep(timeUntilTwilEnd)

		if telescope_num > 2: dome = self.domes[1]
		else: dome = self.domes[0]

		while not dome.isOpen and datetime.datetime.utcnow() < self.site.NautTwilBegin():
			self.logger.info(telescope_name + 'Enclosure closed; waiting for conditions to improve')
			time.sleep(60)

		# find the best focus for the night
		if datetime.datetime.utcnow() < self.site.NautTwilBegin():
			self.logger.info(telescope_name + 'Beginning autofocus')
#			self.telescope_intiailize(telescope_num)
#			telescope.inPosition()
			self.telescope_autoFocus(telescope_num)

		# read the target list
		with open(self.base_directory + '/schedule/' + self.site.night + '.T' + str(telescope_num) + '.txt', 'r') as targetfile:
			next(targetfile) # skip the calibration headers
			next(targetfile) # skip the calibration headers
			for line in targetfile:
				target = self.parseTarget(line)
				if target <> -1:
					# check if the end is after morning twilight begins
					if target['endtime'] > self.site.NautTwilBegin(): 
						target['endtime'] = self.site.NautTwilBegin()
					# check if the start is after evening twilight ends
					if target['starttime'] < self.site.NautTwilEnd(): 
						target['starttime'] = self.site.NautTwilEnd()

					# compute the rise/set times of the target
					self.site.obs.horizon = '20.0'
					body = ephem.FixedBody()
					body._ra = str(target['ra'])
					body._dec = str(target['dec'])
					body._epoch = '2000.0'
					body.compute()

					try:
						risetime = self.site.obs.next_rising(body,start=self.site.NautTwilEnd()).datetime()
					except ephem.AlwaysUpError:
						# if it's always up, don't modify the start time
						risetime = target['starttime']
					except ephem.NeverUpError:
						# if it's never up, skip the target
						risetime = target['endtime']
					try:
						settime = self.site.obs.next_setting(body,start=self.site.NautTwilEnd()).datetime()
					except ephem.AlwaysUpError:
						# if it's always up, don't modify the end time
						settime = target['endtime']
					except ephem.NeverUpError:
						# if it's never up, skip the target
						settime = target['starttime']

					if risetime > settime:
						try:
							risetime = self.site.obs.next_rising(body,start=self.site.NautTwilEnd()-datetime.timedelta(days=1)).datetime()
						except ephem.AlwaysUpError:
							# if it's always up, don't modify the start time
							risetime = target['starttime']
						except ephem.NeverUpError:
							# if it's never up, skip the target
							risetime = target['endtime']
						
					# make sure the target is always above the horizon
					if target['starttime'] < risetime:
						target['starttime'] = risetime
					if target['endtime'] > settime:
						target['endtime'] = settime

					if target['starttime'] < target['endtime']:
						self.doScience(target,telescope_num)
					else:
						self.logger.info(telescope_name + target['name']+ ' not observable; skipping')
						
						
		# Take Morning Sky flats
		# Check if we want to wait for these
		if CalibInfo['WaitForMorning']:
			sleeptime = (self.site.NautTwilBegin() - datetime.datetime.utcnow()).total_seconds()
			if sleeptime > 0:
				self.logger.info(telescope_name + 'Waiting for morning flats (' + str(sleeptime) + ' seconds)')
				time.sleep(sleeptime)
			self.doSkyFlat(flatFilters, True, CalibInfo['nflat'],telescope_num)

		# Want to close the aqawan before darks and biases
		# closeAqawan in endNight just a double check
		self.telescope_park(telescope_num)
		self.observing = False

		if CalibEndInfo['nbiasEnd'] <> 0 or CalibEndInfo['ndarkEnd']:
			self.imager_connect(telescope_num) # make sure the cooler is on


		# Take biases and darks
		if CalibInfo['WaitForMorning']:
			sleeptime = (self.site.sunrise() - datetime.datetime.utcnow()).total_seconds()
			if sleeptime > 0:
				self.logger.info(telescope_name + 'Waiting for sunrise (' + str(sleeptime) + ' seconds)')
				time.sleep(sleeptime)
			t0 = datetime.datetime.utcnow()
			timeout = 600.0

			if telescope_num > 2: dome = self.domes[1]
			else: dome = self.domes[0]

			# wait for the dome to close (the heartbeat thread will update its status)
			while dome.isOpen and (datetime.datetime.utcnow()-t0).total_seconds() < timeout:
				self.logger.info(telescope_name + 'Waiting for dome to close')
				time.sleep(60)
				
			self.doBias(CalibEndInfo['nbiasEnd'],telescope_num)
			self.doDark(CalibEndInfo['ndarkEnd'], CalibInfo['darkexptime'],telescope_num)
		
		self.endNight(telescope_num)
		
	def observingScript_catch(self,telescope_num):
		telescope_name = 'T' + str(telescope_num) +': '
		try:
			self.observingScript(telescope_num)
		except Exception as e:
			self.logger.exception(telescope_name + ' ' + str(e.message) )
			body = "Dear benevolent humans,\n\n" + \
			    'I have encountered an unhandled exception which has killed this thread. The error message is:\n\n' + \
			    str(e.message) + "\n\n" + \
			    "Check control.log for additional information. Please investigate, consider adding additional error handling, and restart this telescope thread only.\n\n" + \
			    "Love,\n" + \
			    "MINERVA"
			mail.send("T" + str(telescope_num) + " thread died",body,level='serious')
			sys.exit()
			
	def observingScript_all(self):
		self.domeControlThread()
		
		# python bug work around -- strptime not thread safe. Must call this onece before starting threads
		junk = datetime.datetime.strptime('2000-01-01 00:00:00','%Y-%m-%d %H:%M:%S')

		threads = [None]*len(self.telescopes)
		self.logger.info('Starting '+str(len(self.telescopes))+ ' telecopes.')
		for t in range(len(self.telescopes)):
			threads[t] = threading.Thread(target = self.observingScript_catch,args = (t+1,))
			threads[t].start()
		for t in range(len(self.telescopes)):
			threads[t].join()
			
	#TODO:set up http server to handle manual commands
	def run_server(self):
		pass
        #S Big batch of psuedo code starting up, trying to get a framework for the RV observing
	#S script written down. 
        def rv_observing(self):
                #S Get the domes running in thread
                self.domeControlThread()
                #S Not really sure what prepNight does, but seems like it
                #S takes care of some loggin stuff/names, and updates site info.
                #S running it, but need explanation
                #TODO I htink prepNight needs t o be run for each scope
                #XXX self.prepNight()
                #S Initialize ALL telescopes
                self.Telescope_initialize
                #S Spec CCD calibration process
                self.spec_calib_time()
                self.spec_calibration()

                

                #S Use a scheduler to determine the best target
                #TODO I think we'll load in the data as a dictionary containing dictionaries for
                #TODO each etaEarth target, so etaEarth['target_name']['attributes']
                while nighttime:
                        #S Better have the scheduler check validity of target as well.
                        #S So nexttarget here is the dictionary of the next target.
                        nexttarget = self.scheduler(etaEarth)
                        self.telescope_aquireTarget(nexttarget['ra'],nexttarget['dec'])
                        self.takeSpectrum(etaEarth[nexttarget])
                
                
                

        ###
	# SPECTROGRAPH CALIBRATION
	###

	#S Spectrograph calibration routine. 

        #S Figure the (hopefully) maximum time needed for calibration sequence.
        #S This returns the time in seconds so, so be aware of that. Could return
        #S a time_diff or something though, which might be a but more useful.
        def spec_calib_time(self):
                #S Readout time for the spec CCD, seconds
                READOUTTIME = 40.
                #S Warm up time for lamps,seconds * minutes, which should be ten.
                #TODO Make self.WARMUPTIME
                WARMUPTIME = 60.*0.5#10.
                #S Calc times
                time_for_arcs = WARMUPTIME + np.sum(np.array(self.calib_dict['arc_nums'])*(READOUTTIME + np.array(self.calib_dict['arc_times'])))
                print 'Time for arcs: '+str(time_for_arcs)
                time_for_flats = WARMUPTIME + np.sum(np.array(self.calib_dict['flat_nums']) * (READOUTTIME + np.array(self.calib_dict['flat_times'])))
                print 'Time for flats: '+str(time_for_flats)
                time_for_darks = np.sum(np.array(self.calib_dict['dark_nums']) * (READOUTTIME + np.array(self.calib_dict['dark_times'])))
                print 'Time for darks: '+str(time_for_darks)
                time_for_bias = np.sum(np.array(self.calib_dict['bias_nums']) * (READOUTTIME + np.array(self.calib_dict['bias_times'])))
                print 'Time for bias: '+str(time_for_bias)

                calib_time = time_for_arcs + time_for_flats + time_for_darks + time_for_bias

                return calib_time
                                                    
                
                
                

	#TODO Measure readout time for CCD for taking it into, about 40s is the guess, more like 42s
	#TODO account for overhead.



	def spec_calibration(self):#num_arcs, num_darks, num_flats, num_bias):
                #TODO Will having the calibration shutter closed be enough for darks, biases? We Think...
                #TODO This could really help for warmup times, etc.
                        

                #S Including a back up to ensure the I2heater is on. As if we are
                #S running calibrations, we'll probably need to be taking spectra of targets.
                self.spectrograph.cell_heater_on()

                #S Turn the ThAr lamp on
                self.spectrograph.thar_turn_on()
                #S Take the number of arcs specified
                #S For the number of sets (e.g. the number of different exposure times we need to take any number
                #S of images for)
                for set_num in range(len(self.calib_dict['arc_nums'])):
                        #S For the number of images in a set
                        for num in range(self.calib_dict['arc_nums'][set_num]):
                                #S Log the number of how many and the exposure time
                                self.logger.info("Taking arc image: %02.0f/%02.0f, at %.0f seconds"%(num+1,self.calib_dict['arc_nums'][set_num],self.calib_dict['arc_times'][set_num]))
                                #S Take it
                                self.takeSpectrum(self.calib_dict['arc_times'][set_num],'arc')
                        
                #S Turn ThAr off, but I think it would be caought by later exposure conditoins
                self.spectrograph.thar_turn_off()
                
                #S Prepping flat lamp
                self.spectrograph.flat_turn_on()
                #S For the number of sets (e.g. the number of different exposure times we need to take any number
                #S of images for)
                for set_num in range(len(self.calib_dict['flat_nums'])):
                        #S For the number of images in a set
                        for num in range(self.calib_dict['flat_nums'][set_num]):
                                #S Log the number of how many and the exposure time
                                self.logger.info("Taking flat image: %02.0f/%02.0f, at %.0f seconds"%(num+1,self.calib_dict['flat_nums'][set_num],self.calib_dict['flat_times'][set_num]))
                                #S Take it
                                self.takeSpectrum(self.calib_dict['flat_times'][set_num],'flat')


                #S Turn the flat lamp off
                self.spectrograph.flat_turn_off()

                #S Lets take darks
                #S For the number of sets (e.g. the number of different exposure times we need to take any number
                #S of images for)
                for set_num in range(len(self.calib_dict['dark_nums'])):
                        #S For the number of images in a set
                        for num in range(self.calib_dict['dark_nums'][set_num]):
                                #S Log the number of how many and the exposure time
                                self.logger.info("Taking arc image: %02.0f/%02.0f, at %.0f seconds"%(num+1,self.calib_dict['dark_nums'][set_num],self.calib_dict['dark_times'][set_num]))
                                #S Take it
                                self.takeSpectrum(self.calib_dict['dark_times'][set_num],'dark')
      
                
                #S Moving on to biases, make this the same as all other routines.
                for set_num in range(len(self.calib_dict['bias_nums'])):                
                        for num in range(self.calib_dict['bias_nums'][set_num]):
                                self.logger.info("Taking bias image: %02.0f/%02.0f at %.0f seconds"%(num+1,self.calib_dict['bias_nums'][set_num],self.calib_dict['bias_times'][set_num]))
                                self.takeSpectrum(self.calib_dict['bias_times'][set_num],'bias')

                return




        #S For now let's anticipate that 'target' is a dictionary containging everything we
        #S need to know about hte target in question
        #S 'name','ra','dec','propermotion','parallax',weight stuff,
        def take_rv_spec(self,target):
                pass
                                
	"""
	#S started outline for autofocus, pursuing different route.
	###
	#AUTOFOCUS
	###
	#S Small file will be needed for a few minor functions in the fitting process, etc
	#S This also seems like an odd spot to put the function, but trust me. Lots of intertwined 
	#S stuff we need to worry about
	def autofocus(self,telescope_number,af_num_steps=10,af_defocus_step=10):
	#	pass
		#S zero index the telenumber
		num = telescope_number - 1
		#S Default exposure time for autofocus, seconds
		af_exptime = 5
		#S Get the initial defocus to start at
		af_defocus = -(af_num_steps/2*af_defocus_step)
		#TODO Get last best focus, telescope getstatus?
		#TODO Similar procedure already exists, see other autofocus function in cdk700(?)
		#TODO any other relevant information we need

		#TODO move to a nice patch of sky, take test image. This isn't detailed in
		#TODO other function, and I think deserves a bit of thought. 
		#S begin_af is a really a flag to hold our position until we have all the details
		#S of the sequence figured out, like exposure time and sky position
		begin_af = False
		while not begin_af:
			aftest_file = self.takeImage(af_exptime,af_filter,af_name,telescope_num)
			aftest = self.cameras[num].af_imagefit(aftest_file)
			#S The check below seem like they could be consolidated, as it feels a bit redundant. Needs
			#S more thought.

			#S this is to check to see if the brightest star is greater by some amount than the background
			#S This is a concern for fitting, as getstars can find 'stars' that we can't fit. Need 
			#S to look into get stars more though...
			if aftest['max_diff'] < max_diff:
				af_exptime += 5
				continue
			#S I think this should be fittable stars more than anything. 
			if aftest['num_stars'] < num_stars:
				#S I think if we don't have enough stars after accounting for exptime, we should try and move
				#S Also, this definition gets a bit hairy. Is it just if we have a pixel in the small frame, 
				#S which is centered around the star centroid, above the median background of the image?
				#TODO Telescope move
				continue
			#S So not that we have 
		#TODO Determine if exptime, sky patch are good
		#TODO begin autofocus sequence
		for imnum in range(number_of_images):
			#S This takes the image for the autofocus, 
			af_name = 'afoc'+str(imnum)
			#S I'm not sure if this is how this works, or how we want to implemenet it.
			#S Presumably the defocus arguement is how far you want ti off of the current focus, 
			#S so this should be fine if we set it initially to the minimum of what we want to offset. 
			af_defocus += af_defocus_step
			filename = self.takeImage(af_exptime,af_filter,af_name,telescope_num,defocus=af_defocus)
			#S Need a function in imager_server to perform fitting stuff, return dictionary with the goods
			af_dict = self.cameras[num].af_imagefit(filename)
			fwhm_list.append(af_dict['median_fwhm'])
		#S Now we have a list of fwhm's, lets fit a quadratic to it. 
		#S We're going to have all of these fitting functions in another file
		new_best_focus = autofocus.fit_autofocus(fwhm_list)
		#S This will return a number or None(?)
		#S I think returning None if there is not a good fit might be a good 
		#S idea, but the only thing is what do we do if there isn't a good fit. 
		#S I think we could also use this function as the check for monotonic 
		#S increasing/decreasing. 
		if new_best_focus <> None:
		"""
			
if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
        if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	ctrl = control('control.ini',base_directory)

	# ctrl.doBias(1,2)
	# ctrl.takeImage(1,'V','test',2)
	# ctrl.testScript(2)
	
	# filters = ['B','I','ip','V']
	# ctrl.doSkyFlat(filters,False,2,2)
	# ctrl.doScience(2)
	
	
	
