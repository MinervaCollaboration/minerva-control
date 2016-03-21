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
import numpy as np
from configobj import ConfigObj
sys.dont_write_bytecode = True

#Minerva library dependency
import env
import aqawan
import cdk700 
import imager
import fau
import spectrograph
import utils
import pdu
import mail
from get_all_centroids import *
import segments
import newauto 
from fix_fits import fix_fits
import copy
import rv_control
from plotweather import plotweather

# FAU guiding dependencies
import PID_test as pid
from read_guider_output import get_centroid

class control:
	
#============Initialize class===============#
	#S The standard init
	def __init__(self,config,base):#telescope_list=0,dome_control=1):
                #S This config file literally only contains the logger name I think.
		self.config_file = config
		self.base_directory = base
		#S Only sets logger name right now
		self.load_config()

		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
		
		#S See below, lots of new objects created here. 
		self.create_class_objects()
		
		self.logger_lock = threading.Lock()
#		self.setup_loggers()
		self.telcom_enable()
		
	#create class objects needed to control Minerva system
	def create_class_objects(self):
		#S Commenting put for operation on minervaMain
		#if socket.gethostname() == 'Kiwispec-PC':
                        #S Give some time for the spec_server to start up, get settled.
               #         time.sleep(20)


		#S NEED TO UNCOMMENT THE LOGGER, SEARCH FOR XXXXXXX
		self.spectrograph = spectrograph.spectrograph('spectrograph.ini',self.base_directory)
		#	#imager.imager('si_imager.ini',self.base_directory)
                self.domes = []
                self.telescopes = []
                self.cameras = []
		self.pdus = []
		self.site = env.site('site_mtHopkins.ini',self.base_directory)
		self.thermalenclosureemailsent = False

		for i in range(2):
			try:
				aqawanob = aqawan.aqawan('aqawan_' + str(i+1) + '.ini',self.base_directory)
				if aqawanob.heartbeat(): self.domes.append(aqawanob)
				else: self.logger.error("Failed to initialize Aqawan " + str(i+1))
			except:
				self.logger.exception("Failed to initialize Aqawan " +str(i+1))

		# initialize the 4 telescopes
		for i in range(4):
			try: 
				self.cameras.append(imager.imager('imager_t' + str(i+1) + '.ini',self.base_directory))
				self.telescopes.append(cdk700.CDK700('telescope_' + str(i+1) + '.ini',self.base_directory))
			except:
				self.logger.exception('T' + str(i+1) + ': Failed to initialize the imager')
		for i in range(5):
			self.pdus.append(pdu.pdu('apc_' + str(i+1) + '.ini',self.base_directory))
		self.pdus.append(pdu.pdu('apc_bench.ini',self.base_directory))


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
		self.night = utils.night()

	def update_logpaths(self,path):
		if not os.path.exists(path): os.mkdir(path)

		fmt = "%(asctime)s [%(filename)s:%(lineno)s,%(thread)d - %(funcName)s()] %(levelname)s: %(message)s"
                datefmt = "%Y-%m-%dT%H:%M:%S"
                formatter = logging.Formatter(fmt,datefmt=datefmt)
                formatter.converter = time.gmtime

		self.logger_lock.acquire()

		# control's logger
		for fh in self.logger.handlers: self.logger.removeHandler(fh)
		fh = logging.FileHandler(path + '/' + self.logger_name + '.log', mode='a')	
                fh.setFormatter(formatter)
		self.logger.addHandler(fh)

		for a in self.domes:
			for fh in a.logger.handlers: a.logger.removeHandler(fh)
			fh = logging.FileHandler(path + '/' + a.logger_name + '.log', mode='a')	
			fh.setFormatter(formatter)
			a.logger.addHandler(fh)
		for t in self.telescopes:
			for fh in t.logger.handlers: t.logger.removeHandler(fh)
			fh = logging.FileHandler(path + '/' + t.logger_name + '.log', mode='a')	
			fh.setFormatter(formatter)
			t.logger.addHandler(fh)
		for c in self.cameras:
			for fh in c.logger.handlers: c.logger.removeHandler(fh)
			fh = logging.FileHandler(path + '/' + c.logger_name + '.log', mode='a')	
			fh.setFormatter(formatter)
			c.logger.addHandler(fh)

		for fh in self.site.logger.handlers: self.site.logger.removeHandler(fh)
		fh = logging.FileHandler(path + '/' + self.site.logger_name + '.log', mode='a')	
		fh.setFormatter(formatter)
		self.site.logger.addHandler(fh)

		for fh in self.spectrograph.logger.handlers: self.spectrograph.logger.removeHandler(fh)
		fh = logging.FileHandler(path + '/' + self.spectrograph.logger_name + '.log', mode='a')	
		fh.setFormatter(formatter)
		self.spectrograph.logger.addHandler(fh)

		self.logger_lock.release()
		

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
				threads[t].name = 'A' + str(self.domes[t].num)
				threads[t].start()
			for t in range(len(self.domes)):
				threads[t].join()
				
	def dome_open(self,num=0,day=False):
		if num >= 1 and num <= len(self.domes):
			if day: self.domes[num-1].open_shutter(1)
			else: self.domes[num-1].open_both()
		else:
			threads = [None]*len(self.domes)
			for t in range(len(self.domes)):
				if t == 0:
					kwargs={'reverse' : True}
				elif t == 1:
					kwargs={'reverse' : False}
				if day:
					threads[t] = threading.Thread(target = self.domes[t].open_shutter,args=[1,])
				else:
					threads[t] = threading.Thread(target = self.domes[t].open_both,kwargs=kwargs)
				threads[t].name = 'A' + str(self.domes[t].num)
				threads[t].start()
			for t in range(len(self.domes)):
				threads[t].join()
		for t in self.domes:
			if t.isOpen() == False:
				return False
		return True
	def dome_close(self,num=0):
		if num >= 1 and num <= len(self.domes):
			self.domes[num-1].close_both()
		else:
			threads = [None]*len(self.domes)
			for t in range(len(self.domes)):
				threads[t] = threading.Thread(target = self.domes[t].close_both)
				threads[t].name = 'A' + str(self.domes[t].num)
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
	def telescope_initialize(self,tele_list = 0, tracking = True, derotate=True):
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
				kwargs['derotate']=derotate
				threads[t] = threading.Thread(target = self.telescopes[tele_list[t]].initialize,kwargs=kwargs)
				threads[t].name = 'T' + str(self.telescopes[tele_list[t]].num)
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
				threads[t].name = 'T' + str(self.telescopes[tele_list[t]].num)
                                threads[t].start()
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                threads[t].join()
                return

        #TODOACQUIRETARGET Needs to be switched to take dictionary arguement
#	def telescope_acquireTarget(self,ra,dec,tele_list = 0):
	def telescope_acquireTarget(self,target,tele_list = 0):
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
				#S i think this might act up due to being a dictionary, but well see. 
                                threads[t] = threading.Thread(target = self.telescopes[tele_list[t]].acquireTarget,args=(target))
				threads[t].name = 'T' + str(self.telescopes[tele_list[t]].num)
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
				threads[t].name = 'T' + str(self.telescopes[tele_list[t]].num)
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
				threads[t].name = 'T' + str(self.telescopes[tele_list[t]].num)
                                threads[t].start()
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]]:
                                threads[t].join()
                return


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
				threads[t].name = 'T' + str(self.cameras[t].telnum)
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
				threads[t].name = 'T' + str(self.cameras[t].telnum)
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
				threads[t].name = 'T' + str(self.cameras[t].telnum)
				threads[t].start()
			for t in range(len(self.cameras)):
				threads[t].join()
				
	def imager_compressData(self,num=0,night=None):
		#S need the night arguement to specify endNight operations on a past night
		if night == None:
			night = self.site.night
		kwargs = {}
		kwargs['night']=night
		if num >= 1 and num <= len(self.cameras):
			self.cameras[num-1].compress_data(night=night)
		else:
			threads = [None]*len(self.cameras)
			for t in range(len(self.cameras)):
				threads[t] = threading.Thread(target = self.cameras[t].compress_data)
				threads[t].name = 'T' + str(self.cameras[t].telnum)
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

        # run astrometry.net on imageName, update solution in header                                             
	def astrometry(self, imageName, rakey='RA', deckey='DEC',pixscalekey='PIXSCALE', pixscale=None):
		hdr = pyfits.getheader(imageName)

		if pixscale == None:
			pixscale = float(hdr[pixscalekey])
			
		try: ra = float(hdr[rakey])
		except: ra = ten(hdr[rakey])*15.0

		try: dec = float(hdr[deckey])
		except: dec = utils.ten(hdr[deckey])
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
		    ' --cpulimit 30' + \
		    ' --no-verify' + \
		    ' --crpix-center' + \
		    ' --no-fits2fits' + \
		    ' --no-plots' + \
		    ' --overwrite ' + \
		    imageName
#        ' --use-sextractor' + \ #need to install sextractor

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


	#S functions for the jnow to j2000 conversions
	def hours_to_rads(self,hours):
		return hours*15.*np.pi/180.
	def degs_to_rads(self,degrees):
		return degrees*np.pi/180.
	def rads_to_hours(self,rads):
		return rads*180./np.pi/15.
	def rads_to_degs(self,rads):
		return rads*180./np.pi

	def hourangle_calc(self,target,telnum=None):
		#S update the site time to the current utc time
		self.site.date = datetime.datetime.utcnow()
		#S convert the radian sideral time from the site to hours
		lst_hours = self.rads_to_hours(self.site.obs.sidereal_time())
		#S i have no idea what this magic does
		if 'ra' in target.keys():
			ha = lst_hours - target['ra']
		elif telnum <> None:
			telescopeStatus = self.telescopes[telnum-1].getStatus()
			ra = utils.ten(telescopeStatus.mount.ra_2000)
			ha = lst_hours - ra
		else:
			self.logger.info(target['name']+' does not have an RA for Hour Angle calc; assuming HA=0')
			ha = 0.
		#S put HA in range (0,24)
		if ha<0.:
			ha+=24.
		if ha>24.:
			ha-=24.
		#S put HA in range (-12,12)
		if ha>12.:
			ha = ha-24

	def jnow_to_j2000_pyephem(self, ra_rads, dec_rads):
		"""
		A bastardized version from Kevin, edited by Sam. The telescope 
		status has them already in degrees. I'm keeping the related
		functions just in case for future use, etc.

		Given apparent (Jnow) coordinates (ra in hours, dec in degrees),
		return J2000 coordinates as a tuple:
		(ra_hours, dec_degs)
		
		Uses PyEphem to do the calculation
		"""

		star = ephem.FixedBody()
#		star._ra = self.hours_to_rads(ra_app_hours)
		star._ra = ra_rads
#		star._dec = self.degs_to_rads(dec_app_degs)
		star._dec = dec_rads

		star._epoch = ephem.now()
		star.compute(when=ephem.J2000)
		return self.rads_to_hours(star.a_ra), self.rads_to_degs(star.a_dec)

	def j2000_to_jnow_pyephem(self, ra_j2000_hours, dec_j2000_degs):
		"""
		Given J2000 coordinates (ra in hours, dec in degrees),
		return Jnow coordinates as a tuple:
		(ra_hours, dec_degs)
		
		Uses PyEphem to do the calculation
		"""
		
		star = ephem.FixedBody()
		star._ra = self.hours_to_rads(ra_j2000_hours)
		star._dec = self.degs_to_rads(dec_j2000_degs)
		star.compute(epoch=ephem.now())
		return self.rads_to_hours(star.ra), self.rads_to_degs(star.dec)


	def getstars(self,imageName):
    
		d = getfitsdata(imageName)
		th = threshold_pyguide(d, level = 4)

		if np.max(d*th) == 0.0:
			return np.zeros((1,3))
    
		imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
		cc = centroid_all_blobs(imtofeed)

		return cc

	def doSpectra(self, target, tele_list):

		# if after end time, return
		if datetime.datetime.utcnow() > target['endtime']:
			self.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + "); skipping")
			return

		# if before start time, wait
		if datetime.datetime.utcnow() < target['starttime']:
			waittime = (target['starttime']-datetime.datetime.utcnow()).total_seconds()
			self.logger.info("Target " + target['name'] + " is before its starttime (" + str(target['starttime']) + "); waiting " + str(waittime) + " seconds")
			time.sleep(waittime)

		# if the dome isn't open, wait for it to open
		for dome in self.domes:
			while not dome.isOpen():
				if datetime.datetime.utcnow() > target['endtime']:
					self.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + ") while waiting for the dome to open; skipping")
					return
				time.sleep(60)

		# acquire the target and begin guiding on each telescope
                if type(tele_list) is int:
                        if (tele_list < 1) or (tele_list > len(self.telescopes)):
                                tele_list = [x+1 for x in range(len(self.telescopes))]
                        else:
                                tele_list = [tele_list]
                threads = [None] * len(tele_list)
                for t in range(len(tele_list)):
                        if self.telcom_enabled[tele_list[t]-1]:
                                #TODOACQUIRETARGET Needs to be switched to take dictionary arguement
                                #S i think this might act up due to being a dictionary, but well see.
                                threads[t] = threading.Thread(target = self.pointAndGuide,args=(target,tele_list[t]))
				threads[t].name = 'T' + str(self.telescopes[tele_list[t]-1].num)
                                threads[t].start()

		self.logger.info("Waiting for all telescopes to acquire")
		# wait for all telescopes to put target on their fibers (or timeout)
		acquired = False
		timeout = 300.0 # is this long enough?
		elapsedTime = 0.0
		t0 = datetime.datetime.utcnow()
		while not acquired and elapsedTime < timeout:
			acquired = True
			for i in range(len(tele_list)):
				self.logger.info("T" + str(tele_list[i]) + ": acquired = " + str(self.cameras[tele_list[i]-1].fau.acquired))
				if not self.cameras[tele_list[i]-1].fau.acquired: 
					self.logger.info("T" + str(tele_list[i]) + " has not acquired the target yet; waiting (elapsed time = " + str(elapsedTime) + ")")
					acquired = False
			time.sleep(1.0)
			elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
			
		# what's the right thing to do in a timeout? 
		# Try again? 
		# Go on anyway? (as long as one telescope succeeded?)
		# We'll try going on anyway for now...

		# begin exposure(s)
		for i in range(target['num'][0]):
			# make sure we're not past the end time
			if datetime.datetime.utcnow() > target['endtime']: 
				self.logger.info("target past its end time (" + str(target['endtime']) + '); skipping')
				self.stopFAU(tele_list)
				return
			
			while not self.domes[0].isOpen():
				self.logger.info("Waiting for dome to open")
				time.sleep(60.0)
				if datetime.datetime.utcnow() > target['endtime']: 
					self.logger.info("target past its end time (" + str(target['endtime']) + '); skipping')
					self.stopFAU(tele_list)
					return

			self.takeSpectrum(target)

		self.stopFAU(tele_list)
		return

	def stopFAU(self,tele_list):

		# set camera.fau.guiding == False to stop guiders
		self.logger.info("Stopping the guiding loop for all telescopes")
		for i in range(len(tele_list)):
			self.cameras[tele_list[i]-1].fau.guiding = False

		return


	def pointAndGuide(self, target, tel_num, backlight=False):

		try:
#			self.telescopes[tel_num-1].logger.info('Beginning autofocus on '+target['name'])
#			newauto.autofocus(self, tel_num, target=target)
			self.logger.info("T" + str(tel_num) + ": pointing to target")
			self.telescopes[tel_num-1].acquireTarget(target, derotate=False)
			self.telescopes[tel_num-1].logger.info('Beginning autofocus on '+target['name'])
#			newauto.autofocus(self, tel_num, target=target)
			newauto.autofocus(self, tel_num)

			if backlight:
				rv_control.backlight(self)
				backlit = glob.glob('/Data/t' + str(tel_num) + '/' + self.night + '/*backlight*.fits')
				if len(backlit) > 1:
					xfiber, yfiber = rv_control.find_fiber(backlit[-1])
					self.logger.info("T" + str(tel_num) + ": Fiber located at (x,y) = (" + str(xfiber) + "," + str(yfiber) + ")")
					camera.fau.xfiber = xfiber
					camera.fau.yfiber = yfiber
				else:
					self.logger.error("T" + str(tel_num) + ": failed to find fiber; using default of (x,y) = (" + str(camera.fau.xfiber) + "," + str(camera.fau.yfiber) + ")")


			self.logger.info("T" + str(tel_num) + ": beginning guiding")
			self.cameras[tel_num-1].fau.guiding=True
			self.fauguide(target,tel_num)
		except:
			self.logger.exception("T" + str(tel_num) + ": Pointing and guiding failed")
#			mail.send("Pointing and guiding failed","",level="serious")

	# Assumes brightest star is our target star!
	# *** will have exceptions that likely need to be handled on a case by case basis ***
	def fauguide(self, target, tel_num, guiding=True, xfiber=None, yfiber=None, acquireonly=False):

		telescope = self.telescopes[tel_num-1]
		camera = self.cameras[tel_num-1]
		camera.fau.acquired = False
		
		if xfiber <> None:
			camera.fau.xfiber = xfiber
		if yfiber <> None: 
			camera.fau.yfiber = yfiber

		p=pid.PID(P=np.array([camera.fau.KPx, camera.fau.KPy]),
			  I=np.array([camera.fau.KIx, camera.fau.KIy]),
			  D=np.array([camera.fau.KDx, camera.fau.KDy]),
			  Integrator_max = camera.fau.Imax,
			  Deadband = camera.fau.Dband,
			  Correction_max = camera.fau.Corr_max)
		p.setPoint((camera.fau.xfiber, camera.fau.yfiber))
		
		pfast=pid.PID(P=np.array([camera.fau.fKPx, camera.fau.fKPy]),
			      I=np.array([camera.fau.fKIx, camera.fau.fKIy]),
			      D=np.array([camera.fau.fKDx, camera.fau.fKDy]),
			      Integrator_max = camera.fau.fImax,
			      Deadband = camera.fau.fDband,
			      Correction_max = camera.fau.fCorr_max)
		pfast.setPoint((camera.fau.xfiber, camera.fau.yfiber))

		tvals=np.array([])
		xvals=np.array([])
		yvals=np.array([])
		npts=10000
		error = np.zeros((npts, 2))
		curpos_old = np.array([-1.0, -1])
		converged=False
		starttime2= time.time()
		lasttimestamp = -1
                
                #MAIN LOOP
		i=0
		while camera.fau.guiding:
			if i>npts:
				break
                        # Grab image data from FAU
			filename = self.takeFauImage(target, telescope_num=tel_num)

			dataPath = '/Data/t' + camera.telnum + '/' + self.night + '/'
#			imagedata = get_centroid(dataPath + filename, badpixelmask=camera.fau.badpix)
			#derive position in pixels
#			curpos = np.array((imagedata['xcen'],imagedata['ycen']))

			stars = self.getstars(dataPath + filename)

			if len(stars) < 1:#curpos[0] == -1 or curpos[1] == -1:
				self.logger.info("T" + str(tel_num) + ": no stars in imaging; skipping guide correction")
			else:

				ndx = np.argmax(stars[:,2])

				self.logger.info("T" + str(tel_num) + ": Found " + str(len(stars)) + " stars, using the star at (x,y)=(" + str(stars[ndx][0]) + "," + str(stars[ndx][1]) + ")")

				# include an arbitrary offset from the nominal position (experimental)
				offset_file = '/home/minerva/minerva-control/t' + str(tel_num) + '_fiber_offset.txt'
				if os.path.exists(offset_file):
					with open(offset_file) as fh:
						entries = fh.readline().split()
						xoffset = float(entries[0])
						yoffset = float(entries[1])
						self.logger.info("T" + str(tel_num) + ": offset file found, applying offset to fiber position (" + str(xoffset) + "," + str(yoffset) + ")")
				else:
					xoffset = 0.0
					yoffset = 0.0

				p.setPoint((camera.fau.xfiber+xoffset,camera.fau.yfiber+yoffset))
				pfast.setPoint((camera.fau.xfiber+xoffset,camera.fau.yfiber+yoffset))

				curpos = np.array([stars[ndx][0],stars[ndx][1]])
				tvals = np.append(tvals,i)
				xvals = np.append(xvals, curpos[0])
				yvals = np.append(yvals, curpos[1])

				filterx=camera.fau.filterdata(xvals, N=camera.fau.smoothing)
				filtery=camera.fau.filterdata(yvals, N=camera.fau.smoothing)
				filtercurpos=np.array([filterx, filtery])
				separation = camera.fau.dist(camera.fau.xfiber+xoffset-curpos[0], camera.fau.yfiber+yoffset-curpos[1])*camera.fau.platescale
				self.logger.info("T%i: Target is at (%f,%f), %f'' away from the fiber (%f,%f) -- tolerance is %f'"%(tel_num,curpos[0],curpos[1],separation,camera.fau.xfiber+xoffset,camera.fau.yfiber+yoffset,camera.fau.acquisition_tolerance))
#				self.logger.info("T" + str(tel_num) + ": Target is at (" + str(curpos[0]) + ',' + str(curpos[1]) + "), " + str(separation) + '" away from the fiber (' + str(camera.fau.xfiber) + "," + str(camera.fau.yfiber) ") -- tolerance is " + str(camera.fau.acquisition_tolerance) + '"')
 				if separation < camera.fau.acquisition_tolerance:
					self.logger.info("T" + str(tel_num) + ": Target acquired")
					camera.fau.acquired = True
					if acquireonly: return
				#else: camera.fau.acquired = False

				if separation < camera.fau.bp:
                                        #note units are arc-seconds here in the "if"
					updateval = p.update(filtercurpos)
					self.logger.info("T" + str(tel_num) + ": Using slow loop")
					fast = False
				else:
					self.logger.info("T" + str(tel_num) + ": Using fast loop")
					updateval = pfast.update(filtercurpos)
					fast = True

				# position angle on the sky
				# PA = parallactic angle - mechanical rotator position + field rotation offset
				parangle = telescope.parangle(useCurrent=True)
				offset = float(telescope.rotatoroffset[telescope.port['FAU']])
				PA = parangle - float(telescope.getStatus().rotator.position) + offset
				self.logger.info('T' + str(tel_num) + ': PA = '+str(PA))


				# Rotate the PID value by the negative of the rotation angle
				updateval= np.dot(camera.fau.rotmatrix(-PA), updateval)
				error[i,:] = np.array(p.error)
                
				# Slew the telescope
				telupdateval = updateval*camera.fau.platescale

				if guiding == True:
				#telescope.increment_alt_az_balanced(telupdateval[0],telupdateval[1])
					telescopeStatus = telescope.getStatus()
					dec = utils.ten(telescopeStatus.mount.dec_2000)
					telescope.mountOffsetRaDec(-telupdateval[0]/math.cos(dec*math.pi/180.0),-telupdateval[1])

					if fast:
						time.sleep(5)
					else:
						time.sleep(1)

				self.logger.debug("T" + str(tel_num) + ": PID LOOP: " + 
						  str(camera.fau.xfiber)+","+
						  str(camera.fau.yfiber)+","+
						  str(curpos[0])+","+
						  str(curpos[1])+","+
						  str(updateval[0])+","+
						  str(updateval[1])+","+
						  str(telupdateval[0])+","+
						  str(telupdateval[1])+","+
						  str(camera.fau.rotangle)+","+
						  str(guiding))

				self.logger.debug("T" + str(tel_num) + ": Curpos " + str(curpos[0])+"   "+str(curpos[1]))
				#self.logger.debug("Filtercurpos " +  filtercurpos)
				self.logger.debug("T" + str(tel_num) + ": distance from target: " +str(round(camera.fau.dist(camera.fau.xfiber+xoffset-curpos[0], camera.fau.yfiber+yoffset-curpos[1]),2)))
				self.logger.debug("T" + str(tel_num) + ": Updatevalue: " + str(updateval[0])+" "+str(updateval[1]))
				self.logger.debug("T" + str(tel_num) + ": Commanding update: " + str(telupdateval[0])+" "+str(telupdateval[1]))
				if i >50:
					meanx = np.mean((xvals)[50:])
					meany = np.mean((yvals)[50:])
					stdx  = np.std( (xvals)[50:])
					stdy  = np.std( (yvals)[50:])

					self.logger.debug("T" + str(tel_num) + ": Mean x position  " + str(meanx))
					self.logger.debug("T" + str(tel_num) + ": Std x position  " + str(stdx))
					self.logger.debug("T" + str(tel_num) + ": Mean y position  " + str(meany))
					self.logger.debug("T" + str(tel_num) + ": Std y position  " + str(stdy))
				else:
					self.logger.debug("T" + str(tel_num) + ": Building up statistics")

			i=i+1

		# The target is no longer acquired
		camera.fau.acquired = False
		return






		filename = self.fau.take_image(5)
		self.logger.info(telescope_name + "Extracting stars for " + filename)
		#self.getstars(filename)
		stars = self.getstars(filename)
		if len(stars[:,0]) ==  0:
			self.logger.error(telescope_name + "No stars in frame")
			return

		
		# proportional servo gain (apply this fraction of the offset)
		gain = 0.66

		# get the platescale from the header
		hdr = pyfits.getheader(filename)
		platescale = float(hdr['PIXSCALE'])
		dec = float(hdr['CRVAL2'])*math.pi/180.0 # declination in radians

		arg = max(min(-float(hdr['CD1_1'])*3600.0/platescale,1.0),-1.0)
		PA = math.acos(arg) # position angle in radians
		self.logger.info(telescope_name + "Image PA=" + str(PA))

		dx = fau.fiber[0] - stars[0][0]
		dy = fau.fiber[1] - stars[0][1]

		# adjust RA/Dec (PA needs to be calibrated)
		deltaRA = -(dx*math.cos(PA) - dy*math.sin(PA))*math.cos(dec)*platescale*gain
		deltaDec = (dx*math.sin(PA) + dy*math.cos(PA))*platescale*gain
		self.logger.info(telescope_name + "Adjusting the RA,Dec by " + str(deltaRA) + "," + str(deltaDec))
		telescope.mountOffsetRaDec(deltaRA,deltaDec)


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
        def ctrl_i2stage_move(self,locationstr = 'out', position=None):
                #S Sends command to begin i2stage movement, whcih will start
                #S a thread in the spectrograph server to move the stage to the
                #S corresponding location string.
		if position <> None:
			ndx = 0
			self.spectrograph.i2stage_movef(position)
			location = position
		else:
			ndx = 1
			self.spectrograph.i2stage_move(locationstr)
			location = locationstr

                #S Time out to wait for the stage to get to destination.
                timeout  = 60
                #S Start time to measure elapsed time of movement.
                start = datetime.datetime.utcnow()
                #S Just priming elapsed time for first time through 'while'
                elapsed_time = 0
                #S If we aren't at our target string AND elapsed time is less than the timeout.
                #S Note that this queries the position string, and compares to the requested. 
                while (self.spectrograph.i2stage_get_pos()[ndx] <> location) and (elapsed_time < timeout):
                        #S Giver her a second
                        time.sleep(1)
                        #S Update elapsed time
                        elapsed_time = (datetime.datetime.utcnow() - start).total_seconds()
                #S We exited the 'while' above, meaning one of the conditions became false.
                #S If the target string is our current string, we made it where we want to go. 
                if self.spectrograph.i2stage_get_pos()[ndx] == location:
                        #S Log some info dog
                        self.logger.info('I2 stage successfully moved to '+str(location)+' after first attempt.')
                        #S Returns nothing right now, and i think that's all we want.
                        return

#		print self.spectrograph.i2stage_get_pos()[ndx],location,self.spectrograph.i2stage_get_pos()[ndx] == location,float(self.spectrograph.i2stage_get_pos()[ndx]) == location
#		ipdb.set_trace()

                #S If we get here, the timeout was surpassed, and we need to try some troubleshooting.
                #S Our first action will be to send the move command again. no harm here.
                #S First, we'l log an error saying we're trying again.
                self.logger.error('I2 stage did not make it to ' + str(location) + ', trying to move again')
                #S Tell it to move
		if position <> None:
			self.spectrograph.i2stage_movef(position)
		else:
			self.spectrograph.i2stage_move(locationstr)
                #S Reset start and elapsed time. This uses same logic above.
                start = datetime.datetime.utcnow()
                elapsed_time = 0
                while (self.spectrograph.i2stage_get_pos()[ndx] <> location) and (elapsed_time < timeout):
                        time.sleep(1)
                        elapsed_time = (datetime.datetime.utcnow() - start).total_seconds()
                        
                if self.spectrograph.i2stage_get_pos()[ndx] == location:
                        self.logger.info('I2 stage successfully moved to '+str(location)+' after second attempt.')
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
		if position <> None:
			self.spectrograph.i2stage_movef(position)
		else:
			self.spectrograph.i2stage_move(locationstr)
                start = datetime.datetime.utcnow()
                elapsed_time = 0
                while (self.spectrograph.i2stage_get_pos()[ndx] <> location) and (elapsed_time < timeout):
                        time.sleep(1)
                        elapsed_time = (datetime.datetime.utcnow() - start).total_seconds()
                if self.spectrograph.i2stage_get_pos()[ndx] == location:
                        self.logger.info('I2 stage successfully moved to '+str(location)+' after third attempt.')
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
        def spec_equipment_check(self,target):#objname,filterwheel=None,template = False):

		kwargs = {
			'locationstr':'in',
			}
                #S Desired warmup time for lamps, in minutes
                #? Do we want seperate times for each lamp, both need to warm for the same rightnow
                WARMUPMINUTES = 0.0#10.
                #S Convert to lowercase, just in case.
                objname = target['name'].lower()
                #S Some logic to see what type of spectrum we'll be taking.

		#S Turn on the Iodine cell heater 
		self.spectrograph.cell_heater_set_temp(self.spectrograph.i2settemp)
		self.spectrograph.cell_heater_on()

                #S Decided it would be best to include a saftey to make sure the lamps
                #S were turned on.
                #S LAMPS NEED TO BE SHUT DOWN MANUALLY THOUGH.
#                if (objname == 'arc'):

#                if (objname == 'fiberflat'):

                
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
                if 'ThAr' in target['name']:
                        #S Move the I2 stage out of the way of the slit.
			kwargs['locationstr'] = 'out'
                        i2stage_move_thread = threading.Thread(target = self.ctrl_i2stage_move,kwargs=kwargs)
			i2stage_move_thread.name = "I2Stage"
                        i2stage_move_thread.start()
                        
                        #self.spectrograph.i2stage_move('out')

                        #Configure the lamps
#                        self.spectrograph.thar_turn_on()
#                        self.spectrograph.flat_turn_off()
                        self.spectrograph.led_turn_off()

                        #S Move filter wheel where we want it.
                        #TODO A move filterwheel function
                        #S Make sure the calibration shutter is open
                        #TODO Calibrtoin shutter open.
                        #S Time left for warm up
#                        warm_time = WARMUPMINUTES*60. - self.spectrograph.time_tracker_check(self.spectrograph.thar_file)
#                        print '\t\t\t\tWARM TIME IS '+str(warm_time)
                        #S Determine if the lamp has been on long enough, or sleep until it has.
#                        if (warm_time > 0.):
#                                time.sleep(warm_time)
#                                print 'Sleeping for '+str(warm_time) + ' for '+objname+' lamp.'
#                        else:
#                                time.sleep(0)
                        self.logger.info('Waiting on i2stage_move_thread')
                        i2stage_move_thread.join()
                            
                #S Flat exposures require the flat lamp to be on for ten minutes too.
                #S Same questions as for thar specs.
		elif (objname == 'slitflat'):
                        #S Move the LED in place with the Iodine stage
			kwargs['locationstr'] = 'flat'
                        i2stage_move_thread = threading.Thread(target = self.ctrl_i2stage_move,kwargs=kwargs)
			i2stage_move_thread.name = "I2Stage"
                        i2stage_move_thread.start()

                        # Configure the lamps
                        self.spectrograph.led_turn_on()
#                        self.spectrograph.thar_turn_off()
#                        self.spectrograph.flat_turn_off()
                        
			#S Move filter wheel where we want it.
                        #TODO A move filterwheel function
                        #S Make sure the calibration shutter is open
                        #TODO Calibrtoin shutter open.

                        #S Time left for warm up
#                        warm_time = WARMUPMINUTES*60. - self.spectrograph.time_tracker_check(self.spectrograph.led_file)
#                        print '\t\t\t\t WARM TIME IS '+str(warm_time)
#                        #S Make sure the lamp has been on long enough, or sleep until it has.
#                        if (warm_time > 0):
#                                time.sleep(warm_time)
#                                print 'Sleeping for '+str(warm_time) + ' for '+objname+' lamp.'
#                        else:
#                                time.sleep(0)
                        self.logger.info('Waiting on i2stage_move_thread')
                        i2stage_move_thread.join()
                elif 'fiberflat' in target['name']:
                        #S Move the I2 stage out of the way of the slit.
			if target['i2']:
				kwargs['locationstr'] = 'in'
			else:
				kwargs['locationstr'] = 'out'
                        i2stage_move_thread = threading.Thread(target = self.ctrl_i2stage_move,kwargs=kwargs)
			i2stage_move_thread.name = "I2Stage"
                        i2stage_move_thread.start()

                        #Configure the lamps
#                        self.spectrograph.thar_turn_off()
#                        self.spectrograph.flat_turn_on()
                        self.spectrograph.led_turn_off()
                                
                        #S Move filter wheel where we want it.
                        #TODO A move filterwheel function
                        #S Make sure the calibration shutter is open
                        #TODO Calibrtoin shutter open.

                        #S Time left for warm up
#                        warm_time = WARMUPMINUTES*60. - self.spectrograph.time_tracker_check(self.spectrograph.flat_file)
#                        print '\t\t\t\t WARM TIME IS '+str(warm_time)
                        #S Make sure the lamp has been on long enough, or sleep until it has.
#                        if (warm_time > 0):
#                                time.sleep(warm_time)
#                                print 'Sleeping for '+str(warm_time) + ' for '+objname+' lamp.'
#                        else:
#                                time.sleep(0)
                        self.logger.info('Waiting on i2stage_move_thread')
                        i2stage_move_thread.join()

                #S Conditions for both bias and dark.
                elif (objname == 'bias') or (objname == 'dark'):

                        #Configure the lamps
#                        self.spectrograph.thar_turn_off()
#                        self.spectrograph.flat_turn_off()
                        self.spectrograph.led_turn_off()

                        #S Make sure the calibrations shutter is closed.
                        #S Move the I2 stage out of the way of the slit.
                        #S Not sure if we need to move it out necessarily, but I think
                        #S this is better than having it randomly in 'flat' or 'in',
                        #S and will at least make things orderly.
			kwargs['locationstr'] = 'in'
                        i2stage_move_thread = threading.Thread(target = self.ctrl_i2stage_move,kwargs=kwargs)
			i2stage_move_thread.name = "I2Stage"
                        i2stage_move_thread.start()
                        #TODO Calibration shutter closed
                        self.logger.info('Waiting on i2stage_move_thread')
                        i2stage_move_thread.join()

                #S Let's do some science!
                #S The cell heater should be turned on before starting this, to give
                #S it time to warm up. It should really be turned on at the beginning
                #S of the night, but just a reminder.
                else:

			
                        #S Move the iodine either in or out, as requested
			if 'i2manualpos' in target.keys():
				kwargs['position'] = target['i2manualpos']
			elif target['i2']:
				kwargs['locationstr'] = 'in'
			else:
				kwargs['locationstr'] = 'out'
			i2stage_move_thread = threading.Thread(target = self.ctrl_i2stage_move,kwargs=kwargs)
			i2stage_move_thread.name = "I2Stage"
			i2stage_move_thread.start()
				
                        #Configure the lamps
#                        self.spectrograph.thar_turn_off()
#                        self.spectrograph.flat_turn_off()
                        self.spectrograph.led_turn_off()

                        #S This loop is a hold for the cell heater to be within a set tolerance
                        #S for the iodine stage's temperature. The least sigfig returned from the
                        #S heater is actually tenths, so this may be a little tight of a restriction.
                        #TODO revise tolerance of heater temp?
			start = datetime.datetime.utcnow()
			elapsedTime = 0.0
			timeout = 10
			i2temp = self.spectrograph.cell_heater_temp()
			
			if not i2temp: ipdb.set_trace()

			while (abs(self.spectrograph.i2settemp - i2temp) > self.spectrograph.i2temptol) and elapsedTime<timeout:
                                #S Give it some time to get there.
				self.logger.info("Waiting for the Iodine cell temperature (" + str(i2temp) + ") to reach its setpoint (" + str(self.spectrograph.i2settemp) + ")")
                                time.sleep(1)
				i2temp = self.spectrograph.cell_heater_temp()
				elapsedTime = (datetime.datetime.utcnow()-start).total_seconds()
                        
                        self.logger.info('Waiting on i2stage_move_thread')
			i2stage_move_thread.join()                      

                self.logger.info('Equipment check passed, continuing with '+objname+' exposure.')
                return
 
	def takeSpecBias(self, num):
		self.takeSpecDark(num, 0.0)

	def takeSpecDark(self, num, exptime):
		target = {}
		target['exptime'] = [exptime]
		target['spectroscopy'] = True
		if exptime == 0.0:
			target['name'] = 'Bias' 
		else: target['name'] = 'Dark'
		for i in range(num):
			self.takeSpectrum(target,tele_list = [])
	def takeSlitFlat(self, num, exptime):
		target = {}
		target['name'] = 'slitFlat'
		target['exptime'] = [exptime]
		target['spectroscopy'] = True
		for i in range(num):
			self.takeSpectrum(target, tele_list = [])

        def takeSpectrum(self,target,tele_list=0):#exptime,objname,template=False, expmeter=None,filterwheel=None):
		
                #S This is a check to ensure that everything is where/how it's supposed to be
                #S based on objname.
                self.spec_equipment_check(target)
                #start imaging process in a different thread
		if 'expmeter' in target.keys():
			kwargs = {'expmeter':target['expmeter']}
		else:
			kwargs = {'expmeter':None}
		kwargs['exptime'] = target['exptime'][0]
		kwargs['objname'] = target['name']

#		self.spectrograph.take_image(target['exptime'][0],target['name'])
		imaging_thread = threading.Thread(target = self.spectrograph.take_image, kwargs=kwargs)
		imaging_thread.name = "SI"
		imaging_thread.start()
                        
		f = self.getHdr(target,[1,2,3,4],[1,2])

		header = json.dumps(f)

		self.spectrograph.logger.info('Waiting for spectrograph imaging thread')
		# wait for imaging process to complete
		imaging_thread.join()
		
		# write header for image
		if self.spectrograph.write_header(header):
			self.spectrograph.logger.info('Finished writing spectrograph header')

			# rewrite the image to make it standard
			self.spectrograph.logger.info("Standardizing the FITS image")
			night = 'n' + datetime.datetime.utcnow().strftime('%Y%m%d')
			dataPath = '/Data/kiwispec/' + night + '/'
			fix_fits_thread = threading.Thread(target = fix_fits, args = (os.path.join(dataPath,self.spectrograph.file_name),))
			fix_fits_thread.name = 'SI'
			fix_fits_thread.start()
			
			return self.spectrograph.file_name
                #ipdb.set_trace()

		self.spectrograph.logger.error('takeSpectrum failed: ' + self.spectrograph.file_name)
		return 'error'

	#take one image based on parameter given, return name of the image, return 'error' if fail
	#image is saved on remote computer's data directory set by imager.set_data_path()
	#TODO camera_num is actually telescope_num
	def takeFauImage(self,target,telescope_num=0):
		telescope_name = 'T' + str(telescope_num) +': '

		#check camera number is valid
		if telescope_num > len(self.telescopes) or telescope_num < 0:
			return 'error'
		if telescope_num > 2: dome = 2
		else: dome = 1

		#S assign the camera.
		imager = self.cameras[telescope_num-1]
		imager.logger.info('starting the FAU imaging thread')

		#start imaging process in a different thread
		kwargs = {'exptime':target['fauexptime'],'objname':target['name']}
		imaging_thread = threading.Thread(target = imager.take_fau_image, kwargs = kwargs)
		imaging_thread.name = "T" + str(imager.telnum)
		imaging_thread.start()
		
		# Prepare header while waiting for imager to finish taking image
		f = self.getHdr(target, telescope_num, dome)
		header = json.dumps(f)
		
		imager.logger.info('waiting for imaging thread')
		# wait for imaging process to complete
		imaging_thread.join()
		
		# write header for image 
		if imager.write_header(header):
			imager.logger.info('finish writing image header')
			return imager.image_name()

		imager.logger.error('takeImage failed: ' + imager.image_name())
		return 'error'	

	def addSpectrographKeys(self, f):

		# blank keys will be filled in from the image when it's taken
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
                f['SET-TEMP'] = ("",'CCD temperature setpoint (C)')            # PARAM62 (in comments!)
                f['CCD-TEMP'] = ("",'CCD temperature at start of exposure (C)')# PARAM0
                f['BACKTEMP'] = ("","Camera backplate temperature (C)")        # PARAM1
                f['XPIXSZ'] = ("",'Pixel Width (microns after binning)')
                f['YPIXSZ'] = ("",'Pixel Height (microns after binning)')
                f['XBINNING'] = ("","Binning factor in width")                  # PARAM18
                f['YBINNING'] = ("","Binning factor in height")                 # PARAM22
                f['XORGSUBF'] = (0,'Subframe X position in binned pixels')      # PARAM16
                f['YORGSUBF'] = (0,'Subframe Y position in binned pixels')      # PARAM20
                f['IMAGETYP'] = ("",'Type of image')
                f['SITELAT'] = (str(self.site.obs.lat),"Site Latitude")
                f['SITELONG'] = (str(self.site.obs.lon),"East Longitude of the imaging location")
                f['SITEALT'] = (self.site.obs.elevation,"Site Altitude (m)")
                f['JD'] = (0.0,"Julian Date at the start of exposure (UTC)")
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
                f['GAIN'] = (1.30,"Detector gain (e-/ADU)")
                f['RDNOISE'] = (3.63,"Detector read noise (e-)")

                                        
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
                f['CCDMODE'] = ('UNKNOWN','CCD Readout Mode')
                f['FIBER'] = ('4-legged','Fiber Bundle Used')
                f['ATM_PRES'] = ('UNKNOWN','Atmospheric Pressure (mbar)')
		f['DETECTOR'] = ('SI850','Detector Name')

                '''
                # spectrograph information
                EXPTYPE = 'Time-Based'         / Exposure Type                                  
                '''


		# pressure in the spectrograph
		specpressure = -999.0
		night = 'n' + datetime.datetime.utcnow().strftime('%Y%m%d')
		try:
			with open('/Data/kiwilog/' + night + '/spec_pressure.log') as fh:
				fh.seek(-1024,2)
				line = fh.readlines()[-1].decode()
				specpressure = float(line.split(',')[-1].strip())
		except:
			self.logger.error("Error reading the spectrograph pressure")

		# pressure at the pump
		pumppressure = -999.0
		try:
			with open('/Data/kiwilog/' + night + '/pump_pressure.log') as fh:
				fh.seek(-1024,2)
				line = fh.readlines()[-1].decode()
				pumppressure = float(line.split(',')[-1].strip())
		except:
			self.logger.error("Error reading the pump pressure")
			

                f['SPECPRES'] = (specpressure,"spectrograph pressure (mbars)")
                f['PUMPPRES'] = (pumppressure,"vacuum pump pressure (mbars)")
                f['SPECHMID'] = ('UNKNOWN','Spectrograph Room Humidity (%)')

		# which valves are open; is the pump on?
		pumpvalve = self.pdus[5].pumpvalve.status()
		ventvalve = self.pdus[5].ventvalve.status()
		pump = self.pdus[4].pump.status()

		f['PUMPVALV'] = (pumpvalve,'Pump valve open?')
		f['VENTVALV'] = (ventvalve,'Vent valve open?')
		f['PUMPON'] = (pump,'Vacuum pump on?')

		# add the temperatures we log
		temp_controllers = ['A','B','C','D']
		for cont in temp_controllers:
			for i in range(4):
				filename = '%s/log/%s/temp.%s.%s.log'%(self.base_directory,night,cont,str(i+1))
				try:
					with open(filename,'r') as fh:
						lineList = fh.readlines()
						temps = lineList[-1].split(',')
						if temps[1] == "None" : temp = 'UNKNOWN'
						else: temp = float(temps[1])
						f['TEMP'+cont+str(i+1)] = (temp,temps[2].strip() + ' Temperature (C)')
				except:
					f['TEMP'+cont+str(i+1)] = ('UNKNOWN','Temperature (C)')
					

		# add the temperatures from the thermal enclosure log
		filename = self.base_directory + '/config/thermal_enclosure.ini'
		with open(filename,'rb') as fh:
			header = fh.readlines()[0].strip().split(',')
		filename = '/Data/thermallog/Thermal Enclosure Log ' + \
		    datetime.datetime.utcnow().strftime('%Y-%m-%d') + ' UTC.csv'
		
		if os.path.exists(filename):
			with open(filename,'rb') as fh:
				temps = fh.readlines()[-1].strip().split(',')
				for i in range(12):
					f['TEMPE'+str(i+1).zfill(2)] = (float(temps[i+4]), header[i] + ' Temperature (C)')
				f['ENCSETP'] = (float(temps[3]),'Thermal enclosure set point (C)')
			self.thermalenclosureemailsent = False
		else:
			if self.thermalenclosureemailsent:
				mail.send("Thermal enclosure logging died","Please restart me!")
			self.thermalenclosureemailsent = True

		# iodine temperature and set point
                f['I2TEMPA'] = (self.spectrograph.cell_heater_temp(),'Iodine Cell Actual Temperature (C)')
                f['I2TEMPS'] = (self.spectrograph.cell_heater_get_set_temp(),'Iodine Cell Set Temperature (C)')

		# iodine stage positions
		i2stagepos = self.spectrograph.i2stage_get_pos()
		try:
			f['I2POSAF'] = (i2stagepos[0],'Iodine Stage Actual Position (mm)')
			f['I2POSAS'] = (i2stagepos[1],'Iodine Stage Actual Position [string]')
                except:			
			f['I2POSAF'] = ('UNKNOWN','Iodine Stage Actual Position (mm)')
			f['I2POSAS'] = ('UNKNOWN','Iodine Stage Actual Position [string]')

		f['I2POSSS'] = (self.spectrograph.lastI2MotorLocation,'Iodine Stage Set Position [string]')
                f['SFOCPOS'] = ('UNKNOWN','KiwiSpec Focus Stage Position')
		
		# is the exposure meter and slit flat LED on?
		f['EXPMETER'] = (self.pdus[4].expmeter.status(),'Exposure meter powered?')
		f['LEDLAMP'] = (self.pdus[4].ledlamp.status(),'LED lamp powered?')
		
		f['XFIBER1'] = (self.cameras[0].fau.xfiber,'X position of fiber on FAU')
		f['YFIBER1'] = (self.cameras[0].fau.yfiber,'Y position of fiber on FAU')
		f['XFIBER2'] = (self.cameras[1].fau.xfiber,'X position of fiber on FAU')
		f['YFIBER2'] = (self.cameras[1].fau.yfiber,'Y position of fiber on FAU')
		f['XFIBER3'] = (self.cameras[2].fau.xfiber,'X position of fiber on FAU')
		f['YFIBER3'] = (self.cameras[2].fau.yfiber,'Y position of fiber on FAU')
		f['XFIBER4'] = (self.cameras[3].fau.xfiber,'X position of fiber on FAU')
		f['YFIBER4'] = (self.cameras[3].fau.yfiber,'Y position of fiber on FAU')

		return f


	def addWeatherKeys(self, f):

		# other threads can overwrite the weather
		weather = -1
		while weather == -1:
			self.site.getWeather()
			weather = copy.deepcopy(self.site.weather)

		# Weather station information
		f['WJD'] = (str(weather['date']),"Last update of weather (UTC)")
		f['RAIN'] = (weather['wxt510Rain'],"Current Rain since UT 00:00 (mm)")
		f['TOTRAIN'] = (weather['totalRain'],"Total yearly rain (mm)")
		f['OUTTEMP'] = (weather['outsideTemp'],"Outside Temperature (C)")
		f['MCLOUD'] = (weather['MearthCloud'],"Mearth Cloud Sensor (C)")
		f['HCLOUD'] = (weather['HATCloud'],"HAT Cloud Sensor (C)")
		f['ACLOUD'] = (weather['AuroraCloud'],"Aurora Cloud Sensor (C)")
		f['MINCLOUD'] = (weather['MINERVACloud'],"MINERVA Cloud Sensor (C)")
		f['DEWPOINT'] = (weather['outsideDewPt'],"Dewpoint (C)")
		f['WINDSPD'] = (weather['windSpeed'],"Wind Speed (mph)")
		f['WINDGUST'] = (weather['windGustSpeed'],"Wind Gust Speed (mph)")
		f['WINDIR'] = (weather['windDirectionDegrees'],"Wind Direction (Deg E of N)")
		f['PRESSURE'] = (weather['barometer'],"Outside Pressure (mbar)")
		f['SUNALT'] = (weather['sunAltitude'],"Sun Altitude (deg)")
		
		return f

	def addAqawanKeys(self,dome_list,f):
		
		if type(dome_list) is int:
			dome_list = [dome_list]

		for dome in dome_list:

			if len(dome_list) == 1:
				domestr = ""
			else: domestr = str(dome)

			if dome <> 1 and dome <> 2:
				self.logger.error("Invalid dome selected (" + str(dome) + ")")
				return f

			domeStatus = self.domes[dome-1].status()

			# Enclosure Specific
			f['AQSOFTV' + domestr] = (domeStatus['SWVersion'],"Aqawan software version number")
			f['AQSHUT1' + domestr] = (domeStatus['Shutter1'],"Aqawan shutter 1 state")
			f['AQSHUT2' + domestr] = (domeStatus['Shutter2'],"Aqawan shutter 2 state")
			f['INHUMID' + domestr] = (float(domeStatus['EnclHumidity']),"Humidity inside enclosure")
			f['DOOR1'   + domestr] = (domeStatus['EntryDoor1'],"Door 1 into aqawan state")
			f['DOOR2'   + domestr] = (domeStatus['EntryDoor2'],"Door 2 into aqawan state")
			f['PANELDR' + domestr] = (domeStatus['PanelDoor'],"Aqawan control panel door state")
			f['HRTBEAT' + domestr] = (int(domeStatus['Heartbeat']),"Heartbeat timer")
			f['AQPACUP' + domestr] = (domeStatus['SystemUpTime'],"PAC uptime (seconds)")
			f['AQFAULT' + domestr] = (domeStatus['Fault'],"Aqawan fault present?")
			f['AQERROR' + domestr] = (domeStatus['Error'],"Aqawan error present?")
			f['PANLTMP' + domestr] = (float(domeStatus['PanelExhaustTemp']),"Aqawan control panel exhaust temp (C)")
			f['AQTEMP'  + domestr] = (float(domeStatus['EnclTemp']),"Enclosure temperature (C)")
			f['AQEXTMP' + domestr] = (float(domeStatus['EnclExhaustTemp']),"Enclosure exhaust temperature (C)")
			f['AQINTMP' + domestr] = (float(domeStatus['EnclIntakeTemp']),"Enclosure intake temperature (C)")
			f['AQLITON' + domestr] = (domeStatus['LightsOn'],"Aqawan lights on?")

			# is the monitor powered on?
			f['MONITOR' + domestr] = (self.pdus[(dome-1)*2].monitor.status(),"Monitor on?")

		return f

	def addTelescopeKeys(self, target, tele_list, f):

		if type(tele_list) is int:
			tele_list = [tele_list]
		
                # loop over each telescope and insert the appropriate keywords
		moonpos = self.site.moonpos()
		moonra = moonpos[0]
		moondec = moonpos[1]
		moonphase = self.site.moonphase()
		f['MOONRA'] = (moonra, "Moon RA (J2000)")    
		f['MOONDEC'] =  (moondec, "Moon Dec (J2000)")
		f['MOONPHAS'] = (moonphase, "Moon Phase (Fraction)")    

                for telnum in tele_list:
			
			# if there's only one telescope (i.e., imager), no need to specify
			if len(tele_list) == 1:
				telstr = ""
			else:
				telstr = str(telnum)

			if telnum < 1 or telnum > 4:
				self.logger.error("Invalid telscope number (" + str(telnum) + ")")
				return f

			telescope = self.telescopes[int(telnum)-1]
			imager = self.cameras[int(telnum)-1]

			telescopeStatus = telescope.getStatus()
			telra =utils.ten(telescopeStatus.mount.ra_2000)*15.0 # J2000 degrees
			teldec = utils.ten(telescopeStatus.mount.dec_2000) # J2000 degrees
			if teldec > 90.0: teldec = teldec-360 # fixes bug in PWI's dec

			az = float(telescopeStatus.mount.azm_radian)*180.0/math.pi
			alt = float(telescopeStatus.mount.alt_radian)*180.0/math.pi
			airmass = 1.0/math.cos((90.0 - float(alt))*math.pi/180.0)
			moonsep = ephem.separation((telra*math.pi/180.0,teldec*math.pi/180.0),moonpos)*180.0/math.pi

			m3port = telescopeStatus.m3.port
			try:
				if m3port == '0': defocus = "UNKNOWN"
				else: defocus = (float(telescopeStatus.focuser.position) - float(telescope.focus[m3port]))/1000.0
			except:
				defocus = "UNKNOWN"
				self.logger.exception("What is going on?")

			rotpos = float(telescopeStatus.rotator.position)
			parang = telescope.parangle(useCurrent=True)
			try: rotoff = float(telescope.rotatoroffset[m3port])
			except: rotoff = "UNKNOWN"
			try: skypa = float(parang) + float(rotoff) - float(rotpos)
			except: skypa = "UNKNOWN"
			hourang = self.hourangle_calc(target,telnum=telnum)
			#hourang = telescope.hourangle(useCurrent=True)
			moonsep = ephem.separation((float(telra)*math.pi/180.0,float(teldec)*math.pi/180.0),moonpos)*180.0/math.pi

			# target ra, J2000 degrees
			if 'ra' in target.keys(): ra = target['ra']*15.0 
			else: ra = telra
                        
                        # target dec, J2000 degrees
			if 'dec' in target.keys(): dec = target['dec']
			else: dec = teldec

			if 'pmra' in target.keys(): pmra = target['pmra']
			else: pmra = 'UNKNOWN' 

			if 'pmdec' in target.keys(): pmdec = target['pmdec']
			else: pmdec = "UNKNOWN"

			if 'parallax' in target.keys(): parallax = target['parallax']
			else: parallax = "UNKNOWN"

			if 'rv' in target.keys(): rv = target['rv']
			else: rv = "UNKNOWN"

			# State can be:
			# INACTIVE -- Telescope is not requested for spectroscopy
			# FAILED -- Telescope was requested for spectroscopy but has failed
			# ACQUIRING -- Telescope was requested for spectroscopy but is still acquiring
			# GUIDING -- Telescope was requested for spectroscopy and is guiding
			# UNKNOWN -- We don't know; something went wrong
			if not imager.fau.guiding:
				state = 'INACTIVE'
			elif imager.fau.failed:
				state = 'FAILED'
			elif imager.fau.acquired and imager.fau.guiding:
				state = 'GUIDING'
			elif not imager.fau.acquired and imager.fau.guiding:
				state = 'ACQUIRING'
			else: state = 'UNKNOWN'

                        #S Get telescope temps
			try: m1temp = float(telescopeStatus.temperature.primary)
			except: m1temp = 'UNKNOWN'
			try: m2temp = float(telescopeStatus.temperature.secondary)
			except: m2temp = 'UNKNOWN'
			try: m3temp = float(telescopeStatus.temperature.m3)
			except: m3temp = 'UNKNOWN'
			try: ambtemp = float(telescopeStatus.temperature.ambient)
			except: ambtemp = 'UNKNOWN'
			try: bcktemp = float(telescopeStatus.temperature.backplate)
			except: bcktemp = 'UNKNOWN'
			    
			f['LST'] = (telescopeStatus.status.lst,"Local Sidereal Time")
			f['OBJECT'  + telstr] = target['name'] 
			f['FAUSTAT' + telstr] = (state,"State of the FAU at start of exposure")
			f['TELRA'   + telstr] = (telra,"Telescope RA (J2000 deg)")
			f['TELDEC'  + telstr] = (teldec,"Telescope Dec (J2000 deg)")
			f['RA'      + telstr] = (ra, "Solved RA (J2000 deg)")
			f['DEC'     + telstr] = (dec,"Solved Dec (J2000 deg)")
			f['TARGRA'  + telstr] = (ra, "Target RA (J2000 deg)")
			f['TARGDEC' + telstr] = (dec,"Target Dec (J2000 deg)")
			f['ALT'     + telstr] = (alt,'Telescope altitude (deg)')
			f['AZ'      + telstr] = (az,'Telescope azimuth (deg E of N)')
			f['AIRMASS' + telstr] = (airmass,"airmass (plane approximation)")
			f['HOURANG' + telstr] = (hourang,"Hour angle")
			f['PMRA'    + telstr] = (pmra, "Target Proper Motion in RA (mas/yr)")  
			f['PMDEC'   + telstr] = (pmdec, "Target Proper Motion in DEC (mas/yr)")  
			f['PARLAX'  + telstr] = (parallax, "Target Parallax (mas)")  
			f['RV'      + telstr] = (rv, "Target RV (km/s)")  
			
			# This will likely need to be calculated by the pipeline
			f['FLUXMID' + telstr] = ("UNKNOWN","Flux-weighted mid exposure time (JD_UTC)")

			f['PMODEL'  + telstr] = (telescope.model[m3port],"Pointing Model File")
			f['FOCPOS'  + telstr] = (float(telescopeStatus.focuser.position),"Focus Position (microns)")
			f['DEFOCUS' + telstr] = (defocus,"Intentional defocus (mm)")
			f['ROTPOS'  + telstr] = (rotpos,"Mechanical rotator position (degrees)")
			f['ROTOFF'  + telstr] = (rotoff,"Mechanical rotator offset (degrees)")
			f['PARANG'  + telstr] = (parang,"Parallactic Angle (degrees)")
			f['SKYPA'   + telstr] = (skypa,"Position angle on the sky (degrees E of N)")
			f['PORT'    + telstr] = (int(m3port),"Selected port on the telescope")
			f['OTAFAN'  + telstr] = (telescopeStatus.fans.on,"OTA Fans on?")			
			f['M1TEMP'  + telstr] = (m1temp,"Primary Mirror Temp (C)")
			f['M2TEMP'  + telstr] = (m2temp,"Secondary Mirror Temp (C)")
			f['M3TEMP'  + telstr] = (m3temp,"Tertiary Mirror Temp (C)")
			f['AMBTEMP' + telstr] = (ambtemp,"Ambient Temp (C)")
			f['BCKTEMP' + telstr] = (bcktemp,"Backplate Temp (C)")

			f['MOONDIS' + telstr] = (moonsep, "Distance between pointing and moon (deg)")

		return f

			
	def getHdr(self,target,tele_list,dome_list):

		#get header info into json format and pass it to imager's write_header method
		f = collections.OrderedDict()

		# Static Keywords
		f['SITELAT'] = str(self.site.obs.lat)
		f['SITELONG'] = (str(self.site.obs.lon),"East Longitude of the imaging location")
		f['SITEALT'] = (str(self.site.obs.elevation),"Site Altitude (m)")
		f['OBSERVER'] = ('MINERVA Robot',"Observer")

		if type(tele_list) is int:
			tel = "T" + str(tele_list)
		else: 
			if len(tele_list) == 1:
				tel = "T" + str(tele_list[0])
			else: tel = 'ALL'

		f['TELESCOP'] = (tel,"Telescope name")
		f['APTDIA'] = (700,"Diameter of the telescope in mm")
		f['APTAREA'] = (490000,"Collecting area of the telescope in mm^2")
                f['FOCALLEN'] = (4560.0,"Focal length of the telescope in mm")

                gitNum = subprocess.check_output(['git', "rev-list", "HEAD", "--count"]).strip()
		f['ROBOVER'] = (gitNum,"Git commit number for robotic control software")

		# add either the keywords specific to the spectrograph or imager
		if 'spectroscopy' in target.keys():
			if target['spectroscopy']:
				f = self.addSpectrographKeys(f)
			else: f = self.addImagerKeys(tele_list, f)
		else: f = self.addImagerKeys(tele_list, f)

		# telescope Specific
		f = self.addTelescopeKeys(target, tele_list, f)

		# enclosure Specific
		f = self.addAqawanKeys(dome_list, f)

		# add the header keys from the weather station
		f = self.addWeatherKeys(f)

		return f


	def addImagerKeys(self, imagernum, f):

		if type(imagernum) is not int:
			self.logger.error("invalid imager specified")
			return f			
		if imagernum < 1 or imagernum > 4:
			self.logger.error("invalid imager specified (" + str(imagernum) + ")")
			return f
		else: 
			imager = self.cameras[imagernum-1]
			telescope = self.telescopes[imagernum-1]
			
		# WCS
		platescale = imager.platescale/3600.0*imager.xbin # deg/pix
		PA = 0.0#float(telescopeStatus.rotator.position)*math.pi/180.0
		f['PIXSCALE'] = (str(platescale*3600.0),"Platescale in arc/pix, as binned")
		f['CTYPE1'] = ("RA---TAN","TAN projection")
		f['CTYPE2'] = ("DEC--TAN","TAN projection")
		f['CUNIT1'] = ("deg","X pixel scale units")
		f['CUNIT2'] = ("deg","Y pixel scale units")
		
		telescopeStatus = telescope.getStatus()
		telra = utils.ten(telescopeStatus.mount.ra_2000)*15.0 # J2000 degrees
		teldec = utils.ten(telescopeStatus.mount.dec_2000) # J2000 degrees
		if teldec > 90.0: teldec = teldec-360 # fixes bug in PWI's dec

		f['CRVAL1'] = (str(telra),"RA of reference point")
		f['CRVAL2'] = (str(teldec),"DEC of reference point")
		f['CRPIX1'] = (str(imager.xcenter),"X reference pixel")
		f['CRPIX2'] = (str(imager.ycenter),"Y reference pixel")
		f['CD1_1'] = str(-platescale*math.cos(PA))
		f['CD1_2'] = str(platescale*math.sin(PA))
		f['CD2_1'] = str(platescale*math.sin(PA))
		f['CD2_2'] = str(platescale*math.cos(PA))

		return f

	def takeImage(self, target, telescope_num=0):
		telescope_name = 'T' + str(telescope_num) +': '
		#check camera number is valid
		if telescope_num > len(self.telescopes) or telescope_num < 0:
			return 'error'
		if telescope_num > 2:
			dome = 2
		elif telescope_num > 0:
			dome = 1

		#S assign the camera.
		imager = self.cameras[telescope_num-1]
		imager.logger.info("starting imaging thread")

		#start imaging process in a different thread
		imaging_thread = threading.Thread(target = imager.take_image, args = (target['exptime'], target['filter'], target['name']))
		imaging_thread.name = 'T' + str(imager.telnum)
		imaging_thread.start()
		
		#Prepare header while waiting for imager to finish taking image
		f = self.getHdr(target, telescope_num, dome)

		header = json.dumps(f)

		imager.logger.info("waiting for imaging thread")

		# wait for imaging process to complete
		imaging_thread.join()
		
		# write header for image 
		if imager.write_header(header):
			imager.logger.info("finish writing image header")

			#S if the objname is not in the list of calibration or test names
			no_pa_list = ['bias','dark','skyflat','autofocus','testbias','test']
			if target['name'].lower() not in no_pa_list:
				# run astrometry asynchronously
				imager.logger.info("Running astrometry to find PA on " + imager.image_name())
				dataPath = '/Data/t' + str(telescope_num) + '/' + self.site.night + '/'
				astrometryThread = threading.Thread(target=self.getPA, args=(dataPath + imager.image_name(),), kwargs={})
				astrometryThread.name = "T" + str(imager.telnum)
				astrometryThread.start()
			return imager.image_name()

		imager.logger.error("takeImage failed: " + imager.image_name())
		return 'error'
	
	def doBias(self,num=11,telescope_num=0,objectName = 'Bias'):
		#S Need to build dictionary to get up to date with new takeimage
		biastarget = {}
		#S just ot chekc whether we canted to call the bias by another name.
		if objectName == 'Bias':
			biastarget['name'] = 'Bias'
		else:
			biastarget['name'] = objectName
		biastarget['filter'] = 'V'
		biastarget['exptime'] = 0
		for x in range(num):
			filename = 'error'
			while filename =='error':
				self.cameras[telescope_num-1].logger.info('Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + '0' + ')')
				#filename = self.takeImage(0,'V',objectName,telescope_num)
				#TODO for new takeimage
				filename = self.takeImage(biastarget,telescope_num)
			
	def doDark(self,num=11, exptime=60,telescope_num=0):
		#S Need to build dictionary to get up to date with new takeimage
		darktarget = {}
		darktarget['name'] = 'Dark'
		darktarget['filter'] = 'V'
		darktarget
		telescope_name = 'T' + str(telescope_num) +': '
		objectName = 'Dark'
		for time in exptime:
			darktarget['exptime'] = time
			for x in range(num):
				filename = 'error'
				while filename == 'error':
					self.cameras[telescope_num-1].logger.info('Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + str(time) + ')')
					#filename = self.takeImage(time,'V',objectName,telescope_num)
					#TODO for new takeimage
					filename = self.takeImage(darktarget,telescope_num)
		
	#doSkyFlat for specified telescope
	def doSkyFlat(self,filters,morning=False,num=11,telescope_num=0):
		#S an empty target dictionary for taking images
		target = {}
		#S all images named SkyFlat
		target['name']='SkyFlat'

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
		while not dome.isOpen():
			# exit if outside of twilight
			if self.site.sunalt() > maxSunAlt or self.site.sunalt() < minSunAlt: return
			self.logger.info("Dome closed; waiting for conditions to improve")
			time.sleep(30)

		# Now it's within 5 minutes of twilight flats
		self.logger.info(telescope_name + 'Beginning twilight flats')

		# make sure the telescope/dome is ready for obs
		if not telescope.initialize(tracking=True, derotate=True):
			telescope.recover()
		
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
				firstImage = True
				#S While the number of flats in the filter is less than required AND the dome is still open
				#TODO needs testing, watch out for this.
				while i < num and dome.isOpen():

					# Slew to the optimally flat part of the sky (Chromey & Hasselbacher, 1996)
					Alt = 75.0 # degrees (somewhat site dependent)
					Az = self.site.sunaz() + 180.0 # degrees
					if Az > 360.0: Az = Az - 360.0

					inPosition = False
					while not inPosition and dome.isOpen():

						self.logger.info(telescope_name + 'Slewing to the optimally flat part of the sky (alt=' + str(Alt) + ', az=' + str(Az) + ')')
						telescope.mountGotoAltAz(Alt,Az)
						# flats are only useful for imagers
						telescope.m3port_switch(telescope.port['IMAGER'])

						if not telescope.inPosition(alt=Alt,az=Az,m3port=telescope.port['IMAGER'],pointingTolerance=3600.0):
							telescope.recover()
						else: inPosition=True

					# Take flat fields
					filename = 'error'
					#S Set the filter name to the current filter
					target['filter']=filterInd
					#S update/get the exposure time
					target['exptime'] = exptime
					#while filename == 'error': filename = self.takeImage(exptime, filterInd, 'SkyFlat',telescope_num)
					#S new target dict implementation
					while filename == 'error' and dome.isOpen(): filename = self.takeImage(target,telescope_num)
					
					# determine the mode of the image (mode requires scipy, use mean for now...)
					mode = imager.getMode()
					self.logger.info(telescope_name + "image " + str(i+1) + " of " + str(num) + " in filter "\
								 + filterInd + "; " + filename + ": mode = " + str(mode) + " exptime = " \
								 + str(exptime) + " sunalt = " + str(self.site.sunalt()))

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
							self.logger.info(telescope_name + "Exposure time at minimum, image saturated, and "\
										 + "getting brighter; skipping remaining exposures in filter " + filterInd)
							break
							
					elif mode < 6.0*biasLevel:
						# Too little signal
						self.logger.info(telescope_name + "Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) + '; sun altitude=' + str(self.site.sunalt()) +
									 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
						imager.remove()
						i -= 1

						if exptime == maxExpTime and not morning:
							self.logger.info(telescope_name + "Exposure time at maximum, not enough counts, and "\
										 + "getting darker; skipping remaining exposures in filter " + filterInd)
							break
					if morning and self.site.sunalt() > maxSunAlt:
						self.logger.info(telescope_name + "Sun rising and greater than maxsunalt; skipping")
						break
					if not morning and self.site.sunalt() < minSunAlt:
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
#		dome.isOpen() = True
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

      		if target['name'] == 'pwi_autofocus':
                        #TODOACQUIRETARGET Needs to be switched to take dictionary arguement
#			try: telescope.acquireTarget(target['ra'],target['dec'],pa=pa)
			try: telescope.acquireTarget(target,pa=pa)
			except: pass
			telescope.inPosition(m3port=telescope.port['IMAGER'])
			telescope.autoFocus()
			return
		
		if target['name'] == 'autofocus':
#			try: telescope.acquireTarget(target,pa=pa)
#			except: pass
			if 'spectroscopy' in target.keys():
				fau = True
			else: 
				fau = False
			telescope.inPosition(m3port=telescope.port['IMAGER'])
			try:
				newauto.autofocus(self,telescope_num,fau=fau,target=target)
			except:
				self.telescopes[telscope_num-1].logger.exception('Failed in autofocus')
			return
		
                #TODOACQUIRETARGET Needs to be switched to take dictionary arguement
		# slew to the target
#		telescope.acquireTarget(target['ra'],target['dec'],pa=pa)
		telescope.acquireTarget(target,pa=pa)
		if 'spectroscopy' in target.keys():
			if target['spectroscopy']:
				newfocus = telescope.focus['FAU'] + target['defocus']*1000.0
			else:
				newfocus = telescope.focus['IMAGER'] + target['defocus']*1000.0
		else:
			newfocus = telescope.focus['IMAGER'] + target['defocus']*1000.0
		status = telescope.getStatus()
		if newfocus <> status.focuser.position:
			self.logger.info(telescope_name + "Defocusing Telescope by " + str(target['defocus']) + ' mm, to ' + str(newfocus))
			telescope.focuserMove(newfocus)
			time.sleep(0.5) # wait for move to register

		status = telescope.getStatus()
		while status.focuser.moving == 'True':
			self.logger.info(telescope_name + 'Focuser moving (' + str(status.focuser.position) + ')')
			time.sleep(0.3)
			status = telescope.getStatus()

		reference = None

		#S going to make a copy of the master target dict to modify for input to takeImage
		#S need to do so as we have lists of filters, exptimes, etc.
		temp_target = target.copy()

		# take one in each band, then loop over number (e.g., B,V,R,B,V,R,B,V,R)
		if target['cycleFilter']:
			for i in range(max(target['num'])):
				for j in range(len(target['filter'])):
					filename = 'error'
					while filename == 'error':
						if dome.isOpen() == False:
							while dome.isOpen() == False:
								self.logger.info(telescope_name + 'Enclosure closed; waiting for conditions to improve')
								time.sleep(30)
								if datetime.datetime.utcnow() > target['endtime']: return
							#TODOACQUIRETARGET Needs to be switched to take dictionary arguement
							#reacquire target after waiting for dome to open
#							telescope.acquireTarget(target['ra'],target['dec'])
							telescope.acquireTarget(target)
						if datetime.datetime.utcnow() > target['endtime']: return
						if i < target['num'][j]:

							#S update the temp_target dict with filters, exptimes
							temp_target['filter'] = target['filter'][j]
							temp_target['exptime'] = target['exptime'][j]

							#S make sure the telescope is in position
							if not telescope.inPosition(m3port=telescope.port['IMAGER']):
								self.logger.error('T'+str(telescope_num)+': not in position, reacquiring target')
								telescope.acquireTarget(target,pa=pa)
							self.logger.info(telescope_name + 'Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " \
											 + str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' \
											 + target['filter'][j] + ' band') 

							#S new target dict takeImage
							filename = self.takeImage(temp_target,telescope_num)
							#filename = self.takeImage(target['exptime'][j], target['filter'][j], target['name'],telescope_num)

							if target['selfguide'] and filename <> 'error': reference = self.guide('/Data/t' + str(telescope_num) + '/'\
																       + self.site.night + '/' + filename,reference)
					
					
		else:
			# take all in each band, then loop over filters (e.g., B,B,B,V,V,V,R,R,R) 
			for j in range(len(target['filter'])):
				# cycle by number
				for i in range(target['num'][j]):
					filename = 'error'
					while filename == 'error':
						if dome.isOpen() == False:
							while dome.isOpen() == False:
								self.logger.info(telescope_name + 'Enclosure closed; waiting for conditions to improve')
								time.sleep(30)
								if datetime.datetime.utcnow() > target['endtime']: return

                                                        #TODOACQUIRETARGET Needs to be switched to take dictionary arguement
						        #reacquire target after waiting for dome to open
#							telescope.acquireTarget(target['ra'],target['dec'])
							telescope.acquireTarget(target)
						if datetime.datetime.utcnow() > target['endtime']: return

						#S update the temp_target dict with filters, exptimes
						temp_target['filter'] = target['filter'][j]
						temp_target['exptime'] = target['exptime'][j]

						#S want to make sure we are on target for the image
						if not telescope.inPosition(m3port=telescope.port['IMAGER']):
							self.logger.debug('T'+str(telescope_num)+': not in position, reacquiring target')
							telescope.acquireTarget(target,pa=pa)
						self.logger.info(telescope_name + 'Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " \
									 + str(target['exptime'][j]) + ' second exposure of ' + target['name'] \
									 + ' in the ' + target['filter'][j] + ' band') 

						#S new target dict takeImage
						filename = self.takeImage(temp_target,telescope_num)
						#filename = self.takeImage(target['exptime'][j], target['filter'][j], target['name'],telescope_num)
						#S guide that thing
						if target['selfguide'] and filename <> 'error': reference = self.guide('/Data/t'+str(telescope_num)+'/'+self.site.night\
															       + '/' + filename,reference)

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


	def endNight(self, num=0, email=True, night=None, kiwispec=True):

		if os.path.exists('aqawan1.request.txt'): os.remove('aqawan1.request.txt')
		if os.path.exists('aqawan2.request.txt'): os.remove('aqawan2.request.txt')
		
		#S This implementation should allow you to specify a night you want to 'clean-up',
		#S or just run end night on the current night. I'm not sure how it will act
		#S if you endnight on an already 'ended' night though.
		#S IF YOU WANT TO ENTER A PAST NIGHT:
		#S make night='nYYYYMMDD' for the specified date.
		if night == None:
			night = self.site.night

		if kiwispec: 
			dataPath = '/Data/kiwispec/' + night + '/'
			objndx = 1
		else: 
			dataPath = '/Data/t' + str(num) + '/' + night + '/'
			objndx = 2

		# park the scope
		self.logger.info("Parking Telescope")
		self.telescope_park(num)
#		self.telescope_shutdown(num)

		# Compress the data
		self.logger.info("Compressing data")
		if kiwispec: pass
		else: self.imager_compressData(num,night=night)

		# Turn off the camera cooler, disconnect
#		self.logger.info("Disconnecting imager")
# 		self.imager_disconnect()

                #TODO: Back up the data
		if kiwispec: pass
		else: self.backup(num,night=night)

		# copy schedule to data directory
		if kiwispec: 
			schedulename = self.base_directory + "/schedule/" + night + ".kiwispec.txt"
			scheduleDest = dataPath + night + '.kiwispec.txt'
		else: 
			schedulename = self.base_directory + "/schedule/" + night + ".T" + str(num) + ".txt"
			scheduleDest = dataPath + night + '.T' + str(num) + '.txt'
		self.logger.info("Copying schedule file from " + schedulename + " to " + dataPath)
		try: shutil.copyfile(schedulename, scheduleDest)
		except: self.logger.exception("Could not copy schedule file from " + schedulename + " to " + scheduleDest)

		# copy server logs to data directory
		logs = glob.glob('/Data/serverlogs/t?/' + night + '/*.log')
		for log in logs:
			self.logger.info("Copying log file " + log + " to " + dataPath)
			try: shutil.copyfile(log, dataPath + os.path.basename(log))
			except: pass

		# copy logs to data directory
		logs = glob.glob(self.base_directory + "/log/" + night + "/*.log")
		for log in logs:
			self.logger.info("Copying log file " + log + " to " + dataPath)
			try: shutil.copyfile(log, dataPath + os.path.basename(log))
			except: pass
		logs = glob.glob(dataPath + "/*.log")

                #### create an observing report ####

		# summarize the observed targets
		filenames = glob.glob(dataPath + '/*.fits*')
		objects = {}
		for filename in filenames:
			obj = filename.split('.')[objndx]
			if not kiwispec and obj <> 'Bias' and obj <> 'Dark':
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
			'MINERVACloud':[],
			'outsideTemp':[],
			'windSpeed':[],
			'windDirectionDegrees':[],
			#        'date':[],
			#        'sunAltitude':[],
			}
#		ipdb.set_trace()

		# these messages contain variables; trim them down so they can be consolidated
		toospecific = [('The camera was unable to reach its setpoint','in the elapsed time'),
			       ('The process "MaxIm_DL.exe" with PID','could not be terminated'),
			       ("Stars are too elliptical, can't use",''),
			       ('The process "python.exe" with PID','could not be terminated'),
			       ('Slew failed to alt','az'),
			       ('Slew failed to J2000',''),
			       ('Telescope reports it is','away from the target postion'),
			       ('Not a valid JSON line',''),
			       ('malformed JSON',''),
			       ('Required key (filter) not present',''),
			       ('No schedule file',''),
			       ('Aqawan failed to close after ','seconds'),
			       ('The server has failed','times'),
			       ('Camera failed','times'),
			       ('taking image failed, image not saved',''),
			       ('Failed to open shutter 1: Success=FALSE, Estop active',''),
			       ('Required key (cycleFilter) not present',''),
			       ('Required key (nflatEnd) not present',''),
			       ('Required key (ndarkEnd) not present',''),
			       ('Required key (nbiasEnd) not present',''),
			       ('failed to save image',''),
			       ('Required key (guide) not present',''),
			       ('Required key (exptime) not present',''),
			       ('Required key (num) not present',''),
			       ('Failed to get hfr value',''),
			       ('Failed to open shutter 1: Success=FALSE, Unknown command',''),
			       ('Telescope reports it is','arcsec away from the requested postion'),
			       ('Coordinates out of bounds; object not acquired!',''),
			       ('File does not exist',''),
			       ('takeImage failed',''),
			       ('Failed to open shutter 2: Success=FALSE, Heartbeat timer expired',''),
			       ('The process "PWI.exe" with PID ','could not be terminated.'),
			       ('Could not copy schedule file',''),
			       ('Failed to open shutter 1: Success=FALSE, Heartbeat timer expired',''),
			       ('Failed to open shutter 2: Success=FALSE, Heartbeat timer expired','')]

		for log in logs:
			with open(log,'r') as f:
				for line in f:
					# search for WARNINGs or ERRORs
					if re.search('WARNING: ',line) or re.search("ERROR: ",line):
						if re.search('WARNING: ',line): errmsg = line.split('WARNING: ')[1].strip()
						else: errmsg = line.split('ERROR: ')[1].strip()
						
						if len(errmsg.split('active ')) > 1:
							errmsg = errmsg.split('active')[0] + 'active'

						# consolidate error messages with variables
						for genmsg in toospecific:
							if genmsg[0] in errmsg and genmsg[1] in errmsg:
								errmsg = genmsg[0] + ' ' + genmsg[1]

						if errmsg not in errors.keys():
							errors[errmsg] = 1
						else: errors[errmsg] += 1
					# Search for weather lines
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

		body += "\nSee the attached plot for tonight's weather. "+\
		    "The yellow shaded regions denote when the sun is up "+\
		    "(sunalt > -12 deg), the red shaded regions denote our "+\
		    "limits for closing when we're already open, the horizontal "+\
		    "lines next to the red regions are our limits for opening "+\
		    "when we're closed (the region in between is the deadband "+\
		    "to prevent rapid cycling of the roof when the weather "+\
		    "conditions are on the edge), the grey shaded regions are "+\
		    "when the dome was actually closed, and the blue line is the "+\
		    "value of the weather parameter denoted on the y axis.\n"

#		for key in weatherstats:
#			arr = [x[1] for x in weatherstats[key]]
#			if len(arr) > 0:
#				body += key + ': min=' + str(min(arr)) + \
#				    ', max=' + str(max(arr)) + \
#				    ', ave=' + str(sum(arr)/float(len(arr))) + '\n'

		body += "\nPlease see the webpage for movies and another diagnostics:\n" + \
		    "https://www.cfa.harvard.edu/minerva/site/" + night + "/movie.html\n\n" + \
		    "Love,\n" + \
		    "MINERVA"

		weatherplotname = plotweather(self,night=night)
		
		# email observing report
		if email: 
			if num == 0: subject="MINERVA done observing"
			else: subject = "T" + str(num) + ' done observing'
			mail.send(subject,body,attachment=weatherplotname)

		print body


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

		if not self.telescopes[telescope_num-1].initialize(tracking=False, derotate=False):
			self.telescopes[telescope_num-1].recover(tracking=False, derotate=False)

		#S Finally (re)park the telescope. 
		self.telescopes[telescope_num-1].park()

		#TODO A useless bias
		#S do a single bias to get the shutters to close, a cludge till we can get there and
		#S check things out ourselves.
		self.doBias(num=1,telescope_num=telescope_num,objectName='testBias')

		# wait for the camera to cool down
		self.cameras[telescope_num-1].cool()

		CalibInfo,CalibEndInfo = self.loadCalibInfo(telescope_num)
		# Take biases and darks
		# wait until it's darker to take biases/darks
		readtime = 10.0

		# turn off both monitors
		self.logger.info('Turning off monitors')
		try: self.pdus[0].monitor.off()
		except: self.logger.exception("Turning off monitor in aqawan 1 failed")
		try: self.pdus[2].monitor.off()
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
		if not self.telescopes[telescope_num-1].initialize(tracking=True, derotate=True):
			self.telescopes[telescope_num-1].recover(tracking=True, derotate=True)
		flatFilters = CalibInfo['flatFilters']
		self.doSkyFlat(flatFilters, False, CalibInfo['nflat'],telescope_num)
		
		
		# Wait until nautical twilight ends 
		timeUntilTwilEnd = (self.site.NautTwilEnd() - datetime.datetime.utcnow()).total_seconds()
		if timeUntilTwilEnd > 0:
			self.logger.info(telescope_name + 'Waiting for nautical twilight to end (' + str(timeUntilTwilEnd) + 'seconds)')
			time.sleep(timeUntilTwilEnd)

		if telescope_num > 2: dome = self.domes[1]
		else: dome = self.domes[0]

		while not dome.isOpen() and datetime.datetime.utcnow() < self.site.NautTwilBegin():
			self.logger.info(telescope_name + 'Enclosure closed; waiting for conditions to improve')
			time.sleep(60)

		# find the best focus for the night
		if datetime.datetime.utcnow() < self.site.NautTwilBegin():
			self.logger.info(telescope_name + 'Beginning autofocus')
#			self.telescope_intiailize(telescope_num)

			#S this is here just to make sure we aren't moving
#			# DON'T CHANGE PORTS (?)
#			self.telescopes[telescope_num-1].inPosition(m3port=self.telescopes[telescope_num-1].port['IMAGER'])
			self.telescopes[telescope_num-1].inPosition()#m3port=self.telescopes[telescope_num-1].port['IMAGER'])

			if telescope_num == 3: spectroscopy=True
			else: spectroscopy=False

#			self.telescope_autoFocus(telescope_num)
			newauto.autofocus(self,telescope_num,fau=spectroscopy)

		# read the target list
		with open(self.base_directory + '/schedule/' + self.site.night + '.T' + str(telescope_num) + '.txt', 'r') as targetfile:
			next(targetfile) # skip the calibration headers
			next(targetfile) # skip the calibration headers
			for line in targetfile:
				target = self.parseTarget(line)
				if target <> -1:

					# truncate the start and end times so it's observable
					utils.truncate_observable_window(self,target)

					if target['starttime'] < target['endtime']:
						if 'spectroscopy' in target.keys():
							if target['spectroscopy']:
								# only one telescope for now...
								rv_control.doSpectra(self,target,[telescope_num])
							else:
								self.doScience(target,telescope_num)
						else:
							self.doScience(target,telescope_num)
					else:
						self.logger.info(telescope_name + target['name']+ ' not observable; skipping')
						
						
		# Take Morning Sky flats
		# Check if we want to wait for these
		#S got rid of this check because domes were closing while other telescopes were observing.
		if True:   #CalibInfo['WaitForMorning']:
			sleeptime = (self.site.NautTwilBegin() - datetime.datetime.utcnow()).total_seconds()
			if sleeptime > 0:
				self.logger.info(telescope_name + 'Waiting for morning flats (' + str(sleeptime) + ' seconds)')
				time.sleep(sleeptime)
			self.doSkyFlat(flatFilters, True, CalibInfo['nflat'],telescope_num)

		# Want to close the aqawan before darks and biases
		# closeAqawan in endNight just a double check
		#S I think we need a way to check if both telescopes are done observing, even if one has
		#S ['waitformorning']==false
		self.telescope_park(telescope_num)

		# all done; close the domes
		if os.path.exists('aqawan1.request.txt'): os.remove('aqawan1.request.txt')
		if os.path.exists('aqawan2.request.txt'): os.remove('aqawan2.request.txt')

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
			while dome.isOpen() and (datetime.datetime.utcnow()-t0).total_seconds() < timeout:
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
	
	def domeControl_catch(self,day=False):
		try:
			self.domeControl(day=day)
		except Exception as e:
			self.logger.exception('DomeControl thread died: ' + str(e.message) )
			body = "Dear benevolent humans,\n\n" + \
			    'I have encountered an unhandled exception which has killed the dome control thread. The error message is:\n\n' + \
			    str(e.message) + "\n\n" + \
			    "Check control.log for additional information. Please investigate, consider adding additional error handling, and restart 'main.py'. The heartbeat will close the domes, but please restart.\n\n" + \
			    "Love,\n" + \
			    "MINERVA"
			mail.send("DomeControl thread died",body,level='serious')
			sys.exit()

	def specCalib(self,nbias=11,ndark=11,nflat=11,darkexptime=300,flatexptime=1):
		self.takeSpecBias(nbias)
		self.takeSpecDark(ndark, darkexptime)
		self.takeSlitFlat(nflat, flatexptime)

	def specCalib_catch(self):
		try:
			self.specCalib()
		except Exception as e:
			self.logger.exception('specCalib thread died: ' + str(e.message) )
                        body = "Dear benevolent humans,\n\n" + \
                            'I have encountered an unhandled exception which has killed the specCalib control thread. The error message is:\n\n' + \
                            str(e.message) + "\n\n" + \
			    "Check control.log for additional information. Please investigate, consider adding additional error handling, and restart 'main.py\n\n'" + \
                            "Love,\n" + \
                            "MINERVA"
                        mail.send("specCalib thread died",body,level='serious')
                        sys.exit()

	def observingScript_all(self):
		with open('aqawan1.request.txt','w') as fh:
			fh.write(str(datetime.datetime.utcnow()))

		with open('aqawan2.request.txt','w') as fh:
			fh.write(str(datetime.datetime.utcnow()))



		# python bug work around -- strptime not thread safe. Must call this once before starting threads
		junk = datetime.datetime.strptime('2000-01-01 00:00:00','%Y-%m-%d %H:%M:%S')

		threads = [None]*len(self.telescopes)
		self.logger.info('Starting '+str(len(self.telescopes))+ ' telecopes.')
		for t in range(len(self.telescopes)):
			threads[t] = threading.Thread(target = self.observingScript_catch,args = (t+1,))
			threads[t].name = 'T' + str(self.telescopes[t].num)
			threads[t].start()

#		speccalib_thread = threading.Thread(target=self.specCalib_catch)
#		speccalib_thread.start()
			       
		for t in range(len(self.telescopes)):
			threads[t].join()
#		speccalib_thread.join()
			
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
                #TODO I htink prepNight needs to be run for each scope
                #XXX self.prepNight()
                #S Initialize ALL telescopes
                self.Telescope_initialize
                #S Spec CCD calibration process
#                self.spec_calib_time()
#                self.spec_calibration()
              

		


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
		return
                #S Readout time for the spec CCD, seconds
                READOUTTIME = 21.6
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
                        
                #S Turn ThAr off, but I think it would be caught by later exposure conditions
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

	def ten(self,string):
                array = string.split()
                if "-" in array[0]:
                        return float(array[0]) - float(array[1])/60.0 - float(array[2])/3600.0
                return float(array[0]) + float(array[1])/60.0 + float(array[2])/3600.0
                                

	#S started outline for autofocus, pursuing different route.
	###
	#AUTOFOCUS
	###
	#S Small file will be needed for a few minor functions in the fitting process, etc
	#S This also seems like an odd spot to put the function, but trust me. Lots of intertwined 
	#S stuff we need to worry about
	def autofocus_step(self,telescope_num,newfocus,af_exptime,af_filter="V",m3port='1'):
		af_target={}
		af_target['name'] = 'autofocus'
		af_target['exptime'] = af_exptime
		af_target['filter'] = af_filter
		telescope = self.telescopes[telescope_num-1]
		status = telescope.getStatus()
		if newfocus <> status.focuser.position:
			telescope.logger.info('T'+str(telescope_number) + ": Defocusing Telescope by " \
						      + str(step) + ' mm, to ' + str(newfocus))
			telescope.focuserMove(newfocus)
			#S Needed a bit longer to recognize focuser movement, changed from 0.3
			time.sleep(.5)

		#S Make sure everythin is in position, namely that focuser has stopped moving
		telescope.m3port_switch(m3port=m3port)
		#S Set the name for the autofocus image
		af_name = 'autofocus'

		#S Take image, recall takeimage returns the filename of the image. we have the datapath from earlier
		#imagename = self.takeImage(af_exptime,af_filter,af_name,telescope_num=telescope_number)
		if telescope.port['IMAGER'] == m3port:
			imagename  = self.takeImage(af_target, telescope_num=telescope_num)
		elif telescope.port['FAU'] == m3port:
			imagename  = self.takeFauImage(af_target, telescope_num=telescope_num)

		imagenum = (imagename.split('.')[4])
		#S Sextract this guy, put in a try just in case. Defaults should be fine, which are set in newauto. NOt sextrator defaults
		try: 
			catalog = utils.sextract(datapath,imagename)
			self.logger.debug('T' + str(telescope_number) + ': Sextractor success on '+catalog)
		except: 
			self.logger.exception('T' + str(telescope_number) + ': Sextractor failed on '+catalog)
		try:
			median, stddev, numstar = newauto.get_hfr_med(catalog)
			self.logger.info('T'+str(telescope_number)+': Got hfr value from '+catalog)
			return median, stddev, numstar, imagenum
		except:
			self.logger.exception('T' + str(telescope_number) + ': Failed to get hfr value from '+catalog)		
			return -999, 999, 0, imagenum


	def new_autofocus(self,telescope_number,num_steps=5,defocus_step=0.4,af_exptime=5,af_filter="V"):

		#S get the telescope we plan on working with
		telescope = self.telescopes[telescope_number-1]
		#S our data path
		datapath = '/Data/t' + str(telescope_number) + '/' + self.site.night + '/'

		# wait for dome to be open
		if telescope_number > 2:
			dome = self.domes[1]
		else:
			dome = self.domes[0]
		#S Get current time for measuring timeout
		t0 = datetime.datetime.utcnow()
		"""
#		
		#S Loop to wait for dome to open, cancels afeter ten minutes 
		while dome.isOpen() == False:
			self.logger.info('T' + str(telescope_number) + ': Enclosure closed; waiting for dome to open')
			timeelapsed = (datetime.datetime.utcnow()-t0).total_seconds()
			if timeelapsed > 600: 
				self.logger.info('T' + str(telescope_number) + ': Enclosure still closed after 10 minutes; skipping autofocus')
				return
			time.sleep(30)
#		

		#S Initialize telescope, we want tracking ON
#		telescope.initialize(tracking=False)
		telescope.initialize(tracking=True)

		#S make array of af_defocus_steps
		defsteps = np.linspace(-defocus_step*(num_steps/2),defocus_step*(num_steps/2),num_steps)
		#S Array of new positions for the focuser, using this rahter than step. 
		pos_arr = defsteps*1000 + telescope.focus
		old_best_focus = telescope.focus

		#S Just need empty np.arrays for the fwhm/hfr and std to append to. made FOCUSMEASure_LIST 
		#Sbecause we don't necessarily know which value we want yet.
		imagenum_arr = np.array(())
		focusmeas_arr = np.array(())
		stddev_arr = np.array(())
		numstar_arr = np.array(())

		#S Actual autofocus sequence
		for position in pos_arr:
			med, std, numstars, imagenum = self.autofocus_step(telescope_num,position,af_exptime,af_filter)
			focusmeas_arr = np.append(focusmeas_arr,med)
			stddev_arr = np.append(stddev_arr,std)
			numstar_arr = np.append(numstar_arr,numstars)
			imagenum_arr = np.append(imagenum_arr,imagenum)
		"""
		#S A value for the threshold of the focus change between runs to determine a good stopping point.
		#TODO make sure units are correct
		MAXDELTA = 100
		#S Want to make sure enter this loop
		delta_focus = 2*MAXDELTA
		#S Maximum number of steps we want to take
		MAXSTEPS = 10
		new_best_focus=200
		old_best_focus=1
		focusmeas_arr = np.array([25.,16.,9.,4.])
		stddev_arr = np.array([1,1,1,1])
		pos_arr = np.array([5.,4.,3.,2.])
		numstar_arr=np.array([1,1,1,1])
		imagenum_arr=np.array([1,1,1,1])
		weight_list=np.array([1.,1.,1.,1.])
		defocus_step = 1e-3
#		ipdb.set_trace()
		med=1
		std=1
		numstars=1
		imagenum=1
		i=1
		while (len(pos_arr)<MAXSTEPS) and (delta_focus>MAXDELTA):
			goodind = np.where(focusmeas_arr <> -999)[0]
			try:
				print 'here',len(pos_arr),len(focusmeas_arr)
				print pos_arr
				print focusmeas_arr
				time.sleep(5)
				new_best_focus,fitcoeffs = newauto.fitquadfindmin(pos_arr[goodind],focusmeas_arr[goodind],\
											  weight_list=stddev_arr[goodind],\
											  logger=self.logger,telescope_num=telescope_number)
				#S Find the change in the focus from the last fit
				delta_focus = np.absolute(old_best_focus - new_best_focus)

				if delta_focus>MAXDELTA:
					print 'in delta focus loop'
					goodind = np.where(focusmeas_arr <> -999)[0]
					#S if there are more points above the new focus then there are below
					#TODO this seems sketchy, we could do flipflopping to more above and below, spending a lot of time 
					#TODO moving the focuser around.
					print len(np.where(pos_arr<new_best_focus)[0])<len(np.where(pos_arr>new_best_focus)[0])
					print len(np.where(pos_arr<new_best_focus)[0])>len(np.where(pos_arr>new_best_focus)[0])
					if len(np.where(pos_arr<new_best_focus)[0])<len(np.where(pos_arr>new_best_focus)[0]):	
					
						telescope.logger.info('Fewer points below focus and not within delta, adding a new min point')
						pos_arr = np.append(pos_arr, (pos_arr[goodind].min()-defocus_step*1000.))
						#S pos_arr.min() should be the point we just added, but need to double check this
						#med, std, numstars, imagenum = self.autofocus_step(telescope_num,pos_arr.min(),af_exptime,af_filter)
						continue

					elif len(np.where(pos_arr<new_best_focus)[0])>len(np.where(pos_arr>new_best_focus)[0]):	
						telescope.logger.info('Fewer points above focus and not within delta, adding a new max point')
						pos_arr = np.append(pos_arr, (pos_arr[goodind].min()+defocus_step*1000.))
						#S pos_arr.min() should be the point we just added, but need to double check this
						#med, std, numstars, imagenum = self.autofocus_step(telescope_num,pos_arr.min(),af_exptime,af_filter)
						continue
					else:
						print 'herheherhehrehrehe'


				focusmeas_arr = np.append(focusmeas_arr,med)
				stddev_arr = np.append(stddev_arr,std)
				numstar_arr = np.append(numstar_arr,numstars)
				imagenum_arr = np.append(imagenum_arr,imagenum)
				continue
			except newauto.afException as e:

				#S we want to only look at good indices here, as you can imagine if we are finding a focus out of bounds,
				#S it could be due to the endpoints not having a good hfr median value. This has the potential
				#S to duplicate positions, but it shouldn't be an issue, as it will only duplicate those points wehre
				#S we don't have a good hfr value. also note that this can get in an infiinte loop as is (i think)

				if e.message == 'LowerLimit_Exception':
					telescope.logger.info('New focus too low, adding a new minimum point')
					pos_arr = np.append(pos_arr, (pos_arr[goodind].min()-defocus_step*1000.))
					#S pos_arr.min() should be the point we just added, but need to double check this
#					med, std, numstars, imagenum = self.autofocus_step(telescope_num,pos_arr.min(),af_exptime,af_filter)

				elif e.message == 'UpperLimit_Exception':
					telescope.logger.info('New focus too low, adding a new maximum point')
					pos_arr = np.append(pos_arr, (pos_arr[goodind].max()+defocus_step*1000.))
					#S pos_arr.max() should be the point we just added, but need to double check this
#					med, std, numstars, imagenum = self.autofocus_step(telescope_num,pos_arr.max(),af_exptime,af_filter)
				
				elif e.message == 'NoMinimum_Exception':
					#S Not sure what I want to do here.
					print 'here fucked up'
					pass
				focusmeas_arr = np.append(focusmeas_arr,med)
				stddev_arr = np.append(stddev_arr,std)
				numstar_arr = np.append(numstar_arr,numstars)
				imagenum_arr = np.append(imagenum_arr,imagenum)

				#S continue just stops this iteration of the loop and starts the next one
				continue

			except:
				telescope.logger.exception('Unhandled error in fitting autofocus')
				
				
			#S Find the change in the focus from the last fit
			delta_focus = np.absolute(old_best_focus - new_best_focus)
			#XXX
			if i == 1:
				delta_focus=101
				i =0
			print pos_arr
			print focusmeas_arr
			print new_best_focus
			if delta_focus>MAXDELTA:
				print 'in delta focus loop'
				goodind = np.where(focusmeas_arr <> -999)[0]
				#S if there are more points above the new focus then there are below
				#TODO this seems sketchy, we could do flipflopping to more above and below, spending a lot of time 
				#TODO moving the focuser around.
				print len(np.where(pos_arr<new_best_focus)[0])<len(np.where(pos_arr>new_best_focus)[0])
				print len(np.where(pos_arr<new_best_focus)[0])>len(np.where(pos_arr>new_best_focus)[0])
				if len(np.where(pos_arr<new_best_focus)[0])<len(np.where(pos_arr>new_best_focus)[0]):	
					
					telescope.logger.info('Fewer points below focus and not within delta, adding a new min point')
					pos_arr = np.append(pos_arr, (pos_arr[goodind].min()-defocus_step*1000.))
					#S pos_arr.min() should be the point we just added, but need to double check this
					#med, std, numstars, imagenum = self.autofocus_step(telescope_num,pos_arr.min(),af_exptime,af_filter)
					continue

				elif len(np.where(pos_arr<new_best_focus)[0])>len(np.where(pos_arr>new_best_focus)[0]):	
					telescope.logger.info('Fewer points above focus and not within delta, adding a new max point')
					pos_arr = np.append(pos_arr, (pos_arr[goodind].min()+defocus_step*1000.))
					#S pos_arr.min() should be the point we just added, but need to double check this
					#med, std, numstars, imagenum = self.autofocus_step(telescope_num,pos_arr.min(),af_exptime,af_filter)
					continue
				else:
					print 'herheherhehrehrehe'


				focusmeas_arr = np.append(focusmeas_arr,med)
				stddev_arr = np.append(stddev_arr,std)
				numstar_arr = np.append(numstar_arr,numstars)
				imagenum_arr = np.append(imagenum_arr,imagenum)
				continue
		print pos_arr
		#S Made it through the fitting routine. Now for all the other stuff in autofocus, updating, etc.
		#S if we went the maximum number of steps, I would consider this a fail, and it needs attention no matter what.
		#S Maybe a little too strict on fail condition here.
		if len(pos_arr)==MAXSTEPS:
			#S if something went wrong, log and send email. May even want to send a text?
			new_best_focus = None
			self.logger.exception('T'+str(telescope_number)+' failed in finding new focus after %i, and could probably use some help'%(MAXSTEPS))
			body = "Hey humans,\n\nI'm having trouble with autofocus, and need your assitance. You have a few options:\n"\
			    +"-Try and figure what is going on with the newautofocus\n"\
			    +"-Revert to PWI autofocus\n"\
			    +"This may be tricky because a lot of this is worked into the observingScript, "\
			    +"and you may be fighting with that for control of the telescope."\
			    +" I would recommend stopping main.py, but it could be situational.\n\n"\
			    +"I AM CONTINUING WITH NORMAL OPERATIONS USING OLD ''BEST'' FOCUS.\n\n"\
			    +"Love,\nMINERVA\n\n"\
			    +"P.S. Tips and tricks (please add to this list):\n"\
			    +"-You could be too far off the nominal best focus, and the routine can't find a clean fit.\n"\
			    +"-The aqawan could somehow be closed, and you're taking pictures that it can't find stars in.\n"\
			    +"-You can now plot the results of any autofocus run, look into newauto.recordplot(). Just "\
			    +"'python newauto.py' and enter the recordplot(path+record_name).\n"
#			mail.send("Autofocus failed on T"+str(telescope_number),body,level='serious')
			return
		

		print ' found focus at ',new_best_focus,fitcoeffs



	def autofocus(self,telescope_number,num_steps=10,defocus_step=0.3,af_exptime=5,af_filter="V",fau=False,target=None):

		#XXX I think that this code is ready to removed. 


		#S This is gonna look stupid, but I'm just going to place the call to newauto.autofocus in here
		newauto.autofocus(self,telescope_number,num_steps=num_steps,defocus_step=defocus_step,\
					  af_exptime=af_exptime,af_filter=af_filter,\
					  fau=fau,target=target)
		return
		if spectroscopy: return

		#S get the telescope we plan on working with
		telescope = self.telescopes[telescope_number-1]
		
		af_target = {}
		#S define aftarget dict for takeImage
		af_target['name'] = 'autofocus'
		af_target['exptime'] = af_exptime
		af_target['filter'] = af_filter
		af_target['spectroscopy'] = fau

		# select the appropriate port (default to imager)
		if 'spectroscopy' in af_target.keys():
			if af_target['spectroscopy']:
				m3port = telescope.port['FAU']
			else: 
				m3port = telescope.port['IMAGER']
		else:
			m3port = telescope.port['IMAGER']

		#S our data path
		datapath = '/Data/t' + str(telescope_number) + '/' + self.site.night + '/'

		# wait for dome to be open
		if telescope_number > 2:
			dome = self.domes[1]
		else:
			dome = self.domes[0]
		#S Get current time for measuring timeout
		t0 = datetime.datetime.utcnow()
#		"""
		#S Loop to wait for dome to open, cancels afeter ten minutes
		while dome.isOpen() == False:
			self.logger.info('T' + str(telescope_number) + ': Enclosure closed; waiting for dome to open')
			timeelapsed = (datetime.datetime.utcnow()-t0).total_seconds()
			if timeelapsed > 600: 
				self.logger.info('T' + str(telescope_number) + ': Enclosure still closed after 10 minutes; skipping autofocus')
				return
			time.sleep(30)
#		"""

		#S Initialize telescope, we want tracking ON
		if not telescope.initialize(tracking=True, derotate=True):
			telescope.recover(tracking=True, derotate=True)

		#S make array of af_defocus_steps
		defsteps = np.linspace(-defocus_step*(num_steps/2),defocus_step*(num_steps/2),num_steps)
		#S Array of new positions for the focuser, using this rahter than step. 
		poslist = defsteps*1000 + telescope.focus

		#S Just need an empty list for the fwhm/hfr and std to append to. made FOCUSMEASure_LIST 
		#Sbecause we don't necessarily know which value we want yet.
		imagenum_list = []
		focusmeas_list = []
		stddev_list = []
		numstar_list = []


		"""
		#S Actual autofocus sequence
		for position in poslist:
			med, std, numstars, imagenum = self.autofocus_step(telescope_num,position,af_exptime,af_filter)
			focusmeas_list.append(med)
			stddev_list.append(std)
			numstar_list.append(numstars)
			imagenum_list.append(imagenum)
		"""
		for step in defsteps:
			#S set the new focus, and move there if necessary
			newfocus = telescope.focus + step*1000.0
			status = telescope.getStatus()
			
			#S ensure we have the correct port
			telescope.m3port_switch(m3port)
			#S move and wait for focuser
			if newfocus <> status.focuser.position:
				self.logger.info('T'+str(telescope_number) + ": Defocusing Telescope by " + str(step) + ' mm, to ' + str(newfocus))
				telescope.focuserMove(newfocus)
				#S Needed a bit longer to recognize focuser movement, changed from 0.3
				time.sleep(.5)

			#S Take image, recall takeimage returns the filename of the image. we have the datapath from earlier
			imagename = self.takeImage(af_target,telescope_num=telescope_number)
			imagenum_list.append(imagename.split('.')[4])

			#S Sextract this guy, put in a try just in case. Defaults should be fine, which are set in newauto. NOt sextrator defaults
			try: 
				catalog = utils.sextract(datapath,imagename)
				self.logger.debug('T' + str(telescope_number) + ': Sextractor success on '+catalog)
			except: 
				self.logger.exception('T' + str(telescope_number) + ': Sextractor failed on '+catalog)

			#S get focus measure value, as well as standard deviation of the mean
			try:
				median, stddev, numstar = newauto.get_hfr_med(catalog,fau=fau,telescope=telescope)
				self.logger.info('T'+str(telescope_number)+': Got hfr value from '+catalog)
				focusmeas_list.append(median)
				stddev_list.append(stddev)
				numstar_list.append(numstar)
			#S if the above fails, we set these obviously wrong numbers, and move on. We'll identify these points later.
			except:
				self.logger.exception('T' + str(telescope_number) + ': Failed to get hfr value from '+catalog)
				#S This sets the default 'bad' value to 999. we want to maintain the size/shape of arrays for later use,
				#S and will thus track these bad points for exclusion later.
				focusmeas_list.append(-999)				
				stddev_list.append(999)
				numstar_list.append(0)
		
		#S define poslist from steps and the old best focus. this is an nparray
		poslist = defsteps*1000 + telescope.focus
		#S Convert to array for ease of mind
		focusmeas_list = np.array(focusmeas_list)
		stddev_list = np.array(stddev_list)
		#S find the indices where we didnt hit the an error getting a measure
		goodind = np.where(focusmeas_list <> -999)[0]

		#S This try is here to catch any errors/exceptions raised out of fitquad. I think we should include exceptions if 
		#S we are too far out of focus, etc to make this catch whenever we didn't find a best focus.
		try:
			#S this is in place to catch us if all the images fail to get sextracted or something else goes on.
			#S probably a better way to do this, but we'll figure that out later.
			if len(goodind) == 0:
				self.logger.exception('T'+str(telescope_number)+' failed autofocus due to no medians')
				raise Exception()
			#S find the best focus
			self.logger.debug('T'+str(telescope_number) +': fitting to '+str(len(goodind))+' points.')
			new_best_focus,fitcoeffs = newauto.fitquadfindmin(poslist[goodind],focusmeas_list[goodind],\
										  weight_list=stddev_list[goodind],\
										  logger=self.logger,telescope_num=telescope_number)
			self.logger.debug('T'+str(telescope_number)+': found a good fit.')
		except:
			#S if something went wrong, log and send email. May even want to send a text?
			new_best_focus = None
			self.logger.exception('T'+str(telescope_number)+' failed in finding new focus, and could probably use some help')
			body = "Hey humans,\n\nI'm having trouble with autofocus, and need your assitance. You have a few options:\n"\
			    +"-Try and figure what is going on with the newautofocus\n"\
			    +"-Revert to PWI autofocus\n"\
			    +"This may be tricky because a lot of this is worked into the observingScript, "\
			    +"and you may be fighting with that for control of the telescope."\
			    +" I would recommend stopping main.py, but it could be situational.\n\n"\
			    +"I AM CONTINUING WITH NORMAL OPERATIONS USING OLD ''BEST'' FOCUS.\n\n"\
			    +"Love,\nMINERVA\n\n"\
			    +"P.S. Tips and tricks (please add to this list):\n"\
			    +"-You could be too far off the nominal best focus, and the routine can't find a clean fit.\n"\
			    +"-The aqawan could somehow be closed, and you're taking pictures that it can't find stars in.\n"\
			    +"-You can now plot the results of any autofocus run, look into newauto.recordplot(). Just "\
			    +"'python newauto.py' and enter the recordplot(path+record_name).\n"
			mail.send("Autofocus failed on T"+str(telescope_number),body,level='serious')


		#S Log the best focus.
		self.logger.info('T' + str(telescope_number) + ': New best focus: ' + str(new_best_focus))

		# if no sensible focus value measured, use the old value
		if new_best_focus == None: new_best_focus = telescope.focus
		
		#S want to record old best focus
		old_best_focus = telescope.focus
		# update the telescope focus
		telescope.focus = new_best_focus
		
		# move to the best focus
		status = telescope.getStatus()
		if telescope.focus <> status.focuser.position:
			self.logger.info('T'+str(telescope_number) + ": Moving focus to " + str(telescope.focus))
			telescope.focuserMove(telescope.focus)

			# wait for focuser to finish moving
			status = telescope.getStatus()
			while status.focuser.moving == 'True':
				self.logger.info('T' + str(telescope_number) + ': Focuser moving (' + str(status.focuser.position) + ')')
				time.sleep(0.3)
				status = telescope.getStatus()

		# record values in the header
		alt = str(float(status.mount.alt_radian)*180.0/math.pi)
                try:    tm1 = str(status.temperature.primary)
		except: tm1 = 'UNKNOWN'
                try:    tm2 = str(status.temperature.secondary)
                except: tm2 = 'UNKNOWN'
                try:    tm3 = str(status.temperature.m3)
		except: tm3 = 'UNKNOWN'
		try:    tamb = str(status.temperature.ambient)
		except: tamb = 'UNKNOWN'
		try:    tback = str(status.temperature.backplate)
                except: tback = 'UNKNOWN'

		self.logger.info('T' + str(telescope_number) + ': Updating best focus to ' + str(telescope.focus) + ' (TM1=' + tm1 + ', TM2=' + tm2 + ', TM3=' + tm3 + ', Tamb=' + tamb + ', Tback=' + tback + ', alt=' + alt + ')' )
                f = open('focus.' + telescope.logger_name + '.txt','w')
		f.write(str(telescope.focus))
		f.close()
                self.logger.info('T' + str(telescope_number) + ': Finished autofocus')

		#S Record all the data to it's own run unique file for potential use later. Just 
		#S don't want to be scraping through logs for it when we can just record it now.
		#S Do we still want the logger line above?
		try:
			#S Check to make sure all the arrays are the same length and not zero.
			if len(imagenum_list)==len(poslist)==len(focusmeas_list)==len(stddev_list)==len(numstar_list):
				#S Stack them all together, then transpose so we can write them in columns 
				autodata = np.vstack([imagenum_list,poslist,focusmeas_list,stddev_list,numstar_list]).transpose()
				#S Name the data file as 'nYYYYMMDD.T#.autorecord.filter.AAAA.BBBB.txt', where AAAA is the image number on the 
				#S first image of the autofocus sequence, and BBBB the last image number.
				datafile = self.site.night+'.T'+str(telescope_number)+'.autorecord.'+af_filter+'.'+imagenum_list[0]+'.'+imagenum_list[-1]+'.txt'
				with open(datapath+datafile,'a') as fd:
					#S Write all the environment temps, etc. also record old and new best focii
					fd.write('Old\tNew\tTM1\tTM2\tTM3\tTamb\tTback\talt\n')
					fd.write(str(old_best_focus)+'\t'+str(new_best_focus)+'\t'+tm1+'\t'+tm2+'\t'+tm3+'\t'+tamb+'\t'+tback+'\t'+alt+'\n')
					#S Write a header with info on following columns
					header = 'Column 1\tImage number\n'+\
					    'Column 2\tFocuser position\n'+\
					    'Column 3\tMedian focus measure\n'+\
					    'Column 4\tSDOM\n'+\
					    'Column 5\tNumber of stars'
					#S save the array of good stuff
					np.savetxt(fd,autodata,fmt='%s',header=header)
			else:
				self.logger.error('T'+str(telescope_number)+': Could not record autodata due to mismatch length in arrays')
		except:
			self.logger.exception('T'+str(telescope_number)+': unhandled error stopped record of autofocus results.')

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
	
	
	
