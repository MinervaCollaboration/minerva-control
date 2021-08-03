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
import copy

#Minerva library dependency
import env
import aqawan
import cdk700 
import imager
import imager_ascom
import fau
import spectrograph
import astrohaven
import utils
import pdu
import mail
from get_all_centroids import *
import segments
import newauto 
from fix_fits import fix_fits
import rv_control
from plotweather import plotweather
from plot_autofocus import plot_autofocus
import scheduler
import plot_pointing_error
import Plot_fits
# FAU guiding dependencies
import PID_test as pid
from read_guider_output import get_centroid
from propagatingthread import PropagatingThread

class control:
	
#============Initialize class===============#
	#S The standard init
	def __init__(self,config,base, red=False, south=False, directory=None):#telescope_list=0,dome_control=1):

		self.config_file = config
		self.base_directory = base
		#S Only sets logger name right now
		self.load_config()
		self.red = red
		self.south = south

		if directory == None:
			if self.red: self.directory = 'directory_red.txt'
			elif self.south: self.directory = 'directory_south.txt'
			else: self.directory = 'directory.txt'
		else: self.directory=directory

		if self.red: self.logger_name = self.logger_name + '_red'

		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
		
                self.gitNum = subprocess.check_output(['git', "rev-list", "HEAD", "--count"]).strip()

		#S See below, lots of new objects created here. 
		self.create_class_objects()
		self.logger_lock = threading.Lock()
		
	#create class objects needed to control Minerva system
	def create_class_objects(self):
                self.domes = []
                self.telescopes = []
                self.cameras = []
		self.pdus = []
		self.site = env.site('site_mtHopkins.ini',self.base_directory)
		self.thermalenclosureemailsent = False

		if self.red:
			self.spectrograph = spectrograph.spectrograph('spectrograph_mred.ini',self.base_directory, red=True)
			self.domes.append(astrohaven.astrohaven('astrohaven_red.ini',self.base_directory))
			self.telescopes.append(cdk700.CDK700('telescope_mred.ini',self.base_directory, red=True))
			self.cameras.append(imager_ascom.imager('imager_mred.ini',self.base_directory))
			#self.cameras.append(imager.imager('imager_mred.ini',self.base_directory))

#			self.cameras.append(imager.imager('imager_mredc14.ini',self.base_directory))
			self.pdus.append(pdu.pdu('apc_mred_cal.ini',self.base_directory))
#			self.pdus.append(pdu.pdu('apc_mredrack.ini',self.base_directory))
		        #S make the scheduler, which has the target list as an attribute
			self.scheduler = scheduler.scheduler('scheduler.ini',self.base_directory,red=True)
			print 'done connecting to everything'
		elif self.south:
			pass
		else:
#			self.logger.error("***Spectrograph disabled!***")
#			self.spectrograph = None
			self.spectrograph = spectrograph.spectrograph('spectrograph.ini',self.base_directory)


#			self.logger.error("***Aqawan 1 disabled***")
#			aqawans = [1]
			aqawans = [1,2]
			for i in aqawans:
#			for i in range(1):
				try:
					aqawanob = aqawan.aqawan('aqawan_' + str(i) + '.ini',self.base_directory)
					if aqawanob.heartbeat(): self.domes.append(aqawanob)
					else: self.logger.error("Failed to initialize Aqawan " + str(i))
				except:
					self.logger.exception("Failed to initialize Aqawan " +str(i))
			# initialize the 4 telescopes
#			self.logger.error("***T1 & T2 disabled due to FAU camera failure***")
#			telescopes = [3,4]
#			telescopes = [3,4]
#			telescopes = [1,2,3,4]

			telescopes = [1,2,4]
			self.logger.error("*** T3 disabled***")


#			self.logger.error("***only using T1 & T2***")
#			telescopes = [1,2]
			for i in telescopes:
				try: 
					self.cameras.append(imager.imager('imager_t' + str(i) + '.ini',self.base_directory))
					self.telescopes.append(cdk700.CDK700('telescope_' + str(i) + '.ini',self.base_directory))
				except:
					self.logger.exception('T' + str(i) + ': Failed to initialize the imager')

			for i in range(5):
				self.pdus.append(pdu.pdu('apc_' + str(i+1) + '.ini',self.base_directory))
			self.pdus.append(pdu.pdu('apc_bench.ini',self.base_directory))

		        #S make the scheduler, which has the target list as an attribute
			self.scheduler = scheduler.scheduler('scheduler.ini',self.base_directory)

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

		fmt = "%(asctime)s.%(msecs).03d [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(threadName)s: %(message)s"
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

		try:
			for fh in self.spectrograph.logger.handlers: self.spectrograph.logger.removeHandler(fh)
			fh = logging.FileHandler(path + '/' + self.spectrograph.logger_name + '.log', mode='a')	
			fh.setFormatter(formatter)
			self.spectrograph.logger.addHandler(fh)
		except:
			pass

		self.logger_lock.release()
	
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
	def telescope_initialize(self,tele_list=[], tracking = True, derotate=True):
		# default to all telescopes
		if isinstance(tele_list,basestring):
			tele_list = [tele_list]
		elif len(tele_list) == 0:
			tele_list = []
			for telescope in self.telescopes:
				tele_list.append(telescope.id)

		threads = []
                for telid in tele_list:
			kwargs={'tracking':tracking,'derotating':derotate}
			telescope = utils.getTelescope(self,telid)
			thread = PropagatingThread(target = telescope.initialize,kwargs=kwargs)
			thread.name = telid + ' (control->telescope_initialize->initialize)'
			thread.start()
			threads.append(thread)

                for thread in threads:
			threads[t].join()

                return

	def telescope_acquireTarget(self,target,tele_list=[]):
		# default to all telescopes
		if isinstance(tele_list,basestring):
			tele_list = [tele_list]
		elif len(tele_list) == 0:
			tele_list = []
			for telescope in self.telescopes:
				tele_list.append(telescope.id)
				
		threads = []
                for telid in tele_list:
			telescope = utils.getTelescope(self,telid)
			thread = PropagatingThread(target = telescope.acquireTarget,args=(target))
			thread.name = telid + ' (control->telescope_acquireTarget->acquireTarget)'
			thread.start()
			threads.append(thread)

                for thread in threads:
			threads[t].join()

                return

	def telescope_mountGotoAltAz(self,alt,az,tele_list=[]):
		# default to all telescopes
		if isinstance(tele_list,basestring):
			tele_list = [tele_list]
		elif len(tele_list) == 0:
			tele_list = []
			for telescope in self.telescopes:
				tele_list.append(telescope.id)
				
		threads = []
                for telid in tele_list:
			telescope = utils.getTelescope(self,telid)
			thread = PropagatingThread(target = telescope.mountGotoAltAz,args=(alt,az))
			thread.name = telid + ' (control->telescope_mountGotoAltAz->mountGotoAltAz)'
			thread.start()
			threads.append(thread)

                for thread in threads:
			thread.join()

                return

	def telescope_park(self,tele_list=[],parkAlt=25.0, parkAz=0.0):

		# default to all telescopes
		if isinstance(tele_list,basestring):
			tele_list = [tele_list]
                elif len(tele_list) == 0:
			tele_list = []
			for telescope in self.telescopes:
				tele_list.append(telescope.id)
				
		threads = []
                for telid in tele_list:
			telescope = utils.getTelescope(self,telid)
			kwargs = {'parkAlt':parkAlt, 'parkAz':parkAz}
			thread = PropagatingThread(target = telescope.park, kwargs=kwargs)
			thread.name = telid + ' (control->telescope_park->cdk700->park)'
			thread.start()
			threads.append(thread)

                for thread in threads:
			thread.join()

                return

	def m3port_switch_list(self, portstr, tele_list = []):

		# default to all telescopes                                                             
                if isinstance(tele_list,basestring):
			tele_list = [tele_list]
                elif len(tele_list) == 0:
                        tele_list = []
                        for telescope in self.telescopes:
                                tele_list.append(telescope.id)
		
		threads = []
                for telid in tele_list:
			telescope = utils.getTelescope(self,telid)
			thread = PropagatingThread(target = telescope.m3port_switch,args=[telescope.port[portstr],])
			thread.name = telid + ' (control->m3port_switch_list->cdk700->m3port_switch)'
			thread.start()
			threads.append(thread)

                for thread in threads:
			thread.join()

                return


#============Imager control===============#
#block until command is complete
#operate on imagre specified by num
#if num is not specified or outside of array range,
#operate all imagers.

	def imager_initialize(self,tele_list=[]):
		# default to all telescopes                                                             
                if isinstance(tele_list,basestring):
			tele_list = [tele_list]
                elif len(tele_list) == 0:
                        tele_list = []
                        for telescope in self.telescopes:
                                tele_list.append(telescope.id)
		
		threads = []
                for telid in tele_list:
			camera = utils.getCamera(self,telid)
			thread = PropagatingThread(target = camera.initialize)
			thread.name = telid + ' (control->imager_initialize->imager->initialize)'
			thread.start()
			threads.append(thread)

                for thread in threads:
			thread.join()

                return

	def imager_connect(self,tele_list=[]):
		# default to all telescopes                                                             
                if isinstance(tele_list,basestring):
			tele_list = [tele_list]
                elif len(tele_list) == 0:
                        tele_list = []
                        for telescope in self.telescopes:
                                tele_list.append(telescope.id)
		
		threads = []
                for telid in tele_list:
			camera = utils.getCamera(self,telid)
			thread = PropagatingThread(target = camera.connect_camera)
			thread.name = telid + ' (control->imager_connect->imager->connect_camera)'
			thread.start()
			threads.append(thread)

                for thread in threads:
			thread.join()

                return

	def imager_setDatapath(self,night,tele_list=[]):

		# default to all telescopes                                                             
                if isinstance(tele_list,basestring):
			tele_list = [tele_list]
                elif len(tele_list) == 0:
                        tele_list = []
                        for telescope in self.telescopes:
                                tele_list.append(telescope.id)
		
		threads = []
                for telid in tele_list:
			camera = utils.getCamera(self,telid)
			thread = PropagatingThread(target = camera.set_dataPath)
			thread.name = telid + ' (control->imager_setDatapath->imager->set_dataPath)'
			thread.start()
			threads.append(thread)

                for thread in threads:
			thread.join()

                return
				
	def imager_compressData(self,tele_list=[],night=None):

                # default to all telescopes 
                if isinstance(tele_list,basestring):
                        tele_list = [tele_list]
                elif len(tele_list) == 0:
                        tele_list = []
                        for telescope in self.telescopes:
                                tele_list.append(telescope.id)

                threads = []
                for telid in tele_list:
                        camera = utils.getCamera(self,telid)
			thread = PropagatingThread(target = camera.compress_data)
                        thread.name = telid + ' (control->imager_compressData->imager->compress_data)'
                        thread.start()
                        threads.append(thread)

                for thread in threads:
                        thread.join()

                return

#======================High level stuff===========================#
#more complex operations 

	#load calibration file
	def loadCalibInfo(self,telid):

		scheduleFile = self.base_directory + '/schedule/' + self.site.night + '.' + telid + '.txt'
		if not os.path.isfile(scheduleFile): 
			self.logger.info('No photometry schedule; skipping imager calibrations')
			return [None, None]
			
		self.logger.info('Loading calib file: ' + scheduleFile)
		try:
			with open(scheduleFile, 'r') as calibfile:
				calibline = calibfile.readline()
				calibendline = calibfile.readline()
			
				calibinfo = json.loads(calibline)
				calibendinfo = json.loads(calibendline)
				self.logger.info('Calib info loaded: ' + self.site.night + '.' + telid + '.txt')
				return [calibinfo,calibendinfo]
		except:
			self.logger.info('Error loading calib info: ' + self.site.night + '.' + telid + '.txt')
			return [None, None]

        # run astrometry.net on imageName, update solution in header                                             
	def astrometry(self, imageName, rakey='RA', deckey='DEC',pixscalekey='PIXSCALE', pixscale=None, nopositionlimit=False, noquadlimit=False, verbose=False):

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
		    ' --scale-high ' + str(1.01*pixscale)
		if not nopositionlimit:
			cmd += ' --ra ' + str(ra) + \
			    ' --dec ' + str(dec) + \
			    ' --radius ' + str(radius)
		if not noquadlimit:
			cmd += ' --quad-size-min 0.4' + \
			    ' --quad-size-max 0.6'
		cmd += ' --cpulimit 30' + \
		    ' --no-verify' + \
		    ' --crpix-center' + \
		    ' --no-fits2fits' + \
		    ' --no-plots' + \
		    ' --overwrite ' + \
		    imageName
#        ' --use-sextractor' + \ #need to install sextractor

		cmd = r'/usr/local/astrometry/bin/' + cmd 
		if not verbose: cmd += + ' >/dev/null 2>&1'
		print cmd
		os.system(cmd)

	def getPA(self,imageName, email=True):
		
		self.logger.info('Finding PA for ' + imageName)
		self.astrometry(imageName, noquadlimit=self.red,verbose=True)
		
		baseName = os.path.splitext(imageName)[0]
		f = pyfits.open(imageName, mode='update')
		if os.path.exists(baseName + '.new'):

			
			self.logger.info('Astrometry successful for ' + imageName)

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
			self.logger.info("Telescope PA = " + str(origPA) + '; solved PA = ' + str(PA) + '; offset = ' + str(dPA) + ' degrees')
			self.logger.info("Telescope RA = " + str(origracen) + '; solved RA = ' + str(racen) + '; offset = ' + str(dRA) + ' arcsec')
			self.logger.info("Telescope Dec = " + str(origdeccen) + '; solved Dec = ' + str(deccen) + '; offset = ' + str(dDec) + ' arcsec')
			self.logger.info("Total pointing error = " + str(dtheta) + ' arcsec')
			
			telname = f[0].header['TELESCOP']
			guideFile = "disableGuiding." + telname + ".txt"
			if abs(dPA) > 5:
				self.logger.error("PA out of range")
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
						mail.send("PA error too large",body,level='serious',directory=self.directory)
			else:
				if os.path.exists(guideFile):
					self.logger.error("PA in range, re-enabling guiding")
					os.remove(guideFile)
					if email:
						body = "Dear benevolent humans,\n\n" + \
						    "The PA error is within range again. Re-enabling guiding.\n\n" + \
						    "Love,\n" + \
						    "MINERVA"
						mail.send("PA error fixed",body,level='serious',directory=self.directory)
					                            
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
				
				try: self.logger.error("Pointing error too large")
				except: pass
				if email: mail.send("Pointing error too large",body,level='serious',directory=self.directory)

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

	def hourangle(self,target,telid=None, status=None):
		#S update the site time to the current utc time
		self.site.date = datetime.datetime.utcnow()
		#S convert the radian sideral time from the site to hours
		lst_hours = self.rads_to_hours(self.site.obs.sidereal_time())
		#S i have no idea what this magic does
		if 'ra' in target.keys():
			ha = lst_hours - target['ra']
		elif telid <> None:
			telescope = utils.getTelescope(self,telid)
			if status==None: status = telescope.getStatus()
			ra = utils.ten(status.mount.ra_2000)
			ha = lst_hours - ra
		else:
			self.logger.info(target['name']+' does not have an RA for Hour Angle calc; HA unknown')
			return "UNKNOWN"
		#S put HA in range (0,24)
		if ha<0.0: ha+=24.0
		elif ha>24.0: ha-=24.0
		#S put HA in range (-12,12)
		if ha>12.0: ha = ha-24.0

		return ha

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

	def takeFauImageFast():

		d = cameras.camera.img
		th = threshold_pyguide(d, level = 4)

		if np.max(d*th) == 0.0:
			return np.zeros((1,3))
    
		imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
		cc = centroid_all_blobs(imtofeed)

		return cc

	# this should be replaced with SExtractor
	def getstars(self,imageName):
    
		d = getfitsdata(imageName)
		th = threshold_pyguide(d, level = 4)

		if np.max(d*th) == 0.0:
			return np.zeros((1,3))
    
		imtofeed = np.array(np.round((d*th)/np.max(d*th)*255), dtype='uint8')
		cc = centroid_all_blobs(imtofeed)

		return cc
	
	# if the telescope fails to point precisely enough to get the
	# star in the FAU field of view, use the imager and offsets in
	# the config files to acquire the star
	def findWithImager(self, telid):
		target = {
			"name":"acquisition",
			"objname":"acquisition",
			'exptime':5,
			'fauexptime':5,
			'fau':False,
			}
		telescope = utils.getTelescope(self,telid)
		camera = utils.getCamera(self,telid)
		dome = utils.getDome(self,telid)
		m3port = telescope.port['IMAGER']
		dataPath = telescope.datadir + self.night + '/'
		
		# take image
		filename = self.takeImage(target,telid)

		PA = self.getPA(datapath + filename)
		

	# search for an object in an outward spiral from current location
	# used for acquiring targets on FAU when pointing is bad
	# this is an inefficient hack treating the symptom, not the problem
	def spiralSearch(self, telid, step=120, maxx=10,maxy=10, timeout=86400.0):		

		target = {
			"name":"spiral",
			"objname":"spiral",
			'exptime':5,
			'fauexptime':5,
			'fau':True,
			}

		telescope = utils.getTelescope(self,telid)
		camera = utils.getCamera(self,telid)
		dome = utils.getDome(self,telid)
		m3port = telescope.port['FAU']
		dataPath = telescope.datadir + self.night + '/'

		t0 = datetime.datetime.utcnow()

		x = y = 0
		dx = 0
		dy = -1
		for i in range(max(maxx,maxy)**2):
			if (-maxx/2.0 < x <= maxx/2.0) and (-maxy/2.0 < y <= maxy/2.0):
				# jog telescope
				self.logger.info(telid + ": jogging telescope by " + str(dx) + ',' + str(dy) + " steps to arrive at " + str(x) + ',' + str(y) + ')')
				telescopeStatus = telescope.getStatus()
				dec = utils.ten(telescopeStatus.mount.dec_2000)
				telescope.mountOffsetRaDec(dx*step/math.cos(dec*math.pi/180.0),dy*step)
				self.logger.info("waiting for jog")
				time.sleep(1)
				moving = telescope.isMoving()
		
				# take image
				filename = self.takeFauImage(target,telid)
				stars = self.getstars(dataPath + filename)
				if len(stars) >= 1:
					self.logger.info(telid + ": found a star!")
					return filename

			if x==y or (x < 0 and x == -y) or (x > 0 and x == 1-y):
				dx,dy=-dy,dx
			x,y=x+dx,y+dy

			elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
			if elapsedTime > timeout or telescope.abort: return filename

		return filename

	def fauguide(self,target,telid,guiding=True,xfiber=None, yfiber=None, acquireonly=False, skiponfail=False, artificial=False, ao=False, maxfail=5, simulate=False):

		telescope = utils.getTelescope(self,telid)
		camera = utils.getCamera(self,telid)
		dome = utils.getDome(self,telid)
		m3port = telescope.port['FAU']

		camera.fau.acquired = False

		# try out the tip/tilt guiding...
		ao = camera.isAOPresent()
		if camera.telid == 'T2': ao = False

		# center the AO unit
		if ao: camera.homeAO()

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
		while camera.fau.guiding and not telescope.abort:
			self.logger.info("entering guiding loop")
			if i>npts:
				break

			#t0,xstar,ystar = camera.getGuideStar()
			t0 = datetime.datetime.utcnow()
			xstar = ystar = np.nan
			nfailed = 0
			while (np.isnan(xstar) or np.isnan(ystar)) and not telescope.abort:

				if nfailed > maxfail:
					camera.fau.acquired = False
					return False

				self.logger.info("beginning image")
				
#				# take an image, don't wait for it to write to disk
#				imaging_thread = PropagatingThread(target=self.takeFauImage,args=(target,telid,))
#				imaging_thread.start()
#
#				time.sleep(target['fauexptime'])
#
#				# imager_server fights when trying to do it asynchronously
#				imaging_thread.join()
#
#
#
#				# update when we have a new image
#				guidetime,xstar,ystar = camera.getGuideStar()
#				while (guidetime-t0).total_seconds() < 0.001:
#					time.sleep(0.001)
#					guidetime,xstar,ystar = camera.getGuideStar()
#				# some sort of race condition?
#				time.sleep(0.5)
#				guidetime,xstar,ystar = camera.getGuideStar()
#				t0 = guidetime
				
#				# if it's been acquired, switch to a subframe around the region
#				if camera.fau.acquired:
#					subframesize = int(round(1.5*tolerance/self.guider.platescale))
#					if (subframesize % 2) == 1: subframesize +=1 # make sure it's even
#					x1 = int(round(camera.fau.xfiber + offset[0] - subframesize))
#					x2 = int(round(camera.fau.xfiber + offset[0] + subframesize))
#					y1 = int(round(camera.fau.yfiber + offset[1] - subframesize))
#					y2 = int(round(camera.fau.yfiber + offset[1] + subframesize))
#					camera.set_roi(x1,x2,y1,y2,fau=True)
#				else: camera.set_roi(fullFrame=True,fau=True)

				if simulate: 
					# include an arbitrary offset from the nominal position (experimental)
					offset_file = self.base_directory + '/' + telid + '_fiber_offset.txt'
				
					if os.path.exists(offset_file):
						with open(offset_file) as fh:
							entries = fh.readline().split()
							xoffset = float(entries[0])
							yoffset = float(entries[1])
							self.logger.info(telid + ": offset file found, applying offset to fiber position (" + str(xoffset) + "," + str(yoffset) + ")")
							offset = (xoffset,yoffset)
					else: offset = (0.0,0.0)		

					xstar = int(round(camera.fau.xfiber + offset[0] + np.random.uniform(low=-1.0,high=1.0)))
					ystar = int(round(camera.fau.yfiber + offset[1] + np.random.uniform(low=-1.0,high=1.0)))
					guidetime = datetime.datetime.utcnow()
					#camera.simulate_star_image([xstar],[ystar],[1e6],1.5,noise=10.0,fau=True)
					#guidetime,xstar,ystar = camera.getGuideStar()

				else:
					t0 = datetime.datetime.utcnow()
					filename = self.takeFauImage(target,telid)
					timeElapsed = 0.0
					timeout = 60
					guidetime = datetime.datetime(2000,1,1)
					while timeElapsed < timeout and guidetime < t0:
						guidetime,xstar,ystar = camera.getGuideStar()
						timeElapsed = (datetime.datetime.utcnow() - t0).total_seconds()

				if np.isnan(xstar) or np.isnan(ystar):
					nfailed += 1
					self.logger.error("Guide star not found in " + filename)
				else:
					self.logger.info("Guide star found at " + str(xstar) + ',' + str(ystar) + ' in ' + filename + '; last updated at ' + str(guidetime))
				
			if telescope.abort: 
				self.logger.info("Telescope requested abort")
				camera.fau.acquired = False
				return True


			if True:
				self.logger.info("Using the star at (x,y)=(" + str(xstar) + "," + str(ystar) +  "); last updated at " + str(guidetime))

				# include an arbitrary offset from the nominal position (experimental)
				offset_file = self.base_directory + '/' + telid + '_fiber_offset.txt'
				
				if os.path.exists(offset_file):
					with open(offset_file) as fh:
						entries = fh.readline().split()
						xoffset = float(entries[0])
						yoffset = float(entries[1])
						self.logger.info(telid + ": offset file found, applying offset to fiber position (" + str(xoffset) + "," + str(yoffset) + ")")
				else:
					xoffset = 0.0
					yoffset = 0.0

				p.setPoint((camera.fau.xfiber+xoffset,camera.fau.yfiber+yoffset))
				pfast.setPoint((camera.fau.xfiber+xoffset,camera.fau.yfiber+yoffset))

				curpos = np.array([xstar,ystar])
				tvals = np.append(tvals,i)
				xvals = np.append(xvals, curpos[0])
				yvals = np.append(yvals, curpos[1])
				
				# make sure it's actually converging
				if not camera.fau.acquired:
					body = 'Dear benevolent humans,\n\n'\
					    'My acquisition is not converging. The rotator position may need to be recalibrated for ' + telid + '. \n\n'\
					    'Love,\nMINERVA'
					if len(xvals) > 1 and len(yvals) > 1:
						if abs(camera.fau.xfiber+xoffset-curpos[0]) > 20:
							# if it was better before, send an email -- it's running away!
							if abs(xvals[-2] - (camera.fau.xfiber + xoffset)) < abs(xvals[-1] - (camera.fau.xfiber + xoffset)):
								mail.send('Acquisition not converging for ' + telid,body,level='serious',directory=self.directory)
								self.logger.info(telid + ": Acquisition not converging, check rotator calibration")
						if abs(camera.fau.yfiber+yoffset-curpos[1]) > 20:
							if abs(yvals[-2] - (camera.fau.yfiber + yoffset)) < abs(yvals[-1] - (camera.fau.yfiber + yoffset)):
								mail.send('Acquisition not converging for ' + telid,body,level='serious',directory=self.directory)
								self.logger.info(telid + ": Acquisition not converging, check rotator calibration")

					# TODO:
					# if we see this often, we probably want to automatically recalibrate the rotator!

				filterx=camera.fau.filterdata(xvals, N=camera.fau.smoothing)
				filtery=camera.fau.filterdata(yvals, N=camera.fau.smoothing)
				filtercurpos=np.array([filterx, filtery])
				separation = camera.fau.dist(camera.fau.xfiber+xoffset-curpos[0], camera.fau.yfiber+yoffset-curpos[1])*camera.fau.platescale
				self.logger.info(telid + ": Target is at (" + str(curpos[0]) + ',' + str(curpos[1]) + "), " + str(separation) + '" away from the fiber (' + str(camera.fau.xfiber) + "," + str(camera.fau.yfiber) + ") -- tolerance is " + str(camera.fau.acquisition_tolerance) + '"')
 				if separation < camera.fau.acquisition_tolerance:
					self.logger.info(telid + ": Target acquired")
					camera.fau.acquired = True
					if acquireonly:
						# tell the calling function it has successfully acquired
						return True
					elif self.red:
						pass
						# take a subframe
						#xc = camera.fau.xfiber+xoffset
						#yc = camera.fau.yfiber+yoffset
						#boxsize = 50
						#camera.fau.set_roi(x1=xc-boxsize, x2=xc+boxsize, y1=yc-boxsize, y2=yc+boxsize)
				elif self.red:
					pass
					# full frame
					#camera.fau.set_roi()
					

				if separation < camera.fau.bp:
                                        #note units are arc-seconds here in the "if"
					updateval = p.update(filtercurpos)
					self.logger.info(telid + ": Using slow loop")
					fast = False
				else:
					self.logger.info(telid + ": Using fast loop")
					updateval = pfast.update(filtercurpos)
					fast = True

				telescopeStatus = telescope.getStatus()

				# position angle on the sky
				# PA = parallactic angle - mechanical rotator position + field rotation offset
				offset = float(telescope.rotatoroffset[telescope.port['FAU']])
				if artificial:
					PA = float(telescope.getRotatorStatus(m3port,status=telescopeStatus).position) - offset
				else:
					parangle = telescope.parangle(useCurrent=True, status=telescopeStatus)
					PA = parangle - float(telescope.getRotatorStatus(m3port,telescopeStatus=telescopeStatus).position) + offset
				self.logger.info(telid + ': PA = '+str(PA))

				# Rotate the PID value by the negative of the rotation angle
				updateval= np.dot(camera.fau.rotmatrix(-PA), updateval)
				error[i,:] = np.array(p.error)
                
				# correction in arcsec 
				telupdateval = updateval*camera.fau.platescale

				if guiding == True:
					dec = utils.ten(telescopeStatus.mount.dec_2000)
					if artificial:
						telescope.mountOffsetAltAzFixed(-telupdateval[0]/math.cos(dec*math.pi/180.0),-telupdateval[1])
					else:
						# if we're using the AO unit and the object is already acquired, send commands to the tip/tilt
						if ao and camera.fau.acquired: 
							self.logger.info("Guiding by AO " + str(telupdateval[1]) + '" North, ' + str(telupdateval[0]) + '" East')
							status = str(camera.moveAO(-telupdateval[1],-telupdateval[0])) # in arcsec
							if status == False:
								self.logger.error("AO move failed")
								
							# if we exceeded the limits of the AO, home the AO and recenter with the mount 
							if (status.split())[0] == 'Limits_Reached':
								self.logger.info("AO limits reached; recentering")
								north, east = camera.get_north_east()
							
								if north == -telupdateval[1] and east == -telupdateval[0]:
									self.logger.info("AO already home and requested move out of AO range. Guiding by mount "  + str(telupdateval[1]) + '" North, ' + str(telupdateval[0]) + '" East')
									telescope.mountOffsetRaDec(-telupdateval[0]/math.cos(dec*math.pi/180.0),-telupdateval[1])
									camera.homeAO() # this is a dumb way to zero the tallies...
									# wait for mount to settle
									time.sleep(0.3)
									telescope.inPosition(m3port=m3port, derotate=False, tracking=True)
								elif north != None and east != None:
									self.logger.info("AO limits reached; recentering with mount and homing AO")
									self.logger.info("Moving mount by "  + str(north) + '" North, ' + str(east) + '" East')

									# changed sign of these corrections on 8/1/2020
									# changed back on 9/4/2020
									telescope.mountOffsetRaDec(east/math.cos(dec*math.pi/180.0),north)
									camera.homeAO()
									time.sleep(0.3)
									telescope.inPosition(m3port=m3port, derotate=False, tracking=True)
								else:
									self.logger.info("AO limits reached; recentering")
									camera.homeAO()
									time.sleep(0.1)

						else: 		
							self.logger.info("Guiding by Mount "  + str(telupdateval[1]) + '" North, ' + str(telupdateval[0]) + '" East')
							# otherwise, send commands to the mount
							telescope.mountOffsetRaDec(-telupdateval[0]/math.cos(dec*math.pi/180.0),-telupdateval[1])
							# wait for mount to settle
							time.sleep(0.3)
							telescope.inPosition(m3port=m3port, derotate=False, tracking=True)

#					if fast:
#						time.sleep(5)
#					else:
#						time.sleep(1)

				self.logger.debug(telid + ": PID LOOP: " + 
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

				self.logger.debug(telid + ": Curpos " + str(curpos[0])+"   "+str(curpos[1]))
				self.logger.debug(telid + ": distance from target: " +str(round(camera.fau.dist(camera.fau.xfiber+xoffset-curpos[0], camera.fau.yfiber+yoffset-curpos[1]),2)))
				self.logger.debug(telid + ": Updatevalue: " + str(updateval[0])+" "+str(updateval[1]))
				self.logger.debug(telid + ": Commanding update: " + str(telupdateval[0])+" "+str(telupdateval[1]))
				if i >50:
					meanx = np.mean((xvals)[50:])
					meany = np.mean((yvals)[50:])
					stdx  = np.std( (xvals)[50:])
					stdy  = np.std( (yvals)[50:])

					self.logger.debug(telid + ": Mean x position  " + str(meanx))
					self.logger.debug(telid + ": Std x position  " + str(stdx))
					self.logger.debug(telid + ": Mean y position  " + str(meany))
					self.logger.debug(telid + ": Std y position  " + str(stdy))
				else:
					self.logger.debug(telid + ": Building up statistics")

			i=i+1

		# The target is no longer acquired
		camera.fau.acquired = False
		return True

	def calibrate_ao(self, telid, exptime=1):
		gain=0.75
		camera = utils.getCamera(self,telid)
		telescope = utils.getTelescope(self,telid)
		xsize = camera.fau.x2
		ysize = camera.fau.y2
		platescale = camera.fau.platescale
		m3port = telescope.port['FAU']

		# move the rotator to skypa = 0
		telescope.rotatorStartDerotating(m3port)
		telescope.rotatorMovePA(0.0,m3port,wait=True)

		# confirm skypa = 0 by moving telescope
		t0 = datetime.datetime.utcnow()
		filename = camera.take_image(exptime=exptime,objname="aoCal_telcheck",fau=True)
		overhead = (datetime.datetime.utcnow() - t0).total_seconds() - exptime
#		self.logger.info("It took " + str(overhead) + " seconds to run 'take_image'")

		# locate star
                datapath = telescope.datadir + self.night + '/'
                x1, y1 = utils.findBrightest(datapath + filename)
                if x1 == None or y1 == None: 
			x1 = xsize/2.0
			y1 = ysize/2.0
#			return False
		print filename, x1, y1

                # the longer I can slew, the more accurate the calculation
                # calculate how far I can move before hitting the edge
                # must assume random orientation
                maxmove = min([x1,xsize-x1,y1,ysize-y1])*platescale

		# jog telescope by 80% of the maximum move in +RA (this should be -X)
                status = telescope.getStatus()
                dec = utils.ten(status.mount.dec)*math.pi/180.0
                telescope.mountOffsetRaDec(-maxmove*gain/math.cos(dec),0.0)

		if telescope.inPosition(m3port=m3port, tracking=True, derotate=True):
                        telescope.logger.info('Finished jog')

                # take exposure
                filename = camera.take_image(exptime=exptime,objname="aoCal_telcheck",fau=fau)

                # locate star
                datapath = telescope.datadir + self.night + '/'
                x2, y2 = utils.findBrightest(datapath + filename)
                if x2 == None or y2 == None: 
			x2 = xsize
			y2 = ysize/2.0
#			return False

                print filename, x2, y2

		tol = 5.0
                imagepa = math.atan2(y2-y1,x2-x1)*180.0/math.pi
		self.logger.info('Sky PA at ' + str(imagepa))
		if abs(imagepa) > tol: 
			self.logger.error('Calibration failed; skyPA at ' + str(imagepa) + ' but it should be at 0. Check the rotator home and offset calibration')
			ipdb.set_trace()
			
		# move back to original position
                telescope.mountOffsetRaDec(maxmove*gain/math.cos(dec),0.0)
		if telescope.inPosition(m3port=m3port, tracking=True, derotate=True):
                        telescope.logger.info('Finished jog')		

		# home the AO
		camera.homeAO()
		northtot = 0.0
		easttot = 0.0

		# move the telescope in a cross
		positions = [0,10,10,10,10,-10,-10,-10,-10,-10,-10,-10,-10,10,10,10,10]
		for axis in [1,2]:
			for move in positions:
				if axis == 1: 
					north = move
					east = 0.0
				else:
					north = 0.0
					east = move

				northtot+= north
				easttot+= east

				self.logger.info("moving mount " + str(north) + ',' + str(east))
				telescope.mountOffsetRaDec(east, north)

				# wait for it to settle
				time.sleep(0.1)

				if telescope.inPosition(m3port=m3port, tracking=True, derotate=True):
					telescope.logger.info('Finished jog')

				# take exposure
				filename = camera.take_image(exptime=exptime,objname="TelCal",fau=True)

				# locate star
				datapath = telescope.datadir + self.night + '/'
				x1, y1 = utils.findBrightest(datapath + filename)
				if x1 == None or y1 == None: 
					x1 = xsize/2.0
					y1 = ysize/2.0
#					return False

				self.logger.info("Star found in " + filename + " at " + str(x1) + ',' + str(y1) + " for position " + str(northtot) + ',' + str(easttot))

		# now move the AO in the same sort of cross
		for axis in [1,2]:
			for move in positions:
				if axis == 1: 
					north = move*0.128
					east = 0.0
				else:
					north = 0.0
					east = move*0.128

				northtot+= north
				easttot+= east

#				# n20200105
#				rotoffset = 30.0*math.pi/180.0 # 238-306
#				rotoffset = -30.0*math.pi/180.0 # 309-342
#				rotoffset = 210.0*math.pi/180.0 # 344-378
#				rotoffset = 150.0*math.pi/180.0 # 380-414
#				rotoffset = -45.0*math.pi/180.0 # 416-450
#				rotoffset = 45.0*math.pi/180.0 # 452-486
#				rotoffset = 0.0*math.pi/180.0 # 488-522
#				north = -(ymove*math.cos(rotoffset) - xmove*math.sin(rotoffset))
#				east  =  (ymove*math.sin(rotoffset) + xmove*math.cos(rotoffset))


				# move the AO by its tip/tilt
				self.logger.info("moving AO " + str(north) + ',' + str(east))
				if not camera.moveAO(north,east): # in arcsec units
					self.logger.info('move not allowed; cannot calibrate')
					ipdb.set_trace()

				# wait for it to settle
				time.sleep(0.1)

				# take exposure
				filename = camera.take_image(exptime=exptime,objname="aoCal",fau=True)

				# locate star
				datapath = telescope.datadir + self.night + '/'
				x1, y1 = utils.findBrightest(datapath + filename)
				if x1 == None or y1 == None: 
					x1 = xsize/2.0
					y1 = ysize/2.0
#					return False

				self.logger.info("Star found in " + filename + " at " + str(x1) + ',' + str(y1) + " for position " + str(northtot) + ',' + str(easttot))
		return
			

		# take exposure
                filename = camera.take_image(exptime=exptime,objname="aoCal",fau=True)

                # locate star
                x2, y2 = utils.findBrightest(datapath + filename)
                if x2 == None or y2 == None: return False

                print filename, x2, y2

                rotatorStatus = telescope.getRotatorStatus(m3port)
                rotpos = float(rotatorStatus.position)
                parang = telescope.parangle(useCurrent=True)

                # calculate rotator angle
		rotoff = float(telescope.rotatoroffset[m3port])
		skypa = (rotoff + float(parang) - float(rotpos) + 360.0) % 360

                imagepa = math.atan2(y2-y1,x2-x1)*180.0/math.pi
		aooff = (imagepa + skypa + 360) % 360 # nope -- very far off
		aooff = (imagepa - skypa + 360) % 360


                #rotoff = (skypa - float(parang) + float(rotpos) + 360.0) % 360

		platescale_measured = math.sqrt((x2-x1)**2 + (y2-y1)**2)/40.0

                if x1 == x2 and y1 == y2:
                        self.logger.error("Same image! Do not trust! WTF?")
                        return -999

                self.logger.info("Found stars at (" + str(x1) + "," + str(y1) + " and (" + str(x2) + "," + str(y2) + ")")
                self.logger.info("The Rotator position is " + str(rotpos) + ' degrees')
                self.logger.info("The parallactic angle is " + str(parang) + ' degrees')
                self.logger.info("The rotator offset is " + str(rotoff) + ' degrees')
                self.logger.info("The Sky PA is " + str(skypa) + ' degrees')
                self.logger.info("The Image PA is " + str(imagepa) + ' degrees')
                self.logger.info("The AO offset is " + str(aooff) + ' degrees')
                self.logger.info("The measured platescale is " + str(platescale_measured) + ' pixels/step')

	'''
	rasters the position of the fiber in a spiral from the nominal position 
	while guiding
	stepsize = size of each step, in pixels, 
	boxsize = size of the box, in steps
	dwelltime = the time to stay at each position
	'''
	def raster(self, telid, stepsize=1.0, maxx=10.0,maxy=10.0, dwelltime=120.0):

		telescope = utils.getTelescope(self,telid)
		offset_file = self.base_directory + '/' + telid + '_fiber_offset.txt'
		x = y = 0.0
                dx = 0.0*stepsize
                dy = -1.0*stepsize

                for i in range(int(math.ceil(max(maxx/stepsize*2.0+1,maxy/stepsize*2.0+1)**2))):
                        if (-maxx <= x <= maxx) and (-maxy <= y <= maxy):

				# update the offset file
                                self.logger.info("setting guide offset to (" + str(x) + ',' + str(y) + ')')
				with open(offset_file,'w') as f: f.write(str(x) + ' ' + str(y) + '\n')
				
				# wait here
				time.sleep(dwelltime)
				
			# the magic that makes it spiral
			if x==y or (x < 0 and x == -y) or (x > 0 and x ==stepsize-y):
				dx,dy=-dy,dx

			# define the next step
			x,y=x+dx,y+dy

                        if telescope.abort: break

		# reset to no offset
		with open(offset_file,'w') as f: f.write('0 0\n')

	def guide(self,filename, reference):

		threshhold = 60.0 # maximum offset in X or Y (larger corrections will be ignored)
		maxangle = 5.0 # maximum offset in theta (larger corrections will be ignored)

		# which telescope is this?
		telid = filename.split('.')[1]
		telescope = utils.getTelescope(self,telid)
		telescopeStatus = telescope.getStatus()
		m3port = telescopeStatus.m3.port

		if os.path.exists("disableGuiding." + telid + ".txt"):
			self.logger.info("Guiding disabled")
			return None

		if reference == None:
			self.logger.info("No reference frame defined yet; using " + filename)
			reference = self.getstars(filename)
			if len(reference[:,0]) < 6:
				self.logger.error("Not enough stars in reference frame")
				return None
			return reference

		self.logger.info("Extracting stars for " + filename)
		stars = self.getstars(filename)
		if len(stars[:,0]) < 6:
			self.logger.error("Not enough stars in frame")
			return reference

		# proportional servo gain (apply this fraction of the offset)
		gain = 0.66

		# get the platescale from the header
		hdr = pyfits.getheader(filename)
		platescale = float(hdr['PIXSCALE'])
		dec = float(hdr['CRVAL2'])*math.pi/180.0 # declination in radians

		arg = max(min(-float(hdr['CD1_1'])*3600.0/platescale,1.0),-1.0)
		PA = math.acos(arg) # position angle in radians
		self.logger.info("Image PA=" + str(PA))

		m0 = 22
		x = stars[:,0]
		y = stars[:,1]
		mag = -2.5*np.log10(stars[:,2])+m0
		
		xref = reference[:,0]
		yref = reference[:,1]
		magref = -2.5*np.log10(reference[:,2])+m0

		self.logger.info("Getting offset for " + filename)
		dx,dy,scale,rot,flag,rmsf,nstf = self.findoffset(x, y, mag, xref, yref, magref)

		self.logger.info("dx=" + str(dx) + ", dy=" + str(dy) + ", scale=" + str(scale) +
				 ", rot=" + str(rot) + ", flag=" + str(flag) +
				 ", rmsf=" + str(rmsf) + ", nstf=" + str(nstf))
    
		if abs(dx) > threshhold or abs(dy) > threshhold or abs(rot) > maxangle:
			self.logger.error("Offset too large; ignoring")
			return reference

		# adjust the rotator angle (sign?)
		self.logger.info("Adjusting the rotator by " + str(rot*gain) + " degrees")
		telescope.rotatorIncrement(rot*gain,m3port)

		# adjust RA/Dec (need to calibrate PA)
		deltaRA = -(dx*math.cos(PA) - dy*math.sin(PA))/math.cos(dec)*platescale*gain
		deltaDec = (dx*math.sin(PA) + dy*math.cos(PA))*platescale*gain
		self.logger.info("Adjusting the RA,Dec by " + str(deltaRA) + "," + str(deltaDec))
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
                       
                mail.send("The iodine stage is not moving.",body,level='serious',directory=self.directory)
                
                        
        #S Here is the general spectrograph equipment check function.
	#S Somethings, like turning lamps on, need to be called before. More
	#S to develop on this
	#TODO TODO
        def spec_equipment_check(self,target):

		# make sure the back light is off and out of the way
		self.spectrograph.backlight_off()

		kwargs = {
			'locationstr':'in',
			}
                #S Desired warmup time for lamps, in minutes
                #? Do we want separate times for each lamp, both need to warm for the same rightnow
                WARMUPMINUTES = 0.0#10.
                #S Convert to lowercase, just in case.
                objname = target['name'].lower()
                #S Some logic to see what type of spectrum we'll be taking.

		#S Turn on the Iodine cell heater 
		if not self.red:
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
                        i2stage_move_thread = PropagatingThread(target = self.ctrl_i2stage_move,kwargs=kwargs)
			i2stage_move_thread.name = "Kiwispec (control->spec_equipmentcheck->ctrl_i2sage_move (ThAr))"
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
			if not self.red:
				i2stage_move_thread = PropagatingThread(target = self.ctrl_i2stage_move,kwargs=kwargs)
				i2stage_move_thread.name = "Kiwispec (control->spec_equipmentcheck->ctrl_i2sage_move (slitflat))"
				i2stage_move_thread.start()

                        # Configure the lamps
#			self.logger.warning("*** Slit flat LED disabled ***")
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

			if not self.red:
				self.logger.info('Waiting on i2stage_move_thread')
				i2stage_move_thread.join()
                elif 'fiberflat' in target['name']:
                        #S Move the I2 stage out of the way of the slit.
			if target['i2']:
				kwargs['locationstr'] = 'in'
			else:
				kwargs['locationstr'] = 'out'
			if not self.red:
				i2stage_move_thread = PropagatingThread(target = self.ctrl_i2stage_move,kwargs=kwargs)
				i2stage_move_thread.name = "Kiwispec (control->spec_equipmentcheck->ctrl_i2sage_move (fiberflat))"
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
			if not self.red:
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
			if not self.red:
				kwargs['locationstr'] = 'in'
				i2stage_move_thread = PropagatingThread(target = self.ctrl_i2stage_move,kwargs=kwargs)
				i2stage_move_thread.name = "Kiwispec (control->spec_equipmentcheck->ctrl_i2sage_move (bias/dark))"
				i2stage_move_thread.start()
				#TODO Calibration shutter closed
				self.logger.info('Waiting on i2stage_move_thread')
				i2stage_move_thread.join()

                #S Let's do some science!
                #S The cell heater should be turned on before starting this, to give
                #S it time to warm up. It should really be turned on at the beginning
                #S of the night, but just a reminder.
                else:
                        #Configure the lamps
#                        self.spectrograph.thar_turn_off()
#                        self.spectrograph.flat_turn_off()
                        self.spectrograph.led_turn_off()


			if not self.red:
				#S Move the iodine either in or out, as requested
				if 'i2manualpos' in target.keys():
					kwargs['position'] = target['i2manualpos']
				elif target['i2']:
					kwargs['locationstr'] = 'in'
				else:
					kwargs['locationstr'] = 'out'
				i2stage_move_thread = PropagatingThread(target = self.ctrl_i2stage_move,kwargs=kwargs)
				i2stage_move_thread.name = "Kiwispec (control->spec_equipmentcheck->ctrl_i2sage_move)"
				i2stage_move_thread.start()
				
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

		tstart = datetime.datetime.utcnow()
		imaging_thread = PropagatingThread(target = self.spectrograph.take_image, kwargs=kwargs)
		if self.red: imaging_thread.name = "MRED"
		else: imaging_thread.name = "Kiwispec"
		imaging_thread.name += ' (control->takeSpectrum->spectrograph->take_image)'
		imaging_thread.start()

		alltels = []
		for telescope in self.telescopes:
			alltels.append(telescope.id)

		f = self.getHdr(target,alltels,None)
		for dome in self.domes:
			f = self.addDomeKeys(dome, f)

		header = json.dumps(f)
		
		self.spectrograph.logger.info('Waiting for spectrograph imaging thread')
		# wait for imaging process to complete
		imaging_thread.join()
		time.sleep(1)
		
		# write header for image
		if self.spectrograph.write_header(header):
			self.spectrograph.logger.info('Finished writing spectrograph header')

			
			if not self.red:
				# rewrite the image to make it standard
				self.spectrograph.logger.info("Standardizing the FITS image")
				night = 'n' + datetime.datetime.utcnow().strftime('%Y%m%d')
				dataPath = '/Data/kiwispec/' + night + '/'

				#fix_fits(os.path.join(dataPath,self.spectrograph.file_name))
				fix_fits_thread = PropagatingThread(target = fix_fits, args = (os.path.join(dataPath,self.spectrograph.file_name),))
				fix_fits_thread.name = 'Kiwispec (control->take_spectrum->fix_fits)'
				fix_fits_thread.start()
			
			# tell the scheduler if we successfully observed a B star
			try:
				if target['bstar']: self.scheduler.bstarobserved=True			
				self.scheduler.record_observation(target,telescopes=tele_list,timeof=tstart)
			except:
				pass

			return self.spectrograph.file_name
                #ipdb.set_trace()

		self.spectrograph.logger.error('takeSpectrum failed: ' + self.spectrograph.file_name)
		return 'error'

	#take one image based on parameter given, return name of the image, return 'error' if fail
	#image is saved on remote computer's data directory set by imager.set_data_path()
	#TODO camera_num is actually telescope_num
	def takeFauImage(self,target,telid):
		self.logger.info('beginning of the FAU imaging thread')

		t0 = datetime.datetime.utcnow()

		dome = utils.getDome(self,telid)

		#S assign the camera
		camera = utils.getCamera(self,telid)
		camera.logger.info('starting the FAU imaging thread')

		telescope = utils.getTelescope(self,telid)

		#start imaging process in a different thread
		# translate offset from north/east (arcsec) to x y (pixels)
		try: north = target['acquisition_offset_north']
		except: north = 0.0
		try: east = target['acquisition_offset_east']
		except: east = 0.0
		
		if north != 0.0 and east != 0.0:

			m3port = telescope.port['FAU']
			rotoffset = float(telescope.rotatoroffset[m3port])
			parangle = telescope.parangle(useCurrent=True)
			PA = parangle - float(telescope.getRotatorStatus(m3port).position) + rotoffset
			PARad = PA*math.pi/180.0
			dy = (north*math.cos(-PARad) - east*math.sin(-PARad))/camera.fau.platescale # pixels
			dx = (north*math.sin(-PARad) + east*math.cos(-PARad))/camera.fau.platescale # pixels
			self.logger.info("Offset guiding. Requested offset was " + str(north) + '" North and ' + str(east) + '" East. The PA is ' + str(PA) + " degrees")
			self.logger.info("Offset guiding. Target star is offset from brighest by (" + str(dx) + "," + str(dy) + ") pixels")

			offset = (dx,dy)
		else: offset = (0.0,0.0)

		dataPath = telescope.datadir + self.night + '/'
		dataPath2 = telescope.datadir + utils.night(utc=True) + '/'

		kwargs = {'exptime':target['fauexptime'],'objname':target['name'],'fau':True, 'offset':offset}
		imaging_thread = PropagatingThread(target = camera.take_image, kwargs = kwargs)
		imaging_thread.name = camera.telid + ' (control->takeFauImage->imager->take_image)'
#		camera.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 10')
		imaging_thread.start()
		dateobs = datetime.datetime.utcnow()
		
		# Prepare header while waiting for imager to finish taking image
		try:
#			camera.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 11')
			f = self.getHdr(target, [telid], dome, fau=True)
#			camera.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 12')
			# add the EXPTIME and DATE-OBS keywords
			f['DATE-OBS'] = (dateobs.strftime('%Y-%m-%dT%H:%M:%S.%f'),'observation start, UTC')
			f['EXPTIME'] = (target['fauexptime'],'Exposure time in seconds')
		except:
			self.logger.exception('error getting header keywords')
			ipdb.set_trace()
			
		header = json.dumps(f)

		camera.logger.info('waiting for imaging thread')
		# wait for imaging process to complete
		imaging_thread.join(target['fauexptime']+5.0)
		camera.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 12.5')
		
		if imaging_thread.isAlive():
			camera.logger.error('takeImage timed out: ' + camera.guider_file_name)
			return 'error'

		# write header for image 
		if camera.write_header(header,guider=True):
			timeout = 3.0
			timeElapsed = 0.0
			tstart = datetime.datetime.utcnow()
			camera.logger.info('finish writing image header for ' + camera.guider_file_name)
			while not os.path.exists(dataPath + camera.guider_file_name) and not os.path.exists(dataPath2 + camera.guider_file_name) and timeElapsed < timeout:
				time.sleep(0.001)
				timeElapsed = (datetime.datetime.utcnow() - tstart).total_seconds()
#			camera.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 13')
			if os.path.exists(dataPath + camera.guider_file_name): return camera.guider_file_name
			if os.path.exists(dataPath2 + camera.guider_file_name): return camera.guider_file_name

		camera.logger.error('takeImage failed: ' + camera.guider_file_name)
		return 'error'	

	def addSpectrographKeys(self, f, target=None):
		
		# blank keys will be filled in from the image when it's taken
#                f['SIMPLE'] = 'True'
#                f['BITPIX'] = (16,'8 unsigned int, 16 & 32 int, -32 & -64 real')
#                f['NAXIS'] = (2,'number of axes')
#                f['NAXIS1'] = (0,'Length of Axis 1 (Columns)')
#                f['NAXIS2'] = (0,'Length of Axis 2 (Rows)')
#                f['BSCALE'] = (1,'physical = BZERO + BSCALE*array_value')
#                f['BZERO'] = (0,'physical = BZERO + BSCALE*array_value')
#                f['DATE-OBS'] = ("","UTC at exposure start")
                f['EXPTIME'] = ("","Exposure time in seconds")               # derived from TIME keyword
                f['MEXPTIME'] = ("","Maximum Exposure time in seconds")      # PARAM24/1000
		f['EXPFLUX'] = ("","Exposure meter flux during exposure in counts")
		try:
			mexpmeter = target['expmeter']
		except:
			mexpmeter = 'NA'
		f['MEXPFLUX'] = (mexpmeter,"Maximum Exposure meter flux in counts")
                f['SET-TEMP'] = ("UNKNOWN",'CCD temperature setpoint (C)')            # PARAM62 (in comments!)
                f['CCD-TEMP'] = ("UNKNOWN",'CCD temperature at start of exposure (C)')# PARAM0
                f['BACKTEMP'] = ("UNKNOWN","Camera backplate temperature (C)")        # PARAM1
                f['XPIXSZ'] = ("UNKNOWN",'Pixel Width (microns after binning)')
                f['YPIXSZ'] = ("UNKNOWN",'Pixel Height (microns after binning)')
                f['XBINNING'] = ("UNKNOWN","Binning factor in width")                  # PARAM18
                f['YBINNING'] = ("UNKNOWN","Binning factor in height")                 # PARAM22
                f['XORGSUBF'] = (0,'Subframe X position in binned pixels')      # PARAM16
                f['YORGSUBF'] = (0,'Subframe Y position in binned pixels')      # PARAM20
                f['IMAGETYP'] = ("UNKNOWN",'Type of image')
                f['SITELAT'] = (str(self.site.obs.lat),"Site Latitude")
                f['SITELONG'] = (str(self.site.obs.lon),"East Longitude of the imaging location")
                f['SITEALT'] = (self.site.obs.elevation,"Site Altitude (m)")
                f['JD'] = (0.0,"Julian Date at the start of exposure (UTC)")
                f['SWCREATE'] = ("SI2479E 2011-12-02","Name of the software that created the image")
                f['INSTRUME'] = ('KiwiSpec','Name of the instrument')
                f['OBSERVER'] = ('MINERVA Robot',"Observer")
                f['SHUTTER'] = ("UNKNOWN","Shuter Status")             # PARAM8
                f['XIRQA'] = ("UNKNOWN",'XIRQA status')                # PARAM9
                f['COOLER'] = ("UNKNOWN","Cooler Status")              # PARAM10
                f['CONCLEAR'] = ("UNKNOWN","Continuous Clear")         # PARAM25
                f['DSISAMP'] = ("UNKNOWN","DSI Sample Time")           # PARAM26
                f['ANLGATT'] = ("UNKNOWN","Analog Attenuation")        # PARAM27
                f['PORT1OFF'] = ("UNKNOWN","Port 1 Offset")            # PARAM28
                f['PORT2OFF'] = ("UNKNOWN","Port 2 Offset")            # PARAM29
                f['TDIDELAY'] = ("UNKNOWN","TDI Delay,us")             # PARAM32
                f['CMDTRIG'] = ("UNKNOWN","Command on Trigger")        # PARAM39
                f['ADCOFF1'] = ("UNKNOWN","Port 1 ADC Offset")         # PARAM44
                f['ADCOFF2'] = ("UNKNOWN","Port 2 ADC Offset")         # PARAM45
                f['MODEL'] = ("UNKNOWN","Instrument Model")            # PARAM48
                f['SN'] = ("UNKNOWN","Instrument SN")                  # PARAM49
                f['HWREV'] = ("UNKNOWN","Hardware Revision")           # PARAM50
                f['SERIALP'] =("UNKNOWN","Serial Phasing")             # PARAM51
                f['SERIALSP'] = ("UNKNOWN","Serial Split")             # PARAM52
                f['SERIALS'] = ("UNKNOWN","Serial Size,Pixels")        # PARAM53
                f['PARALP'] = ("UNKNOWN","Parallel Phasing")           # PARAM54
                f['PARALSP'] = ("UNKNOWN","Parallel Split")            # PARAM55
                f['PARALS'] = ("UNKNOWN","Parallel Size,Pixels")       # PARAM56
                f['PARDLY'] = ("UNKNOWN","Parallel Shift Delay, ns")   # PARAM57
                f['NPORTS'] = ("UNKNOWN","Number of Ports")            # PARAM58
                f['SHUTDLY'] = ("UNKNOWN","Shutter Close Delay, ms")   # PARAM59
                f['GAIN'] = (1.30,"SI Detector gain (e-/ADU)")
                f['RDNOISE'] = (3.63,"SI Detector read noise (e-)")

                                        
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
		try: pumpvalve = self.pdus[5].pumpvalve.status()
		except: pumpvalve = "UNKNOWN"
		try: ventvalve = self.pdus[5].ventvalve.status()
		except: ventvalve = "UNKNOWN"
		try: pump = self.pdus[4].pump.status()
		except: pump = "UNKNOWN"

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
					try: f['TEMPE'+str(i+1).zfill(2)] = (float(temps[i+4]), header[i] + ' Temperature (C)')
					except: 
						self.logger.exception('Error reading the thermal enclosure log')
						f['TEMPE'+str(i+1).zfill(2)] = ('UNKNOWN', header[i] + ' Temperature (C)')
				try: f['ENCSETP'] = (float(temps[3]),'Thermal enclosure set point (C)')
				except: f['ENCSETP'] = ('UNKNOWN','Thermal enclosure set point (C)')
			self.thermalenclosureemailsent = False
		else:
			if self.thermalenclosureemailsent:
				mail.send("Thermal enclosure logging died","Please restart me! Note that you must be logged in as the temp users, not as minerva",directory=self.directory)
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
		try: f['EXPMETER'] = (self.pdus[4].expmeter.status(),'Exposure meter powered?')
		except: f['EXPMETER'] = ('UNKNOWN','Exposure meter powered?')

		try: f['LEDLAMP'] = (self.pdus[4].ledlamp.status(),'LED lamp powered?')
		except: f['LEDLAMP'] = ('UNKNOWN','LED lamp powered?')
		
		try:
			c1 = utils.getCamera(self,'T1')
			f['XFIBER1'] = (c1.fau.xfiber,'X position of fiber on FAU')
			f['YFIBER1'] = (c1.fau.yfiber,'Y position of fiber on FAU')
		except:
			f['XFIBER1'] = ('UNKNOWN','X position of fiber on FAU')
			f['YFIBER1'] = ('UNKNOWN','Y position of fiber on FAU')
		try:
			c2 = utils.getCamera(self,'T2')
			f['XFIBER2'] = (c2.fau.xfiber,'X position of fiber on FAU')
			f['YFIBER2'] = (c2.fau.yfiber,'Y position of fiber on FAU')
		except:
			f['XFIBER2'] = ('UNKNOWN','X position of fiber on FAU')
			f['YFIBER2'] = ('UNKNOWN','Y position of fiber on FAU')
		try:
			c3 = utils.getCamera(self,'T3')
			f['XFIBER3'] = (c3.fau.xfiber,'X position of fiber on FAU')
			f['YFIBER3'] = (c3.fau.yfiber,'Y position of fiber on FAU')
		except:
			f['XFIBER3'] = ('UNKNOWN','X position of fiber on FAU')
			f['YFIBER3'] = ('UNKNOWN','Y position of fiber on FAU')
		try:
			c4 = utils.getCamera(self,'T4')
			f['XFIBER4'] = (c4.fau.xfiber,'X position of fiber on FAU')
			f['YFIBER4'] = (c4.fau.yfiber,'Y position of fiber on FAU')
		except:
			f['XFIBER4'] = ('UNKNOWN','X position of fiber on FAU')
			f['YFIBER4'] = ('UNKNOWN','Y position of fiber on FAU')
			
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

	def addDomeKeys(self,dome,f):
		if 'astrohaven' in dome.id:
			return self.addAstrohavenKeys(dome, f)
		else:
			return self.addAqawanKeys(dome, f)
		

	def addAstrohavenKeys(self, dome, f):
		domeopen = dome.isOpen()
		f['DOMEOPEN'] = (domeopen,"Astrohaven open")
		return f

	def addAqawanKeys(self,dome,f):
		
		try:
			if dome.id <> 'aqawan1' and dome.id <> 'aqawan2':
				self.logger.error("Invalid dome selected (" + str(dome) + ")")
				return f
		except:
			return f
			
		domeStatus = dome.status()

		domestr = str(dome.num)

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
		# monitor moved inside on 2/2017
#		f['MONITOR' + domestr] = (self.pdus[(dome-1)*2].monitor.status(),"Monitor on?")

		return f

	def addTelescopeKeys(self, target, tele_list, f, telescopeStatuses=None):

		t0 = datetime.datetime.utcnow()

		if type(tele_list) is int:
			tele_list = [tele_list]
		
                # loop over each telescope and insert the appropriate keywords
		moonpos = self.site.moonpos()
		moonra = float(moonpos[0])*180.0/math.pi
		moondec = float(moonpos[1])*180.0/math.pi
		moonphase = self.site.moonphase()
		f['MOONRA'] = (moonra, "Moon RA (J2000 deg)")    
		f['MOONDEC'] =  (moondec, "Moon Dec (J2000 deg)")
		f['MOONPHAS'] = (moonphase, "Moon Phase (Fraction)")    

                for telid in tele_list:
			
			# if there's only one telescope (i.e., imager), no need to specify
			if len(tele_list) == 1:	telstr = ""
			else: telstr = str(telid)[-1]

			telescope = utils.getTelescope(self,telid)
			if not telescope: continue
			camera = utils.getCamera(self,telid)
	
			try: telescopeStatus = telescopeStatuses[telid]
			except: telescopeStatus = telescope.getStatus()

			telra =utils.ten(telescopeStatus.mount.ra_2000)*15.0 # J2000 degrees
			teldec = utils.ten(telescopeStatus.mount.dec_2000) # J2000 degrees
			if teldec > 90.0: teldec = teldec-360 # fixes bug in PWI's dec

			az = float(telescopeStatus.mount.azm_radian)*180.0/math.pi
			alt = float(telescopeStatus.mount.alt_radian)*180.0/math.pi
			airmass = 1.0/math.cos((90.0 - float(alt))*math.pi/180.0)
			moonsep = ephem.separation((telra*math.pi/180.0,teldec*math.pi/180.0),(moonra*math.pi/180.0,moondec*math.pi/180.0))*180.0/math.pi

			m3port = telescopeStatus.m3.port
			if m3port == '1': 
				focuserStatus = telescopeStatus.focuser1
				rotatorStatus = telescopeStatus.rotator1	
			else: 
				focuserStatus = telescopeStatus.focuser2
				rotatorStatus = telescopeStatus.rotator2	

			try:
				if m3port == '0': defocus = "UNKNOWN"
				else: defocus = (float(focuserStatus.position) - float(telescope.focus[m3port]))/1000.0
			except:
				defocus = "UNKNOWN"
				self.logger.exception("What is going on?")

			# this has three(!) status calls embedded in it
			parang = telescope.parangle(useCurrent=True, status=telescopeStatus)

			rotpos = float(rotatorStatus.position)
			try: rotoff = float(telescope.rotatoroffset[m3port])
			except: rotoff = "UNKNOWN"
			try: skypa = float(parang) + float(rotoff) - float(rotpos)
			except: skypa = "UNKNOWN"
			#hourang = self.hourangle(target,telid=telid, status=telescopeStatus)
			hourang = telescope.hourangle(target=target, status=telescopeStatus)
			moonsep = ephem.separation((float(telra)*math.pi/180.0,float(teldec)*math.pi/180.0),moonpos)*180.0/math.pi

			# target ra, J2000 degrees
			if 'ra' in target.keys(): ra = float(target['ra'])*15.0 
			else: ra = telra
                        
                        # target dec, J2000 degrees
			if 'dec' in target.keys(): dec = float(target['dec'])
			else: dec = teldec

			if 'pmra' in target.keys(): pmra = float(target['pmra'])
			else: pmra = 'UNKNOWN' 

			if 'pmdec' in target.keys(): pmdec = float(target['pmdec'])
			else: pmdec = "UNKNOWN"

			if 'parallax' in target.keys(): parallax = float(target['parallax'])
			else: parallax = "UNKNOWN"

			if 'rv' in target.keys(): rv = float(target['rv'])
			else: rv = "UNKNOWN"

			#parang = -180.0/math.pi*math.atan2(-math.sin(hourang*math.pi/12.0),
			#math.cos(dec*math.pi/180.0)*math.tan(float(telescope.site.latitude)*math.pi/180.0)-
			#				    math.sin(dec*math.pi/180.0)*math.cos(hourang*math.pi/12.0))
			#self.logger.info('old parangle' + str(parang))
			#self.logger.info('new parangle' + str(parang2))

			# State can be:
			# INACTIVE -- Telescope is not requested for spectroscopy
			# FAILED -- Telescope was requested for spectroscopy but has failed
			# ACQUIRING -- Telescope was requested for spectroscopy but is still acquiring
			# GUIDING -- Telescope was requested for spectroscopy and is guiding
			# UNKNOWN -- We don't know; something went wrong
			if not camera.fau.guiding:
				state = 'INACTIVE'
			elif camera.fau.failed:
				state = 'FAILED'
			elif camera.fau.acquired and camera.fau.guiding:
				state = 'GUIDING'
			elif not camera.fau.acquired and camera.fau.guiding:
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
			f['OBJECT'  + telstr] = (target['name'],"Object name")
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
			f['FOCPOS'  + telstr] = (float(focuserStatus.position),"Focus Position (microns)")
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


	def getTelStatusThread(self, telescope, results, index):
		results[index] = telescope.getStatus()
			
	def getHdr(self,target,tele_list,dome,fau=False, fast=False):
		t0 = datetime.datetime.utcnow()

		#get header info into json format and pass it to imager's write_header method
		f = collections.OrderedDict()

		# Static Keywords
		f['SITELAT'] = str(self.site.obs.lat)
		f['SITELONG'] = (str(self.site.obs.lon),"East Longitude of the imaging location")
		f['SITEALT'] = (str(self.site.obs.elevation),"Site Altitude (m)")
		f['OBSERVER'] = ('MINERVA Robot',"Observer")
		if type(tele_list) is int:
			tel = tele_list
		else: 
			if len(tele_list) == 1:
				tel = tele_list[0]
			else: tel = 'ALL'

		telescopeStatuses = {}
		threads = []
		for telid in tele_list:
			telescope = utils.getTelescope(self,telid)
			status_thread = PropagatingThread(target=self.getTelStatusThread,args=(telescope,telescopeStatuses,telid,))
			status_thread.name = telid + ' (control->getHdr->getStatus)'
			status_thread.start()		
			threads.append(status_thread)

#		self.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 0')

		f['TELESCOP'] = (tel,"Telescope name")
		f['APTDIA'] = (700,"Diameter of the telescope in mm")
		f['APTAREA'] = (490000,"Collecting area of the telescope in mm^2")
                f['FOCALLEN'] = (4560.0,"Focal length of the telescope in mm")

		f['ROBOVER'] = (self.gitNum,"Git commit number for robotic control software")

		if 'spectroscopy' not in target.keys(): target['spectroscopy'] = False

		# add either the keywords specific to the spectrograph or imager
		if target['spectroscopy']:
			if self.red:
				#TODO: add MRED spectrograph keys
				#f = self.addMredSpectrographKeys(f,target=target)
				pass				
			else:
				f = self.addSpectrographKeys(f,target=target)
				
			# make sure we're done getting the telescope Status
			for thread in threads:
				thread.join()

		else: 
			# make sure we're done getting the telescope Status
			for thread in threads:
				thread.join()

			# add the imager keywords (3 ms)
#			self.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 1')
			f = self.addImagerKeys(tele_list, f, telescopeStatuses=telescopeStatuses)

		if fau: 
			# add the FAU keywords (3 ms)
#			self.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 2')
			f = self.addImagerKeys(tele_list,f,fau=True, telescopeStatuses=telescopeStatuses)

		# add the telescope keywords (0.4 ms)
#		self.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 3')
		f = self.addTelescopeKeys(target, tele_list, f, telescopeStatuses=telescopeStatuses)
#		self.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 4')

		# add the dome keywords (1 ms)
		if dome != None: f = self.addDomeKeys(dome,f)
#		self.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 5')

		# add the weather keywords (30 ms)
		f = self.addWeatherKeys(f)
#		self.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 6')

		return f

	def addImagerKeys(self, tele_list, f, fau=False, telescopeStatuses=None):

		t0 = datetime.datetime.utcnow()

		if type(tele_list) is int:
			tele_list = [tele_list]

                for telid in tele_list:
			
			# if there's only one telescope (i.e., imager), no need to specify
			if len(tele_list) == 1:
				telstr = ""
			else:
				telstr = str(telid)[-1]

			telescope = utils.getTelescope(self,telid)
			if not telescope: continue
			camera = utils.getCamera(self,telid)
			f['TTON' + telstr] = (str(camera.isAOPresent()),"Active Optics Enabled?")
			
			# WCS
			if fau:
				platescale = camera.fau.platescale/3600.0*camera.fau.xbin
				xcenter = camera.fau.xcenter
				ycenter = camera.fau.ycenter
			else:
				platescale = camera.platescale/3600.0*camera.xbin # deg/pix
				xcenter = camera.xcenter
				ycenter = camera.ycenter

#			self.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 31')

			try: telescopeStatus = telescopeStatuses[telid]
			except: telescopeStatus = telescope.getStatus()

			if fau: m3port = telescope.port['FAU']
			else: m3port = telescope.port['IMAGER']

			if m3port == '1': 
				focuserStatus = telescopeStatus.focuser1
				rotatorStatus = telescopeStatus.rotator1	
			else: 
				focuserStatus = telescopeStatus.focuser2
				rotatorStatus = telescopeStatus.rotator2	

			try: rotpos = float(rotatorStatus.position)
			except: rotpos = "UNKNOWN"

			try: parang = float(telescope.parangle(useCurrent=True, status=telescopeStatus))
			except: parang = "UNKNOWN"

			try: rotoff = float(telescope.rotatoroffset[str(m3port)])
			except: rotoff = "UNKNOWN"

			try: PA = (float(parang) + float(rotoff) - float(rotpos))*math.pi/180.0
			except: PA = 0.0

#			self.logger.info('it took ' + str((datetime.datetime.utcnow() - t0).total_seconds()) + ' to get here 31')

			f['PIXSCALE' + telstr] = (platescale*3600.0,"Platescale in arc/pix, as binned")
			f['CTYPE1' + telstr] = ("RA---TAN","TAN projection")
			f['CTYPE2' + telstr] = ("DEC--TAN","TAN projection")
			f['CUNIT1' + telstr] = ("deg","X pixel scale units")
			f['CUNIT2' + telstr] = ("deg","Y pixel scale units")
		
			telra = utils.ten(telescopeStatus.mount.ra_2000)*15.0 # J2000 degrees
			teldec = utils.ten(telescopeStatus.mount.dec_2000) # J2000 degrees
			if teldec > 90.0: teldec = teldec-360 # fixes bug in PWI's dec

			f['CRVAL1' + telstr] = (float(telra),"RA of reference point")
			f['CRVAL2' + telstr] = (float(teldec),"DEC of reference point")
			f['CRPIX1' + telstr] = (float(xcenter),"X reference pixel")
			f['CRPIX2' + telstr] = (float(ycenter),"Y reference pixel")
			f['CD1_1' + telstr] = (float(-platescale*math.cos(PA)),"DL/DX")
			f['CD1_2' + telstr] = (float(platescale*math.sin(PA)),"DL/DY")
			f['CD2_1' + telstr] = (float(platescale*math.sin(PA)),"DM/DX")
			f['CD2_2' + telstr] = (float(platescale*math.cos(PA)),"DM/DY")

		return f

	def takeImage(self, target, telid, fau=False, piggyback=False):

		dome = utils.getDome(self,telid)
		telescope = utils.getTelescope(self,telid)
	 	
		#S assign the camera.
		camera = utils.getCamera(self,telid)
		camera.logger.info("starting imaging thread")

		#start imaging process in a different thread
		if piggyback:
			kwargs = {"filterInd":target['PBfilter'],'objname':target['name'],'piggyback':True}
			imaging_thread = PropagatingThread(target = camera.take_image, args = (target['PBexptime'],),kwargs=kwargs)
		else:
			kwargs = {"filterInd":target['filter'],'objname':target['name']}
			imaging_thread = PropagatingThread(target = camera.take_image, args = (target['exptime'],),kwargs=kwargs)
		
		imaging_thread.name = camera.telid + ' (control->takeImage->take_image)'
		imaging_thread.start()
		
		#Prepare header while waiting for imager to finish taking image
		f = self.getHdr(target, [telid], dome)

		header = json.dumps(f)

		camera.logger.info("waiting for imaging thread")

		# wait for imaging process to complete
		imaging_thread.join()
		
		# write header for image 
		if camera.write_header(header):
			camera.logger.info("finish writing image header")

			
			if piggyback or fau: filename = camera.guider_file_name
			else: filename = camera.file_name
			if not fau:
			        #S if the objname is not in the list of calibration or test names
				no_pa_list = ['bias','dark','skyflat','autofocus','testbias','test']
				if target['name'].lower() not in no_pa_list:
					# run astrometry asynchronously
					camera.logger.info("Running astrometry to find PA on " + filename)
					dataPath = telescope.datadir + self.site.night + '/'
					astrometryThread = PropagatingThread(target=self.getPA, args=(dataPath + filename,), kwargs={})
					astrometryThread.name = camera.telid + ' (control->takeImage->getPA)'
					astrometryThread.start()
			return filename
		
		if piggyback or fau: filename = camera.guider_file_name
		else: filename = camera.file_name
		camera.logger.error("takeImage failed: " + filename)
		return 'error'
	
	def doBias(self,num=11,telid=None,objectName = 'Bias', piggyback = False):
		#S Need to build dictionary to get up to date with new takeimage
		biastarget = {}
		#S just to check whether we canted to call the bias by another name.
		if objectName == 'Bias':
			biastarget['name'] = 'Bias'
		else:
			biastarget['name'] = objectName
		biastarget['filter'] = None
		biastarget['exptime'] = 0
		biastarget['PBexptime'] = 0
		camera = utils.getCamera(self,telid)
		for x in range(num):
			filename = 'error'
			while filename =='error':
				camera.logger.info('Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + '0' + ')')
				filename = self.takeImage(biastarget,telid , piggyback = piggyback)
			
	def doDark(self,num=11, exptime=[60],telid=None, piggyback = False):
		#S Need to build dictionary to get up to date with new takeimage
		darktarget = {}
		darktarget['name'] = 'Dark'
		darktarget['filter'] = None
		darktarget
		objectName = 'Dark'
		camera = utils.getCamera(self,telid)		
		for time in exptime:
			darktarget['exptime'] = time
			for x in range(num):
				filename = 'error'
				while filename == 'error':
					camera.logger.info('Taking ' + objectName + ' ' + str(x+1) + ' of ' + str(num) + ' (exptime = ' + str(time) + ')')
					filename = self.takeImage(darktarget,telid, piggyback = piggyback)
		
	#doSkyFlat for specified telescope
	def doSkyFlat(self,filters,morning=False,num=11,telid=None, piggyback = False):

		#S an empty target dictionary for taking images
		target = {}
		#S all images named SkyFlat
		target['name']='SkyFlat'

		dome = utils.getDome(self,telid)
		telescope = utils.getTelescope(self,telid)
		camera = utils.getCamera(self,telid)

		if piggyback:
			minSunAlt = camera.PBflatminsunalt
			maxSunAlt = camera.PBflatmaxsunalt

			targetCounts = camera.PBflattargetcounts
			biasLevel = camera.PBbiaslevel
			saturation = camera.PBsaturation
			maxExpTime = camera.PBflatmaxexptime
			minExpTime = camera.PBflatminexptime
			camerafilters = camera.PBfilters
                else:	
			minSunAlt = camera.flatminsunalt
			maxSunAlt = camera.flatmaxsunalt

			targetCounts = camera.flattargetcounts
			biasLevel = camera.biaslevel
			saturation = camera.saturation
			maxExpTime = camera.flatmaxexptime
			minExpTime = camera.flatminexptime
			camerafilters = camera.filters
	   
		# can we actually do flats right now?
		if datetime.datetime.now().hour > 12:
			# Sun setting (evening)
			if morning:
				self.logger.info('Sun setting and morning flats requested; skipping')
				return
			if self.site.sunalt() < minSunAlt:
				self.logger.info('Sun setting and already too low; skipping')
				return               
			self.site.obs.horizon = str(maxSunAlt)
			flatStartTime = self.site.obs.next_setting(ephem.Sun(),start=self.site.startNightTime, use_center=True).datetime()
			secondsUntilTwilight = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0
		else:
			# Sun rising (morning)
			if not morning:
				self.logger.info('Sun rising and evening flats requested; skipping')
				return
			if self.site.sunalt() > maxSunAlt:
				self.logger.info('Sun rising and already too high; skipping')
				return  
			self.site.obs.horizon = str(minSunAlt)
			flatStartTime = self.site.obs.next_rising(ephem.Sun(),start=self.site.startNightTime, use_center=True).datetime()
			secondsUntilTwilight = (flatStartTime - datetime.datetime.utcnow()).total_seconds() - 300.0
			
		if secondsUntilTwilight > 7200:
			self.logger.info('Twilight too far away (' + str(secondsUntilTwilight) + " seconds)")
			return

		# wait for twilight
		if secondsUntilTwilight > 0 and (self.site.sunalt() < minSunAlt or self.site.sunalt() > maxSunAlt):
			self.logger.info('Waiting ' +  str(secondsUntilTwilight) + ' seconds until Twilight')
			time.sleep(secondsUntilTwilight)

		# wait for the dome to open
		while not dome.isOpen():
			# exit if outside of twilight
			if self.site.sunalt() > maxSunAlt or self.site.sunalt() < minSunAlt: return
			self.logger.info("Dome closed; waiting for conditions to improve")
			time.sleep(30)

		# Now it's within 5 minutes of twilight flats
		self.logger.info('Beginning twilight flats')

		# make sure the telescope/dome is ready for obs
		if not telescope.initialize(tracking=True, derotate=True):
			telescope.recover()
		
		# start off with the extreme exposure times
		if morning: exptime = maxExpTime
		else: exptime = minExpTime

		# filters ordered from least transmissive to most transmissive
		# flats will be taken in this order (or reverse order in the morning)
		masterfilters = ['Calcium', 'H-Beta','H-Alpha','Ha','Y','U','up','zp','zs','B','I','ip','V','rp','R','gp','w','solar','air']
		if morning: masterfilters.reverse()  

		for filterInd in masterfilters:
			if filterInd in filters and filterInd in camerafilters:

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

						self.logger.info('Slewing to the optimally flat part of the sky (alt=' + str(Alt) + ', az=' + str(Az) + ')')
						telescope.mountGotoAltAz(Alt,Az)
						# flats are only useful for imagers
						telescope.m3port_switch(telescope.port['IMAGER'])

						if not telescope.inPosition(alt=Alt,az=Az,m3port=telescope.port['IMAGER'],pointingTolerance=3600.0,tracking=True, derotate=True):
							telescope.recover()
						else: inPosition=True

					# Take flat fields
					filename = 'error'
					#S Set the filter name to the current filter
					target['filter']=filterInd

					#S update/get the exposure time
					target['exptime'] = exptime

					#S new target dict implementation
					while filename == 'error' and dome.isOpen(): filename = self.takeImage(target,telid, piggyback = piggyback)
					
					# determine the mode of the image (mode requires scipy, use mean for now...)
					mode = camera.getMode(guider=piggyback)
					self.logger.info("image " + str(i+1) + " of " + str(num) + " in filter "\
								 + filterInd + "; " + filename + ": mode = " + str(mode) + " exptime = " \
								 + str(exptime) + " sunalt = " + str(self.site.sunalt()))

					# if way too many counts, it can roll over and look dark
					supersaturated = camera.isSuperSaturated(guider=piggyback)
					
					if mode >= saturation or supersaturated:
						# Too much signal
						self.logger.info("Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) +
								 '; sun altitude=' + str(self.site.sunalt()) +
								 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
						camera.remove()
						i-=1
						if exptime == minExpTime and morning:
							self.logger.info("Exposure time at minimum, image saturated, and " +
									 "getting brighter; skipping remaining exposures in filter " + filterInd)
							break
							
					elif mode < 6.0*biasLevel:
						# Too little signal
						self.logger.info("Flat deleted: exptime=" + str(exptime) + " Mode=" + str(mode) + 
								 '; sun altitude=' + str(self.site.sunalt()) +
								 "; exptime=" + str(exptime) + '; filter = ' + filterInd)
						camera.remove()
						i -= 1

						if exptime == maxExpTime and not morning:
							self.logger.info("Exposure time at maximum, not enough counts, and "+
									 "getting darker; skipping remaining exposures in filter " + filterInd)
							break
					if morning and self.site.sunalt() > maxSunAlt:
						self.logger.info("Sun rising and greater than maxsunalt; skipping")
						break
					if not morning and self.site.sunalt() < minSunAlt:
						self.logger.info("Sun setting and less than minsunalt; skipping")
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
						self.logger.info("Scaling exptime to " + str(exptime))
					i += 1

	### USE UTILS.SCHEDULEISVALID INSTEAD ###
	### this version is deprecated ###
	def scheduleIsValid(self, scheduleFile, email=True):

		if not os.path.exists(self.base_directory + '/schedule/' + scheduleFile):
			self.logger.error('No schedule file: ' + scheduleFile)
			return False

		emailbody = ''
		with open(self.base_directory + '/schedule/' + scheduleFile, 'r') as targetfile:
			linenum = 1
			line = targetfile.readline()
			try: CalibInfo = json.loads(line)
			except: CalibInfo = -1
			# check for malformed JSON code
			if CalibInfo == -1:
				self.logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
				emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
			else:
				requiredKeys = ['nbias','ndark','nflat','darkexptime','flatFilters','WaitForMorning']
				for key in requiredKeys:
					if key not in CalibInfo.keys():
						self.logger.error('Line 1: Required key (' + key + ') not present: ' + line)
						emailbody = emailbody + 'Line 1: Required key (' + key + ') not present: ' + line + '\n'

			linenum = 2
			line = targetfile.readline()
			try: CalibEndInfo = json.loads(line)
			except: CalibEndInfo = -1
			# check for malformed JSON code
			if CalibEndInfo == -1:
				self.logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
				emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
			else:
				requiredKeys = ['nbiasEnd','ndarkEnd','nflatEnd']
				for key in requiredKeys:
					if key not in CalibEndInfo.keys():
						self.logger.error('Line 2: Required key (' + key + ') not present: ' + line)
						emailbody = emailbody + 'Line 2: Required key (' + key + ') not present: ' + line + '\n'
						
			linenum = 3
			for line in targetfile:
				target = utils.parseTarget(line, logger=self.logger)
				
				# check for malformed JSON code
				if target == -1:
					self.logger.error('Line ' + str(linenum) + ': malformed JSON: ' + line)
					emailbody = emailbody + 'Line ' + str(linenum) + ': malformed JSON: ' + line + '\n'
				else:
					# check to make sure all required keys are present
					key = 'name'
					if key not in target.keys():
						self.logger.error('Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line)
						emailbody = emailbody + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line + '\n'
					else:
						if target['name'] == 'autofocus':
							requiredKeys = ['starttime','endtime']
						else:
							requiredKeys = ['starttime','endtime','ra','dec','filter','num','exptime','defocus','selfguide','guide','cycleFilter']
							
						for key in requiredKeys:
							if key not in target.keys():
								self.logger.error('Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line)
								emailbody = emailbody + 'Line ' + str(linenum) + ': Required key (' + key + ') not present: ' + line + '\n'
									
						if target['name'] <> 'autofocus':
							try:
								nnum = len(target['num'])
								nexptime = len(target['exptime'])
								nfilter = len(target['filter'])
								if nnum <> nexptime or nnum <> nfilter:
									self.logger.error('Line ' + str(linenum) + ': Array size for num (' + str(nnum) + '), exptime (' + str(nexptime) + '), and filter (' + str(nfilter) + ') must agree')
									emailbody = emailbody + 'Line ' + str(linenum) + ': Array size for num (' + str(nnum) + '), exptime (' + str(nexptime) + '), and filter (' + str(nfilter) + ') must agree\n'                            
							except:
								pass            
				linenum = linenum + 1
				if emailbody <> '':
					if email: mail.send("Errors in target file: " + scheduleFile,emailbody,level='serious',directory=self.directory)
					return False
		return True

	#if telid out of range or not specified, do science for all telescopes
	#S I don't think the above is true. Do we want to do something similar tp what
	#S telescope commands were switched to.
	def doScience(self,target,telid = None):

		dome = utils.getDome(self,telid)
		telescope = utils.getTelescope(self,telid)
			
		# if after end time, return
		if datetime.datetime.utcnow() > target['endtime']:
			self.logger.info("Target " + target['name'] + " past its endtime (" + str(target['endtime']) + "); skipping")
			return

		# if before start time, wait
		if datetime.datetime.utcnow() < target['starttime']:
			waittime = (target['starttime']-datetime.datetime.utcnow()).total_seconds()
			self.logger.info("Target " + target['name'] + " is before its starttime (" + str(target['starttime']) + "); waiting " + str(waittime) + " seconds")
			time.sleep(waittime)

		if 'positionAngle' in target.keys(): pa = target['positionAngle']
		else: pa = None

      		if target['name'] == 'pwi_autofocus':
			try: telescope.acquireTarget(target,pa=pa)
			except: pass
			telescope.inPosition(m3port=telescope.port['IMAGER'], tracking=True, derotate=True)
			telescope.autoFocus()
			return
		
		if target['name'] == 'autofocus':
			if 'spectroscopy' in target.keys():
				fau = True
			else: 
				fau = False
			telescope.inPosition(m3port=telescope.port['IMAGER'], tracking=True, derotate=True)
			try:
				newauto.autofocus(self,telid,target=target)
			except:
				telescope.logger.exception('Failed in autofocus')
		
		# slew to the target
		telescope.acquireTarget(target,pa=pa)
		if 'spectroscopy' in target.keys():
			if target['spectroscopy']:
				newfocus = float(telescope.focus[telescope.port['FAU']] )+ float(target['defocus'])*1000.0
			else:
				newfocus = float(telescope.focus[telescope.port['IMAGER']] )+ float(target['defocus'])*1000.0
		else:
			newfocus = float(telescope.focus[telescope.port['IMAGER']] )+ float(target['defocus'])*1000.0
		status = telescope.getStatus()
		m3port = telescope.port['IMAGER']
		focuserStatus = telescope.getFocuserStatus(m3port)
		if newfocus <> focuserStatus.position:
			self.logger.info("Defocusing Telescope by " + str(target['defocus']) + ' mm, to ' + str(newfocus))
			if not telescope.focuserMoveAndWait(newfocus,m3port):
				self.logger.info("Focuser failed to move; beginning recovery")
				telescope.recoverFocuser(newfocus, m3port)
				telescope.acquireTarget(target,pa=pa)

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
								self.logger.info('Enclosure closed; waiting for conditions to improve')
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
							if not telescope.inPosition(m3port=telescope.port['IMAGER'], tracking=True, derotate=True):
								self.logger.error('Telescope not in position, reacquiring target')
								telescope.acquireTarget(target,pa=pa)
							self.logger.info('Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " +
									 str(target['exptime'][j]) + ' second exposure of ' + target['name'] + ' in the ' +
									 target['filter'][j] + ' band') 

							#S new target dict takeImage
							filename = self.takeImage(temp_target,telid)

							if target['selfguide'] and filename <> 'error': reference = self.guide(telescope.datadir + self.site.night + '/' + filename,reference)
					
					
		else:
			# take all in each band, then loop over filters (e.g., B,B,B,V,V,V,R,R,R) 
			for j in range(len(target['filter'])):
				# cycle by number
				for i in range(target['num'][j]):
					filename = 'error'
					while filename == 'error':
						if dome.isOpen() == False:
							while dome.isOpen() == False:
								self.logger.info('Enclosure closed; waiting for conditions to improve')
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
						if not telescope.inPosition(m3port=telescope.port['IMAGER'], tracking=True, derotate=True):
							self.logger.debug('Telescope not in position, reacquiring target')
							telescope.acquireTarget(target,pa=pa)
							self.logger.info('Beginning ' + str(i+1) + " of " + str(target['num'][j]) + ": " +
									 str(target['exptime'][j]) + ' second exposure of ' + target['name'] +
									 ' in the ' + target['filter'][j] + ' band') 

						#S new target dict takeImage
						filename = self.takeImage(temp_target,telid)
						#S guide that thing
						datapath = telescope.datadir + self.site.night + '/'
						if target['selfguide'] and filename <> 'error': reference = self.guide(datapath + filename,reference)

		telescope.mountTrackingOff()

	#prepare logger and set imager data path
	def prepNight(self,telescope,email=True):

		# reset the night at 10 am local
		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
			today = today + datetime.timedelta(days=1.0)
		night = 'n' + today.strftime('%Y%m%d')

		# delete various files that shouldn't carry over from night to night
		# sunoverride, request, telescope_?.error, disableGuiding*.txt
		try: os.remove("disableGuiding." + telescope.id + ".txt")
		except: pass
		try: os.remove("telescope." + telescope.id + ".error")
		except: pass

		# check disk space on all machines; email warnings if low
		drives = ['/Data/t1/','/Data/t2/','/Data/t3/','/Data/t4/','/nas/','/Data/kiwispec','/']
		for drive in drives:
			s = os.statvfs(drive)
			free_space = s.f_bsize * s.f_bavail/1024./1024./1024. # GB
			print drive, free_space
			self.logger.info('Drive ' + drive + ' has ' + str(free_space) + ' GB remaining')
			if free_space < 20:
				self.logger.error('The disk space on a system critical drive (' + drive +
						  ') is low (' + str(free_space) + ' GB)')
				mail.send('Disk space on ' + drive + ' critically low','Dear Benevolent Humans,\n\n'+
					  'The disk space on a system critical drive (' + drive +
					  ') is critically low (' + str(free_space) + ' GB). '+
					  'Please free up space immediately or operations will be compromised.\n\n'+
					  'Love,\nMINERVA.',level='serious', directory=self.directory)
			elif free_space < 50:
				self.logger.warning('The disk space on a system critical drive (' + drive +
						    ') is low (' + str(free_space) + ' GB)')
				mail.send('Disk space on ' + drive + ' low','Dear Benevolent Humans,\n\n'+
					  'The disk space on a system critical drive (' + drive +
					  ') is low (' + str(free_space) + ' GB). '+
					  'Please free up space or operations may be compromised in the next ~week.\n\n'+
					  'Love,\nMINERVA.',level='normal', directory=self.directory)

		# check that kiwispec is configured correctly
		# check overscan set to 2090
		# check mode = 3
		# check cooler set to -90, camera within acceptable range
		# check exposure meter logging
		# check spectrograph pressure logging, pressure within acceptable range
		# check spectrograph temperature logging, temperature within acceptable range
		# check clocks?

		# confirm domeControl.py is running
		# confirm PT100.py is running
		

		#set correct path for the night
		self.logger.info("Setting up directories for " + night)
		self.imager_setDatapath(night,telescope.id)

		# turn off shutter heaters
		if not self.red and not self.south:
			self.logger.info('Turning off shutter heaters')
			try: self.pdus[0].heater.off()
			except: self.logger.exception("Turning off heater 1 failed")
			try: self.pdus[1].heater.off()
			except: self.logger.exception("Turning off heater 2 failed")
			try: self.pdus[2].heater.off()
			except: self.logger.exception("Turning off heater 3 failed")
			try: self.pdus[3].heater.off()
			except: self.logger.exception("Turning off heater 4 failed")

			for aqawan in self.domes:
				self.logger.info('Turning off lights in aqawan ' + str(aqawan.num))
				aqawan.lights_off()

		if email: mail.send(telescope.id + ' Starting observing','Love,\nMINERVA',directory=self.directory)
		
	def backup(self, telid, night=None):
		
		if night == None:
			night = self.site.night

		telescope = utils.getTelescope(self,telid)
		dataPath = telescope.datadir

		backupPath = '/home/minerva/backup/' + telid + '/' + night + '/'
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


	def endNight(self, telescope, email=True, night=None, kiwispec=True):

		#S This implementation should allow you to specify a night you want to 'clean-up',
		#S or just run end night on the current night. I'm not sure how it will act
		#S if you endnight on an already 'ended' night though.
		#S IF YOU WANT TO ENTER A PAST NIGHT:
		#S make night='nYYYYMMDD' for the specified date.
		if night == None:
			night = self.night

		if self.red:
			if os.path.exists(self.base_directory + '/minerva_library/astrohaven1.request.txt'): 
				os.remove(self.base_directory + '/minerva_library/astrohaven1.request.txt')

			if kiwispec: 
				dataPath = '/Data/mredspec/' + night + '/'
				objndx = 1
			else: 
				dataPath = telescope.datadir + night + '/'
				objndx = 2


		elif self.south:
			pass
		else:
			if os.path.exists(self.base_directory + '/minerva_library/aqawan1.request.txt'): 
				os.remove(self.base_directory + '/minerva_library/aqawan1.request.txt')
			if os.path.exists(self.base_directory + '/minerva_library/aqawan2.request.txt'): 
				os.remove(self.base_directory + '/minerva_library/aqawan2.request.txt')

			if kiwispec: 
				dataPath = '/Data/kiwispec/' + night + '/'
				objndx = 1
			else: 
				dataPath = telescope.datadir + night + '/'
				objndx = 2

		if not os.path.exists(dataPath): os.mkdir(dataPath)

		# park the scope
		self.logger.info("Parking Telescope")
		self.telescope_park(telescope.id)
#		self.telescope_shutdown(num)

		# Compress the data
		self.logger.info("Compressing data")
		if kiwispec: pass
		else: self.imager_compressData(telescope.id,night=night)


		# Turn off the camera cooler, disconnect
#		self.logger.info("Disconnecting imager")
# 		self.imager_disconnect()

                #TODO: Back up the data
#		if kiwispec: pass
#		else: self.backup(telescope.id,night=night)

		# copy schedule to data directory
		schedulename = self.base_directory + "/schedule/" + night + "." + telescope.id + ".txt"
		scheduleDest = dataPath + night + '.' + telescope.id + '.txt'
		if os.path.exists(schedulename):
			self.logger.info("Copying schedule file from " + schedulename + " to " + dataPath)
			try: shutil.copyfile(schedulename, scheduleDest)
			except: self.logger.exception("Could not copy schedule file from " + schedulename + " to " + scheduleDest)
		else:
			self.logger.info("No schedule for this telescope; skipping copy")

		# copy server logs to data directory
		logs = glob.glob('/Data/serverlogs/*/' + night + '/*.log')
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
                     try:
			obj = filename.split('.')[objndx]
			if not kiwispec and obj <> 'Bias' and obj <> 'Dark':
				obj += ' ' + filename.split('.')[3]
			if obj not in objects.keys():
				objects[obj] = 1
			else: objects[obj] += 1
                     except:
                        ipdb.set_trace()

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

		# these messages contain variables; trim them down so they can be consolidated
		toospecific = [('takeImage timed out', ''),
			       ('Autofocus failed, using best measured focus', ''),
			       ('The camera was unable to reach its setpoint','in the elapsed time'),
			       ('No hfr in','cat'),
			       ('Taking image failed, image not saved',''),
			       ('Focus position','out of range'),
			       ('failed to find fiber in image','using default'),
			       ('Error homing telescope',''),
			       ('backlight image not taken; using default',''),
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
			       ('Failed to open shutter 2: Success=FALSE, Heartbeat timer expired',''),
			       ('Fitted focus', 'was outside of limits'),
			       ('A1: Error reading the cloud page',''),
			       ('A2: Error reading the cloud page',''),
			       ('T1: Fitted focus',' was outside of limits'),
			       ('T2: Fitted focus',' was outside of limits'),
			       ('T3: Fitted focus',' was outside of limits'),
			       ('T4: Fitted focus',' was outside of limits'),
			       ('T1: Autofocus failed, using best measured focus',''),
			       ('T2: Autofocus failed, using best measured focus',''),
			       ('T3: Autofocus failed, using best measured focus',''),
			       ('T4: Autofocus failed, using best measured focus',''),
			       ('T1: Focuser',' not at requested position'),
			       ('T2: Focuser',' not at requested position'),
			       ('T3: Focuser',' not at requested position'),
			       ('T4: Focuser',' not at requested position'),
			       ('T1','Guide star not found'),
			       ('T2','Guide star not found'),
			       ('T3','Guide star not found'),
			       ('T4','Guide star not found'),
			       ('MRED','Guide star not found'),
			       ('A1: Failed to open shutter 1: Success=FALSE, Enclosure not in AUTO',''),
			       ('A1: Failed to open shutter 2: Success=FALSE, Enclosure not in AUTO',''),
			       ('A2: Failed to open shutter 1: Success=FALSE, Enclosure not in AUTO',''),
			       ('A2: Failed to open shutter 2: Success=FALSE, Enclosure not in AUTO','')]

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
							try: time = datetime.datetime.strptime(line.split()[0],"%Y-%m-%dT%H:%M:%S.%f")
							except: time = datetime.datetime.strptime(line.split()[0],"%Y-%m-%dT%H:%M:%S")
							try:
								value = float(line.split('=')[-1].strip())
								weatherstats[key].append((time,value))
							except: pass

		try: Pointing_plot_name = plot_pointing_error.plot_pointing_error(night)
		except: Pointing_plot_name = ''

		try: fits_plot_name = Plot_fits.plot_fits(night)
		except: fits_plot_name = ''

		try: af_plot_names = plot_autofocus(night)
		except: af_plot_names = []

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

#		ipdb.set_trace()

		try: weatherplotname = plotweather(self,night=night)
		except: weatherplotname = ''


		# run read_temps/run_yesterdays_temps.sh
		# attach /home/minerva/minerva-control/log/nYYYYMMDD/nYYYYMMDD.hvac.png
		process = subprocess.Popen(self.base_directory + '/minerva_library/read_temps/run_yesterdays_temps.sh', shell=True, stdout=subprocess.PIPE)
		process.wait()
		hvactempname = '/home/minerva/minerva-control/log/' + night + '/' + night + '.hvac.png'
		if not os.path.isfile(hvactempname): hvactempname = ''


		cmd = self.base_directory + '/minerva_library/runidl.sh "/Data/kiwispec/' + night + '/' + night + '.*.????.fits"'
		print cmd
		process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
		process.wait()
		filepath = '/Data/kiwispec/' + night + '/' + night + '.*.????.png'
		attachments = glob.glob(filepath)
		print filepath
		print attachments
		attachments.extend([weatherplotname,Pointing_plot_name,fits_plot_name,hvactempname])
		attachments.extend(af_plot_names)
		print attachments

		# email observing report
		if email: 
			subject = telescope.id + ' done observing'
			mail.send(subject,body,attachments=attachments,directory=self.directory)

#		print body


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
	def observingScript(self,telescope,piggyback=False):
		
		camera = utils.getCamera(self,telescope.id)
		
		#set up night's directory
		self.prepNight(telescope)
		scheduleFile = self.site.night + '.' + telescope.id + '.txt'
		if not utils.scheduleIsValid(self.base_directory + '/schedule/' + scheduleFile,logger=self.logger, directory=self.directory):
			mail.send("No schedule file for telescope " + telescope.id,'',level='serious',directory=self.directory)
			return False

		if not telescope.initialize(tracking=False, derotate=False):
			telescope.recover(tracking=False, derotate=False)

		#S Finally (re)park the telescope. 
		telescope.home()
		telescope.park()

		#TODO A useless bias
		#S do a single bias to get the shutters to close, a cludge till we can get there and
		#S check things out ourselves.
		self.doBias(num=1,telid=telescope.id,objectName='testBias')
		
		# wait for the camera to cool down
		camera.cool()

		CalibInfo,CalibEndInfo = self.loadCalibInfo(telescope.id)
		self.logger.info("done loading calib info")
		# Take biases and darks
		# wait until it's darker to take biases/darks
		readtime = 10.0

		# turn off both monitors
		#self.logger.info('Turning off monitors')
		#try: self.pdus[0].monitor.off()
		#except: self.logger.exception("Turning off monitor in aqawan 1 failed")
		#try: self.pdus[2].monitor.off()
		#except: self.logger.exception("Turning off monitor in aqawan 2 failed")



		self.logger.info("calculating calibration overheads")
		bias_seconds = CalibInfo['nbias']*readtime+CalibInfo['ndark']*sum(CalibInfo['darkexptime']) + CalibInfo['ndark']*readtime*len(CalibInfo['darkexptime']) + 600.0
		biastime = self.site.sunset() - datetime.timedelta(seconds=bias_seconds)
		waittime = (biastime - datetime.datetime.utcnow()).total_seconds()
		self.logger.info("done calculating calibration overheads")
		
		if waittime > 0:
			# Take biases and darks (skip if we don't have time before twilight)
			self.logger.info('Waiting until darker before biases/darks (' + str(waittime) + ' seconds)')
			time.sleep(waittime)
			#S Re-initialize, and turn tracking on. 
			self.doBias(CalibInfo['nbias'],telescope.id)
			self.doDark(CalibInfo['ndark'], CalibInfo['darkexptime'],telescope.id)
			
		dome = utils.getDome(self,telescope.id)

		# Take Evening Sky flats
		#S Initialize again, but with tracking on.
		if not telescope.initialize(tracking=True, derotate=True):
			telescope.recover(tracking=True, derotate=True)
		flatFilters = CalibInfo['flatFilters']
		self.doSkyFlat(flatFilters, False, CalibInfo['nflat'],telescope.id, piggyback=piggyback)
		
		# Wait until nautical twilight ends 
		timeUntilTwilEnd = (self.site.NautTwilEnd() - datetime.datetime.utcnow()).total_seconds()
		if timeUntilTwilEnd > 0:
			self.logger.info('Waiting for nautical twilight to end (' + str(timeUntilTwilEnd) + 'seconds)')
			time.sleep(timeUntilTwilEnd)

		while not dome.isOpen() and datetime.datetime.utcnow() < self.site.NautTwilBegin():
			self.logger.info('Enclosure closed; waiting for conditions to improve')
			time.sleep(60)

		# find the best focus for the night
		if datetime.datetime.utcnow() < self.site.NautTwilBegin():
			self.logger.info('Beginning autofocus')

			#S this is here just to make sure we aren't moving
#			# DON'T CHANGE PORTS (?)
			telescope.inPosition(m3port=telescope.port['IMAGER'], tracking=True, derotate=True)

#			newauto.autofocus(self,telescope.id)

		# read the target list
		with open(self.base_directory + '/schedule/' + scheduleFile, 'r') as targetfile:
			next(targetfile) # skip the calibration headers
			next(targetfile) # skip the calibration headers
			for line in targetfile:
				target = utils.parseTarget(line, logger=self.logger)
				if target <> -1:

					# truncate the start and end times so it's observable
					utils.truncate_observable_window(self.site,target,logger=self.logger)
					if target['starttime'] < target['endtime'] and datetime.datetime.utcnow() < self.site.NautTwilBegin():
						if 'spectroscopy' in target.keys():
							if target['spectroscopy']:
								# only one telescope for now...
								rv_control.doSpectra(self,target,[telescope.id])
							else:
								self.doScience(target,telescope.id)
						else:
							self.doScience(target,telescope.id)
					else:
						self.logger.info(target['name']+ ' not observable; skipping')
						
						
		# Take Morning Sky flats
		# Check if we want to wait for these
		#S got rid of this check because domes were closing while other telescopes were observing.
		if True:   #CalibInfo['WaitForMorning']:
			sleeptime = (self.site.NautTwilBegin() - datetime.datetime.utcnow()).total_seconds()
			if sleeptime > 0:
				self.logger.info('Waiting for morning flats (' + str(sleeptime) + ' seconds)')
				time.sleep(sleeptime)
			self.doSkyFlat(flatFilters, True, CalibInfo['nflat'],telescope.id, piggyback=piggyback)

		# Want to close the aqawan before darks and biases
		# closeAqawan in endNight just a double check
		#S I think we need a way to check if both telescopes are done observing, even if one has
		#S ['waitformorning']==false
		self.telescope_park(telescope.id)

		# all done; close the domes
		if os.path.exists(self.base_directory + '/minerva_library/aqawan1.request.txt'): 
			os.remove(self.base_directory + '/minerva_library/aqawan1.request.txt')
		if os.path.exists(self.base_directory + '/minerva_library/aqawan2.request.txt'): 
			os.remove(self.base_directory + '/minerva_library/aqawan2.request.txt')

		if CalibEndInfo['nbiasEnd'] <> 0 or CalibEndInfo['ndarkEnd']:
			self.imager_connect(telescope.id) # make sure the cooler is on


		# Take biases and darks
		if CalibInfo['WaitForMorning']:
			sleeptime = (self.site.sunrise() - datetime.datetime.utcnow()).total_seconds()
			if sleeptime > 0:
				self.logger.info('Waiting for sunrise (' + str(sleeptime) + ' seconds)')
				time.sleep(sleeptime)
			t0 = datetime.datetime.utcnow()
			timeout = 600.0
			
			dome = utils.getDome(self,telescope.id)

			# wait for the dome to close (the heartbeat thread will update its status)
			while dome.isOpen() and (datetime.datetime.utcnow()-t0).total_seconds() < timeout:
				self.logger.info('Waiting for dome to close')
				time.sleep(60)

			self.doBias(CalibEndInfo['nbiasEnd'],telescope.id)
			self.doDark(CalibEndInfo['ndarkEnd'], CalibInfo['darkexptime'],telescope.id)
		
		self.endNight(telescope, kiwispec=False)

		
	def observingScript_catch(self,telescope,piggyback=False):

		try:
			self.observingScript(telescope,piggyback=piggyback)
		except Exception as e:
			self.logger.exception(str(e.message) )
			body = "Dear benevolent humans,\n\n" + \
			    'I have encountered an unhandled exception which has killed this thread. The error message is:\n\n' + \
			    str(e.message) + "\n\n" + \
			    "Check control.log for additional information. Please investigate, consider adding additional error handling, and restart this telescope thread only.\n\n" + \
			    "Love,\n" + \
			    "MINERVA"
			mail.send(telescope.id + " thread died",body,level='serious',directory=self.directory)
			sys.exit()
	
	def specCalib(self,nbias=11,ndark=11,nflat=11,darkexptime=300.0,flatexptime=1.0,checkiftime=True):
		#S seconds for reading out si imager
		ro_time = 22.0
		#S seconds needed for biases
		b_time = nbias*ro_time
		#S seconds needed for darks
		d_time = ndark*(darkexptime+ro_time)
		#S seconds for slitflats, plus (liberal) 120 seconds for stage moving
		sf_time = nflat*(flatexptime+ro_time)+120.0
		total_caltime = b_time+d_time+sf_time
		# If there is no user override is in place (i.e. checkiftime==True) and total calibration time will go past sunset, then skip all spec calibrations
		if datetime.timedelta(seconds=total_caltime)+datetime.datetime.utcnow() > self.site.NautTwilEnd() and checkiftime:
			self.logger.warning('Not enough time to complete calibrations '+str(total_caltime)+ ' seconds of calibrations; skipping')
			return 
		self.logger.info('Starting approx '+str(total_caltime)+ ' seconds of calibrations')
		self.takeSpecBias(nbias)
		self.takeSpecDark(ndark, darkexptime)
		if self.red:
			self.takeFiberFlat(nflat,1.5)
			self.takeFiberArc(nflat,90.0)
		else:
			self.takeSlitFlat(nflat, flatexptime)

	def takeFiberFlat(self,nflat,flatexptime, warmup=5.0):
		self.pdus[0].flatlamp.on()
		self.spectrograph.fiber_to_calibrate()
		time.sleep(warmup) # wait for lamp to warm up
		target = {}
		target['name'] = 'fiberFlat'
		target['exptime'] = [flatexptime]
		target['spectroscopy'] = True
		for i in range(nflat):
			self.takeSpectrum(target, tele_list = [])
		self.pdus[0].flatlamp.off()
		self.spectrograph.fiber_to_science()

	def takeFiberArc(self, narc, arcexptime, warmup=180.0):
		self.pdus[0].arclamp.on()
		self.spectrograph.fiber_to_calibrate()
		time.sleep(warmup) # wait for lamp to warm up
		target = {}
		target['name'] = 'fiberArc'
		target['exptime'] = [arcexptime]
		target['spectroscopy'] = True
		for i in range(narc):
			self.takeSpectrum(target, tele_list = [])
		self.pdus[0].arclamp.off()
		self.spectrograph.fiber_to_science()

	def specCalib_catch(self, nbias=11,ndark=11,nflat=11,darkexptime=300,flatexptime=1,checkiftime=True):
		try:
			self.specCalib(nbias=nbias,ndark=ndark,nflat=nflat,darkexptime=darkexptime,flatexptime=flatexptime,checkiftime=checkiftime)
		except Exception as e:
			self.logger.exception('specCalib thread died: ' + str(e.message) )
                        body = "Dear benevolent humans,\n\n" + \
                            'I have encountered an unhandled exception which has killed the specCalib control thread. The error message is:\n\n' + \
                            str(e.message) + "\n\n" + \
			    "Check control.log for additional information. Please investigate, consider adding additional error handling, and restart 'main.py\n\n'" + \
                            "Love,\n" + \
                            "MINERVA"
                        mail.send("specCalib thread died",body,level='serious',directory=self.directory)
                        sys.exit()

	def observingScript_all(self,piggyback=False):
		if self.red:
			with open(self.base_directory + '/minerva_library/astrohaven1.request.txt','w') as fh:
				fh.write(str(datetime.datetime.utcnow()))
		elif self.south:
			pass
		else:
			with open(self.base_directory + '/minerva_library/aqawan1.request.txt','w') as fh:
				fh.write(str(datetime.datetime.utcnow()))

			with open(self.base_directory + '/minerva_library/aqawan2.request.txt','w') as fh:
				fh.write(str(datetime.datetime.utcnow()))

		# python bug work around -- strptime not thread safe. Must call this once before starting threads
		junk = datetime.datetime.strptime('2000-01-01 00:00:00','%Y-%m-%d %H:%M:%S')

		threads = []
		self.logger.info('Starting '+str(len(self.telescopes))+ ' telecopes.')
		for telescope in self.telescopes:
			thread = PropagatingThread(target = self.observingScript_catch,args = (telescope,))
			thread.name = telescope.id + ' (control->observingScript_all->observingScript_catch)'
			thread.start()
			threads.append(thread)

#		speccalib_thread = PropagatingThread(target=self.specCalib_catch)
#		speccalib_thread.start()

		for t in range(len(self.telescopes)):
			threads[t].join()
#		speccalib_thread.join()
			
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

	def homeAll(self):
		threads = []
		for telescope in self.telescopes:
			# home the telescope
			thread = PropagatingThread(target = telescope.homeAllMechanisms)
			thread.name = telescope.id + '(control->homeAll)'
			thread.start()
			threads.append(thread)
			
		# wait for homing to complete
		for thread in threads:
                        thread.join()

        #S For now let's anticipate that 'target' is a dictionary containging everything we
        #S need to know about the target in question
        #S 'name','ra','dec','propermotion','parallax',weight stuff,
        def take_rv_spec(self,target):
                pass

if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
        if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	minerva = control('control.ini',base_directory)

	ipdb.set_trace()
	
	
	
