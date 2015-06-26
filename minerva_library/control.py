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
from configobj import ConfigObj
sys.dont_write_bytecode = True

#Minerva library dependency
import env
import aqawan
import cdk700 
import imager
import spectrograph
import mail
import ephem
from get_all_centroids import *
import segments

class control:
	
#============Initialize class===============#
	
	def __init__(self,config,base):
		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.create_class_objects()
		
		self.logger_lock = threading.Lock()
		self.setup_loggers()
		self.telcom_enable()
		
	#create class objects needed to control Minerva system
	def create_class_objects(self):
	
		self.site = env.site('site_mtHopkins.ini',self.base_directory)
		self.spectrograph = spectrograph.spectrograph('spectrograph.ini',self.base_directory)
		
		self.domes = [
		aqawan.aqawan('aqawan_1.ini',self.base_directory),
		aqawan.aqawan('aqawan_2.ini',self.base_directory)]
	
		self.telescopes = [
		cdk700.CDK700('telescope_1.ini',self.base_directory),
		cdk700.CDK700('telescope_2.ini',self.base_directory),
		cdk700.CDK700('telescope_3.ini',self.base_directory),
		cdk700.CDK700('telescope_4.ini',self.base_directory)]
		
		self.cameras = [
		imager.imager('imager_t1.ini',self.base_directory),
		imager.imager('imager_t2.ini',self.base_directory),
		imager.imager('imager_t3.ini',self.base_directory),
		imager.imager('imager_t4.ini',self.base_directory)]
		
	def load_config(self):
		
		try:
			config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.logger_name = config['LOGNAME']
			self.observing = False
		except:
			print("ERROR accessing configuration file: " + self.config_file)
			sys.exit() 
			
	#create logger object and link to log file, if night is not specified, log files will go into /log/dump directory
	def setup_logger(self,night='dump'):
			
		log_path = self.base_directory + '/log/' + night
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
	def setup_loggers(self,night='dump'):
	
		self.logger_lock.acquire()
		self.setup_logger(night)
		for a in self.domes:
			a.setup_logger(night)
		for t in self.telescopes:
			t.setup_logger(night)
		for c in self.cameras:
			c.setup_logger(night)
		self.site.setup_logger(night)
		self.spectrograph.setup_logger(night)
		self.logger_lock.release()
		
	#enable sending commands to telcom
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
		
#==================Telescope control==================#
#block until command is complete
#operate telescope specified by num
#if num is not specified or outside of array range, 
#all enabled telescopes will execute command in parallel
#=====================================================#
		
	def telescope_initialize(self,num=0):
		if num >= 1 and num <= len(self.telescopes):
			self.telescopes[num-1].initialize()
		else:
			threads = [None]*len(self.telescopes)
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t] = threading.Thread(target = self.telescopes[t].initialize)
					threads[t].start()
			for t in range(len(self.telescopes)):
				if self.telcom_enabled[t] == True:
					threads[t].join()
					
	def telescope_autoFocus(self,num=0):
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
					
	def telescope_acquireTarget(self,ra,dec,num=0):
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
					
	def telescope_mountGotoAltAz(self,Alt,Az,num=0):
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
					
	def telescope_park(self,num=0):
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
			self.cameras[num-1].set_dataPath(night)
		else:
			threads = [None]*len(self.cameras)
			for t in range(len(self.cameras)):
				threads[t] = threading.Thread(target = self.cameras[t].set_dataPath,args=(night,))
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

		telescope_name = 'T(' + str(num) +'): '

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
		
	#open dome with weather check
	def domeOpen(self):
		if (datetime.datetime.utcnow() - self.domes[0].lastClose) < datetime.timedelta(minutes=20):
			self.logger.info('Domes closed at ' + str(self.domes[0].lastClose) + '; waiting 20 minutes for conditions to improve')
		else:
			if self.site.oktoopen():
				self.logger.debug('Weather is good; opening dome')
				return self.dome_open()
			else:
				if site.sunalt() < 6:
					self.logger.info('Weather still not ok; resetting timeout')
					self.domes[0].lastClose = self.domes[1].lastClose = datetime.datetime.utcnow()
		return False

	#periodically check weather condition, decide weather to open/close dome
	def domeControl(self):
		while self.observing:
			t0 = datetime.datetime.utcnow()
			if not self.site.oktoopen(open=True):
				self.dome_close()
			else:
				self.domeOpen()
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

		telescope_name = 'T(' + os.path.splitext(imageName)[0].split('.')[1][1] + '): '
		
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
		
		telescope_name = 'T(' + str(num) +'): '


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
		PA = math.acos(-float(hdr['CD1_1'])*3600.0/platescale) # position angle in radians
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
	


	#take one image based on parameter given, return name of the image, return 'error' if fail
	#image is saved on remote computer's data directory set by imager.set_data_path()
	def takeImage(self, exptime, filterInd, objname, camera_num=0):

		telescope_name = 'T(' + str(camera_num) +'): '
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
		f['RA'] = (ra, "Target RA (J2000)")
		f['DEC'] =  (dec, "Target Dec (J2000)")
		f['MOONRA'] = (moonra, "Moon RA (J2000)")    
		f['MOONDEC'] =  (moondec, "Moon Dec (J2000)")
		f['MOONPHAS'] = (moonphase, "Moon Phase (Fraction)")    
		f['MOONDIST'] =  (moonsep, "Distance between pointing and moon (deg)")
		f['PMODEL'] = (telescopeStatus.mount.pointing_model,"Pointing Model File")

		# Focuser Specific
		f['FOCPOS'] = (telescopeStatus.focuser.position,"Focus Position (microns)")

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
		if telescopeStatus.temperature == None:
			f['M1TEMP'] = ("UNKNOWN","Primary Mirror Temp (C)")
			f['M2TEMP'] = ("UNKNOWN","Secondary Mirror Temp (C)")
			f['M3TEMP'] = ("UNKNOWN","Tertiary Mirror Temp (C)")
			f['AMBTMP'] = ("UNKNOWN","Ambient Temp (C)")
			f['BCKTMP'] = ("UNKNOWN","Backplate Temp (C)")
		else:
			f['M1TEMP'] = (telescopeStatus.temperature.primary,"Primary Mirror Temp (C)")
			f['M2TEMP'] = (telescopeStatus.temperature.secondary,"Secondary Mirror Temp (C)")
			f['M3TEMP'] = (telescopeStatus.temperature.m3,"Tertiary Mirror Temp (C)")
			f['AMBTMP'] = (telescopeStatus.temperature.ambient,"Ambient Temp (C)")
			f['BCKTMP'] = (telescopeStatus.temperature.backplate,"Backplate Temp (C)")

		if self.site.weather != -1:
			# Weather station
			f['WJD'] = (str(self.site.weather['date']),"Last update of weather (UTC)")
			f['RAIN'] = (str(self.site.weather['wxt510Rain']),"Current Rain (mm?)")
			f['TOTRAIN'] = (str(self.site.weather['totalRain']),"Total rain since ?? (mm?)")
			f['OUTTEMP'] = (str(self.site.weather['outsideTemp']),"Outside Temperature (C)")
			f['SKYTEMP'] = (str(self.site.weather['relativeSkyTemp']),"Sky - Ambient (C)")
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
		telescope_name = 'T(' + str(camera_num) +'): '
		objectName = 'Bias'
		for x in range(num):
			filename = 'error'
			while filename =='error':
				self.logger.info(telescope_name + 'Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + '0' + ')')
				filename = self.takeImage(0,'V',objectName,camera_num)
			
	def doDark(self,num=11, exptime=60,camera_num=0):
		telescope_name = 'T(' + str(camera_num) +'): '
		objectName = 'Dark'
		for time in exptime:
			for x in range(num):
				filename = 'error'
				while filename == 'error':
					self.logger.info(telescope_name + 'Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + str(time) + ')')
					filename = self.takeImage(time,'V',objectName,camera_num)
		
	#doSkyFlat for specified telescope
	def doSkyFlat(self,filters,morning=False,num=11,telescope_num=0):

		telescope_name = 'T(' + str(telescope_num) +'): '
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
		telescope_name = 'T(' + str(num) +'): '


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
	def doScience(self,target,telescope_num = 0):

		telescope_name = 'T(' + str(telescope_num) +'): '
		
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
			try: telescope.acquireTarget(target['ra'],target['dec'],pa=pa)
			except: pass
			telescope.inPosition()
			telescope.autoFocus()
			return

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
							#reacquire target after waiting for dome to open
							telescope.acquireTarget(target['ra'],target['dec'])
						if datetime.datetime.utcnow() > target['endtime']: return
						if i < target['num'][j]:
							self.logger.info(telescope_name + 'Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
							filename = self.takeImage(target['exptime'][j], target['filter'][j], target['name'],telescope_num)
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

						        #reacquire target after waiting for dome to open
							telescope.acquireTarget(target['ra'],target['dec'])
						if datetime.datetime.utcnow() > target['endtime']: return
						self.logger.info(telescope_name + 'Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' + target['filter'][j] + ' band') 
						filename = self.takeImage(target['exptime'][j], target['filter'][j], target['name'],telescope_num)
						if target['selfguide'] and filename <> 'error': reference = self.guide('/Data/t' + str(telescope_num) + '/' + self.site.night + '/' + filename,reference)

	#prepare logger and set imager data path
	def prepNight(self,num=0,email=True):

		# reset the night at 10 am local
		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
			today = today + datetime.timedelta(days=1)
		night = 'n' + today.strftime('%Y%m%d')

		#set correct path for the night
		self.logger.info("Setting up directories for " + night)
		self.setup_loggers(night)
		self.imager_setDatapath(night,num)
	
		if email: mail.send('T' + str(num) + ' Starting observing','Love,\nMINERVA')

	def backup(self, num):
		
		dataPath = '/Data/t' + str(num) + '/' + self.site.night + '/'
		backupPath = '/home/minerva/backup/t' + str(num) + '/' + self.site.night + '/'
		if not os.path.exists(backupPath):
			os.mkdir(backupPath)

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
		self.logger.info("Copying schedule file from ./schedule/" + self.site.night + ".txt to " + dataPath)
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
			'relativeSkyTemp':[],
			'outsideTemp':[],
			'windSpeed':[],
			'windDirectionDegrees':[],
			#        'date':[],
			#        'sunAltitude':[],
			}
		for log in logs:
			with open(log,'r') as f:
				for line in f:
					if re.search('WARNING: ',line) or re.search("ERROR: ",line):
						if re.search('WARNING: ',line): errmsg = line.split('WARNING: ')[1].strip()
						else: errmsg = line.split('ERROR: ')[1].strip()
						if errmsg not in errors.keys():
							errors[errmsg] = 1
						else: errors[errmsg] += 1
					elif re.search('=',line):
						key = line.split('=')[-2].split()[-1]
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
		
		telescope_name = 'T(' + str(telescope_num) +'): '

		if telescope_num < 1 or telescope_num > len(self.telescopes):
			self.logger.error(telescope_name + 'invalid telescope index')
			return
			
		#set up night's directory
		self.prepNight(telescope_num)
		self.scheduleIsValid(telescope_num)

		# home and initialize the telescope
		self.telescopes[telescope_num-1].home()
		self.telescopes[telescope_num-1].home_rotator()
		self.telescopes[telescope_num-1].initialize_autofocus()
		time.sleep(360)

		# wait for the camera to cool down
		self.cameras[telescope_num-1].cool()

		CalibInfo,CalibEndInfo = self.loadCalibInfo(telescope_num)
		# Take biases and darks
		# wait until it's darker to take biases/darks
		readtime = 10.0

		bias_seconds = CalibInfo['nbias']*readtime+CalibInfo['ndark']*sum(CalibInfo['darkexptime']) + CalibInfo['ndark']*readtime*len(CalibInfo['darkexptime']) + 600.0
		biastime = self.site.sunset() - datetime.timedelta(seconds=bias_seconds)
		waittime = (biastime - datetime.datetime.utcnow()).total_seconds()
		if waittime > 0:
			# Take biases and darks (skip if we don't have time before twilight)
			self.logger.info(telescope_name + 'Waiting until darker before biases/darks (' + str(waittime) + ' seconds)')
			time.sleep(waittime)
			self.doBias(CalibInfo['nbias'],telescope_num)
			self.doDark(CalibInfo['ndark'], CalibInfo['darkexptime'],telescope_num)

		# Take Evening Sky flats
		flatFilters = CalibInfo['flatFilters']
		self.doSkyFlat(flatFilters, False, CalibInfo['nflat'],telescope_num)
		
		# Wait until nautical twilight ends 
		timeUntilTwilEnd = (self.site.NautTwilEnd() - datetime.datetime.utcnow()).total_seconds()
		if timeUntilTwilEnd > 0:
			self.logger.info(telescope_name + 'Waiting for nautical twilight to end (' + str(timeUntilTwilEnd) + 'seconds)')
			time.sleep(timeUntilTwilEnd)

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
		telescope_name = 'T(' + str(telescope_num) +'): '
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
		
		threads = [None]*len(self.telescopes)
		for t in range(len(self.telescopes)):
			threads[t] = threading.Thread(target = self.observingScript_catch,args = (t+1,))
			threads[t].start()
		for t in range(len(self.telescopes)):
			threads[t].join()
			
	#TODO:set up http server to handle manual commands
	def run_server(self):
		pass
		
if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
	ctrl = control('control.ini',base_directory)

	# ctrl.doBias(1,2)
	# ctrl.takeImage(1,'V','test',2)
	# ctrl.testScript(2)
	
	# filters = ['B','I','ip','V']
	# ctrl.doSkyFlat(filters,False,2,2)
	# ctrl.doScience(2)
	
	
	
