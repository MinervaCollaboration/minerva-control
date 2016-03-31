import urllib
import urllib2
import datetime
import time
import logging
import json
import os
import sys
import ipdb
import mail
import math
import numpy
import pdu
import threading
import numpy as np
import socket
import shutil
import subprocess
import ephem
import utils

from configobj import ConfigObj
#import pwihelpers as pwi
from xml.etree import ElementTree
sys.dont_write_bytecode = True

#HELPER CLASSES
class Status: 
	"""
	Contains a node (and possible sub-nodes) in the parsed XML status tree.
	Properties are added to the class by the elementTreeToObject function.
	"""

	def __str__(self):
		result = ""
		for k,v in self.__dict__.items():
			result += "%s: %s\n" % (k, str(v))

		return result

def elementTreeToObject(elementTreeNode):
	"""
	Recursively convert an ElementTree node to a hierarchy of objects that allow for
	easy navigation of the XML document. For example, after parsing:
	  <tag1><tag2>data</tag2><tag1> 
	You could say:
	  xml.tag1.tag2   # evaluates to "data"
	"""

	if len(elementTreeNode) == 0:
		return elementTreeNode.text

	result = Status()
	for childNode in elementTreeNode:
		setattr(result, childNode.tag, elementTreeToObject(childNode))

	result.value = elementTreeNode.text

	return result



class CDK700:
	def __init__(self, config, base=''):
		#S Set config file
		self.config_file = config
		#S Set base directory
		self.base_directory = base
		#S Get values from config_file
		self.load_config()

		self.num = self.logger_name[-1]

		#S Set up logger
		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)

		self.pdu = pdu.pdu(self.pdu_config,base)
		self.status_lock = threading.RLock()
		# threading.Thread(target=self.write_status_thread).start()
		
		self.focus = {'0':'UNKNOWN'}
		# initialize to the most recent best focus
		for port in ['1','2']:
			if os.path.isfile('focus.' + self.logger_name + '.port'+port+'.txt'):
				f = open('focus.' + self.logger_name + '.port'+port+'.txt','r')
				self.focus[port] = float(f.readline())
				f.close()
			else:
				# if no recent best focus exists, initialize to 25000. (old: current value)
				status = self.getStatus()
				self.focus[port] = self.default_focus[port]  #status.focuser.position
				
			
	#additional higher level routines
	#tracking and detrotating should be on by default
	#much worse to be off when it should be on than vice versa
	def isInitialized(self,tracking=True, derotate=True):
		# check to see if it's properly initialized
		telescopeStatus = self.getStatus()
		if telescopeStatus.mount.encoders_have_been_set <> 'True':
			self.logger.warning('T' + self.num + ': encoders not set (' + telescopeStatus.mount.encoders_have_been_set + '), telescope not initialized')
			return False
		if telescopeStatus.mount.alt_enabled <> 'True':
			self.logger.warning('T' + self.num + ': altitude motor not enabled (' + telescopeStatus.mount.alt_enabled + '), telescope not initialized')
			return False
		if telescopeStatus.mount.alt_motor_error_message <> 'No error': 
			self.logger.warning('T' + self.num + ': altitude motor error present (' + telescopeStatus.mount.alt_motor_error_message + '), telescope not initialized')
			return False
		if telescopeStatus.mount.azm_enabled <> 'True':
			self.logger.warning('T' + self.num + ': azimuth motor not enabled (' + telescopeStatus.mount.azm_enabled + '), telescope not initialized')
			return False
		if telescopeStatus.mount.azm_motor_error_message <> 'No error': 
			self.logger.warning('T' + self.num + ': azimuth motor error present (' + telescopeStatus.mount.azm_motor_error_message + '), telescope not initialized')
			return False
		if telescopeStatus.mount.connected <> 'True': 
			self.logger.warning('T' + self.num + ': mount not connected (' + telescopeStatus.mount.connected + '), telescope not initialized')
			return False
		if telescopeStatus.rotator.connected <> 'True': 
			self.logger.warning('T' + self.num + ': rotator not connected (' + telescopeStatus.rotator.connected + '), telescope not initialized')
			return False
		if telescopeStatus.focuser.connected <> 'True': 
			self.logger.warning('T' + self.num + ': focuser not connected (' + telescopeStatus.focuser.connected + '), telescope not initialized')
			return False

		if tracking:
			if telescopeStatus.mount.tracking <> 'True': 
				self.logger.info('T' + self.num + ': mount not tracking (' + telescopeStatus.mount.tracking + '), telescope not initialized')
				return False
		if derotate:
			if telescopeStatus.rotator.altaz_derotate <> 'True': 
				self.logger.info('T' + self.num + ': rotator not tracking (' + telescopeStatus.rotator.altaz_derotate + '), telescope not initialized')
				return False
		
		return True

	# by default, set tracking and derotating
	# it's much worse to have it off when it should be on than vice versa
	def initialize(self,tracking=True, derotate=True):

		# turning on mount tracking
		self.logger.info('T' + self.num + ': Connecting to mount')
		if not self.mountConnect(): return False #S Start yer engines

		self.logger.info('T' + self.num + ': Enabling motors')
		if not self.mountEnableMotors(): return False

		self.logger.info('T' + self.num + ': Connecting to focuser')
		if not self.focuserConnect(): return False
		
		self.logger.info('T' + self.num + ': Homing telescope')
		if not self.home(): return False

		self.logger.info('T' + self.num + ': re-loading pointing model for the current port')
		telescopeStatus = self.getStatus()
		self.m3port_switch(telescopeStatus.m3.port,force=True)

		# turning on/off mount tracking, rotator tracking
		if tracking:
			self.logger.info('T' + self.num + ': Turning mount tracking on')
			self.mountTrackingOn()
		else:
			self.logger.info('T' + self.num + ': Turning mount tracking off')
			self.mountTrackingOff()
		
		if derotate:
			self.logger.info('T' + self.num + ': Turning rotator tracking on')
			self.rotatorStartDerotating()
		else:
			self.logger.info('T' + self.num + ': Turning rotator tracking off')
			self.rotatorStopDerotating()

		return self.isInitialized(tracking=tracking,derotate=derotate)
		
	def load_config(self):
		
		try:
			config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.HOST = config['Setup']['HOST']
			self.NETWORKPORT = config['Setup']['NETWORKPORT']
			self.imager = config['Setup']['IMAGER']
			self.guider = config['Setup']['GUIDER']
			self.fau = config['Setup']['FAU']
			self.logger_name = config['Setup']['LOGNAME']
			self.pdu_config = config['Setup']['PDU']
			self.latitude = float(config['Setup']['LATITUDE'])
			self.longitude = float(config['Setup']['LONGITUDE'])
			self.elevation = float(config['Setup']['ELEVATION'])
			self.horizon = float(config['Setup']['HORIZON'])
			self.nfailed = 0
			self.port = config['PORT']
			self.modeldir = config['Setup']['MODELDIR']
			self.model = config['MODEL']
			self.rotatoroffset = config['ROTATOROFFSET']
			self.default_focus = config['DEFAULT_FOCUS']
			self.focus_offset = config['FOCUS_OFFSET']
		except:
			print("ERROR accessing configuration file: " + self.config_file)
			sys.exit() 

		for key in self.focus_offset:
			try: self.focus_offset[key] = float(self.focus_offset[key])
			except: pass


                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')

	# SUPPORT FUNCITONS
	def makeUrl(self, **kwargs):
		"""
		Utility function that takes a set of keyword=value arguments
		and converts them into a properly formatted URL to send to PWI.
		For example, calling the function as:
		  makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
		will return the string:
		  http://127.0.0.1:8080/?device=mount&cmd=move&dec=20+30+40&ra=10+20+30

		Note that spaces have been URL-encoded to "+" characters.
		"""

		url = "http://" + self.HOST + ":" + str(self.NETWORKPORT) + "/?"
		url = url + urllib.urlencode(kwargs.items())
		return url

	def pwiRequest(self, **kwargs):
		"""
		Issue a request to PWI using the keyword=value parameters
		supplied to the function, and return the response received from
		PWI.

		For example:
		  makeUrl(device="mount", cmd="move", ra2000="10 20 30", dec2000="20 30 40")
		will request a slew to J2000 coordinates 10:20:30, 20:30:40, and will
		(under normal circumstances) return the status of the telescope as an
		XML string.
		"""
		url = self.makeUrl(**kwargs)
		try: ret = urllib.urlopen(url).read()
		except:
			self.restartPWI()
			ret = urllib.urlopen(url).read()
		return ret

	def parseXml(self, xml):
		"""
		Convert the XML into a smart structure that can be navigated via
		the tree of tag names; e.g. "status.mount.ra"
		"""

		return elementTreeToObject(ElementTree.fromstring(xml))


	def pwiRequestAndParse(self, **kwargs):
		"""
		Works like pwiRequest(), except returns a parsed XML object rather
		than XML text
		"""
		try: return self.parseXml(self.pwiRequest(**kwargs))
		except:
			self.restartPWI()
			return self.parseXml(self.pwiRequest(**kwargs))

	### Status wrappers #####################################
	def getStatusXml(self):
		"""
		Return a string containing the XML text representing the status of the telescope
		"""
		return self.pwiRequest(cmd="getsystem")

	def status(self):

		import xmltodict
		status = xmltodict.parse(self.getStatusXml())

		with open(self.currentStatusFile,'w') as outfile:
			json.dump(status,outfile)

		ipdb.set_trace()

		return status    

	def getStatus(self):
		"""
		Return a status object representing the tree structure of the XML text.
		Example: getStatus().mount.tracking --> "False"
		"""
		return self.parseXml(self.getStatusXml())

	def write_status(self):
		pass
		
	#status thread, exit when main thread stops
	def write_status_thread(self):
		
		for i in threading.enumerate():
				if i.name == "MainThread":
					main_thread = i
					break
		n = 15
		while True:
			if main_thread.is_alive() == False:
				break
			n+= 1
			if n > 14:
				self.write_status()
				n = 0
			time.sleep(1)
			
	### FOCUSER ###
	def focuserConnect(self, port=1):
		"""
		Connect to the focuser on the specified Nasmyth port (1 or 2).
		"""

		return self.pwiRequestAndParse(device="focuser"+str(port), cmd="connect")

	def focuserDisconnect(self, port=1):
		"""
		Disconnect from the focuser on the specified Nasmyth port (1 or 2).
		"""

		return self.pwiRequestAndParse(device="focuser"+str(port), cmd="disconnect")

	def focuserMove(self, position, port=1):
		"""
		Move the focuser to the specified position in microns
		"""

		return self.pwiRequestAndParse(device="focuser"+str(port), cmd="move", position=position)

	def focuserMoveAndWait(self,position,port=1,timeout=90.0):
		self.focuserMove(position,port=port)

		# wait for the focuser to start moving
		time.sleep(2.0) 
		status = self.getStatus()

		t0 = datetime.datetime.utcnow()
		elapsedTime = 0.0
		
		# wait for the focuser to finish moving
		# or the timeout (90 seconds is about how long it takes to go from one extreme to the other)
		while status.focuser.moving == 'True' and elapsedTime < timeout:
			self.logger.info('Focuser moving (' + str(status.focuser.position) + ')')
			time.sleep(0.3)
			status = self.getStatus()
			elapsedTime = (datetime.datetime.utcnow()-t0).total_seconds()

		if abs(float(status.focuser.position) - float(position)) > 10:
			return False

		return True


	def focuserIncrement(self, offset, port=1):
		"""
		Offset the focuser by the specified amount, in microns
		"""

		return self.pwiRequestAndParse(device="focuser"+str(port), cmd="move", increment=offset)

	def focuserStop(self, port=1):
		"""
		Halt any motion on the focuser
		"""

		return self.pwiRequestAndParse(device="focuser"+str(port), cmd="stop")

	def startAutoFocus(self):
		"""
		Begin an AutoFocus sequence for the currently active focuser
		"""
		return self.pwiRequestAndParse(device="focuser", cmd="startautofocus")

	### ROTATOR ###
	def rotatorMove(self, position, port=1):
		return self.pwiRequestAndParse(device="rotator"+str(port), cmd="move", position=position)

	def rotatorIncrement(self, offset, port=1):
		return self.pwiRequestAndParse(device="rotator"+str(port), cmd="move", increment=offset)

	def rotatorStop(self, port=1):
		return self.pwiRequestAndParse(device="rotator"+str(port), cmd="stop")

	def rotatorStartDerotating(self, port=1):
		return self.pwiRequestAndParse(device="rotator"+str(port), cmd="derotatestart")

	def rotatorStopDerotating(self, port=1):
		return self.pwiRequestAndParse(device="rotator"+str(port), cmd="derotatestop")
	
	#S i think we should make targets classes for functions like this, not in telescope.
	#S i did that in scheduler sim, but could be a bit of an overhaul here....
	def hourangle(self,target=None, useCurrent=False):
		#S calculate the current hour angle of the target
		#TODO need to incorporate the updated RA, will be off by a few degrees
		#TODO similar to caluclating the angle from target set check in observing script
		lst = self.lst()
		if useCurrent:
			status = self.getStatus()
			ra = utils.ten(status.mount.ra)
		else:
			ra = target['ra']
		return lst - ra

	# calculate the Local Sidereal Time                                                   
	# this is a bit of a hack...
        def lst(self):
                status = self.getStatus()
                return utils.ten(status.status.lst)
	
        # calculate the parallactic angle (for guiding)
        def parangle(self, target=None, useCurrent=False):

		ha = self.hourangle(target=target, useCurrent=useCurrent)
		if useCurrent:
			status = self.getStatus()
			dec = utils.ten(status.mount.dec)
		else:
			dec = target['dec']
                #stolen from parangle.pro written by Tim Robinshaw
                return -180.0/math.pi*math.atan2(-math.sin(ha*math.pi/12.0),
                                                  math.cos(dec*math.pi/180.0)*math.tan(self.latitude*math.pi/180.0)-
                                                  math.sin(dec*math.pi/180.0)*math.cos(ha*math.pi/12.0))

	def solveRotatorPosition(self, target):
		if 'pa' in target.keys():
			desiredPA = float(target['pa'])
		else:
			desiredPA = 0.0

		parangle = self.parangle(target=target)

		if 'spectroscopy' in target.keys():
			if target['spectroscopy'] == True :
				offset = float(self.rotatoroffset[self.port['FAU']])
			else:
				offset = float(self.rotatoroffset[self.port['IMAGER']])
		else:
			offset = float(self.rotatoroffset[self.port['IMAGER']])



		rotator_pos = parangle + offset - float(desiredPA)
		
		# make sure the angle is positive
		while rotator_pos < 0.0: rotator_pos += 360.0

		rotator_pos = math.fmod(rotator_pos,360.0)
		self.logger.info('Calculated a mech position of ' + str(rotator_pos) + ' for PA of ' + str(desiredPA))
		return rotator_pos

		#
	### MOUNT ###
	def mountConnect(self):
		status = self.pwiRequestAndParse(device="mount", cmd="connect")
		if status.mount.connected == 'False':
			self.logger.error('T' + self.num + ': Failed to connect to mount')
			return False
		return True

	def mountDisconnect(self):
		return self.pwiRequestAndParse(device="mount", cmd="disconnect")

	def mountEnableMotors(self):
		return self.pwiRequestAndParse(device="mount", cmd="enable")

	def mountHome(self):
		return self.pwiRequestAndParse(device="mount", cmd="findhome")

	def mountDisableMotors(self):
		return self.pwiRequestAndParse(device="mount", cmd="disable")

	def mountOffsetRaDec(self, deltaRaArcseconds, deltaDecArcseconds):
		return self.pwiRequestAndParse(device="mount", cmd="move", incrementra=deltaRaArcseconds, incrementdec=deltaDecArcseconds)

	def increment_alt_az_balanced(self,alt=0,azm=0):
		status = self.getStatus()
		curr_alt = float(status.mount.alt_radian)
		alttosend = str(alt)
		azmtosend = str(azm/np.cos(curr_alt))
		return self.mountOffsetAltAz(alttosend,azmtosend)

	def mountOffsetAltAz(self, deltaAltArcseconds, deltaAzArcseconds):
		return self.pwiRequestAndParse(device="mount", cmd="move", incrementazm=deltaAzArcseconds, incrementalt=deltaAltArcseconds)

	def mountGotoRaDecApparent(self, raAppHours, decAppDegs):
		"""
		Begin slewing the telescope to a particular RA and Dec in Apparent (current
		epoch and equinox, topocentric) coordinates.

		raAppHours may be a number in decimal hours, or a string in "HH MM SS" format
		decAppDegs may be a number in decimal degrees, or a string in "DD MM SS" format
		"""

		return self.pwiRequestAndParse(device="mount", cmd="move", ra=raAppHours, dec=decAppDegs)

	def mountGotoRaDecJ2000(self, ra2000Hours, dec2000Degs):
		"""
		Begin slewing the telescope to a particular J2000 RA and Dec.
		ra2000Hours may be a number in decimal hours, or a string in "HH MM SS" format
		dec2000Degs may be a number in decimal degrees, or a string in "DD MM SS" format
		"""
		return self.pwiRequestAndParse(device="mount", cmd="move", ra2000=ra2000Hours, dec2000=dec2000Degs)

	def mountGotoAltAz(self, altDegs, azmDegs):
		return self.pwiRequestAndParse(device="mount", cmd="move", alt=altDegs, azm=azmDegs)

	def mountStop(self):
		return self.pwiRequestAndParse(device="mount", cmd="stop")

	def mountTrackingOn(self):
		return self.pwiRequestAndParse(device="mount", cmd="trackingon")

	def mountTrackingOff(self):
		return self.pwiRequestAndParse(device="mount", cmd="trackingoff")

	def mountSetTracking(self, trackingOn):
		if trackingOn:
			self.mountTrackingOn()
		else:
			self.mountTrackingOff()

	def mountSetTrackingRateOffsets(self, raArcsecPerSec, decArcsecPerSec):
		"""
		Set the tracking rates of the mount, represented as offsets from normal
		sidereal tracking in arcseconds per second in RA and Dec.
		"""
		return self.pwiRequestAndParse(device="mount", cmd="trackingrates", rarate=raArcsecPerSec, decrate=decArcsecPerSec)

	# this is untested!!!
#	def hourangle(self,obs,ra,dec):
#		c = coord.ICRSCoordinates(ra=ra, dec=dec, unit=(u.hour,u.deg))
#		t = coord.Angle(obs.sidereal_time(),u.radian)
#		t.lat = obs.lat
#		t.lon = obs.lon
#		ha = coor.angles.RA.hour_angle(c.ra,t)
#		return None

	def mountSetPointingModel(self, filename):
		return self.pwiRequestAndParse(device="mount", cmd="setmodel", filename=filename)

	def mountAddToModel(self,ra,dec):
		return self.pwiRequestAndParse(device="mount",cmd="addtomodel",ra2000=ra,dec2000=dec)

	def mountSync(self,ra,dec):
		return self.pwiRequestAndParse(device="mount",cmd="sync",ra2000=ra,dec2000=dec)

	### M3 ###
	def m3SelectPort(self, port):
		return self.pwiRequestAndParse(device="m3", cmd="select", port=port)

	def m3Stop(self):
		return self.pwiRequestAndParse(device="m3", cmd="stop")

	def recover(self,tracking = True, derotate=True):
		#S need to make sure all these functions don't call recover
		#S shutdown looks clear, all basePWI functions

		if self.nfailed <= 1:
			self.logger.warning('T' + self.num + ': failed; trying to reconnect')
			try: self.shutdown()
			except: pass
		
			if self.initialize(tracking=tracking, derotate=derotate):
				self.logger.info('T' + self.num + ': recovered after reconnecting')
				return True

		self.logger.warning('T' + self.num + ': reconnecting failed; restarting PWI')
		try: self.shutdown()
		except: pass
		self.restartPWI()
		
		if self.initialize(tracking=tracking, derotate=derotate):
			self.logger.info('T' + self.num + ': recovered after restarting PWI')
			return True

		# power cycle and rehome the scope
		self.logger.info('T' + self.num + ': restarting PWI failed, power cycling the mount')
		try: self.shutdown()
		except: pass
		self.killPWI()
		self.powercycle()
		self.startPWI()

		if self.initialize():
			self.logger.info('T' + self.num + ': recovered after power cycling the mount')
			return True

		filename = "telescope_" + self.num + '.error'
		body = "Dear benevolent humans,\n\n" + \
		    "I have failed to recover automatially. Please recover me, then delete " + filename + " to restart operations.\n\n" + \
		    "Love,\n" + \
		    "MINERVA"			
		while not self.initialize(tracking=tracking, derotate=derotate):
			self.logger.error('T' + self.num + ': Telescope has failed to automatically recover; intervention required')
			mail.send('T' + self.num + " has failed",body,level='serious')
			fh = open(filename,'w')
			fh.close()
			while os.path.isfile(filename):
				time.sleep(1)
		return True

	
	
	def makePointingModel(self, minerva, npoints=100, maxmag=4.0, fau=True, brightstar=True, random=False, grid=False, nalt=4, naz=10, exptime=5.0, filterName='V'):
		
		camera = utils.getCamera(minerva,self.num)

		if fau:
			xcenter = camera.fau.xcenter
			ycenter = camera.fau.ycenter
			xsize = camera.fau.x2
			ysize = camera.fau.y2			
			m3port = self.port['FAU']
			platescale = camera.fau.platescale
			derotate = False
		else:
			xcenter = camera.xcenter
			ycenter = camera.ycenter
			xsize = camera.x2
			ysize = camera.y2
			m3port = self.port['IMAGER']
			platescale = camera.platescale
			derotate = True

		if brightstar:
			brightstars = utils.brightStars(maxmag=maxmag)
			
		pointsAdded = 0
		
		while pointsAdded < npoints:
			for i in range(len(brightstars['dec'])):

				# apply proper motion to coordinates
				raj2000 = float(brightstars['ra'][i])
				decj2000 = float(brightstars['dec'][i])
				pmra = float(brightstars['pmra'][i])
				pmdec = float(brightstars['pmdec'][i])
#				ra,dec = self.starmotion(raj2000,decj2000,pmra,pmdec)

				# ignore proper motion
				ra = raj2000
				dec = decj2000

				self.logger.info("J2000 " + str(raj2000) + ',' + str(decj2000) + " adding proper motion " + str(pmra) + "," + str(pmdec) + " is " + str(ra) + "," + str(dec))
				# if the star is not above the horizon, skip to the next one
				alt,az = self.radectoaltaz(ra,dec)
				if (alt-1) < self.horizon: continue

				target = {
					'ra':ra,
					'dec':dec,
					'spectroscopy':fau,
					'fauexptime': exptime,
					'name':'Pointing',
					}


				# slew to bright star
				self.acquireTarget(target, derotate=derotate, m3port=m3port)

				camera.fau.guiding=True
				camera.fau.acquisition_tolerance=1.5
				if minerva.fauguide(target,int(self.num),acquireonly=True,xfiber=xcenter,yfiber=ycenter,skiponfail=True):
					# add point to model
					self.logger.info("Adding point to model: ra = " + str(ra) + ", dec = " + str(dec))
					self.mountAddToModel(ra,dec)

					# update the model file (so the new point doesn't get overwritten on port switch)
					# TODO: need function to save model as default
#					shutil.copyfile(self.modeldir + 'Default_Mount_Model.PXP',self.modeldir + self.model[m3port])
	
					pointsAdded += 1
					if pointsAdded >= npoints: return
#				continue


				imageName = minerva.takeFauImage(target,telescope_num=int(self.num))
				datapath = '/Data/t' + self.num + '/' + self.night + '/'
				x,y = utils.findBrightest(datapath + imageName)
				if x==None or y==None: continue

				# update the reference pixel to the brightest (target) star
				f = pyfits.open(dataPath + imageName, mode='update')
				f[0].header]['CRVAL1'] = ra
				f[0].header]['CRVAL2'] = dec
				f[0].header]['CRPIX1'] = x
				f[0].header]['CRPIX2'] = y
				f.flush()
				f.close()

				# call xy2sky to determine the J2000 coordinates of the center pixel
				p = subprocess.Popen(["xy2sky",datapath+imageName,str(xcenter),str(ycenter)],
						     stderr=subprocess.PIPE,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
				output,err = p.communicate()
				racen = utils.ten(output.split()[0])
				deccen = utils.ten(output.split()[1])


				edge = 10

			
				# take image
				imageName = camera.take_image(exptime=exptime, objname='Pointing', fau=fau, filterInd=filterName)

				# find the brightest star
				datapath = '/Data/t' + self.num + '/' + self.night + '/'
				x,y = utils.findBrightest(datapath + imageName)
				if x==None or y==None: continue

				# determine J2000 coordinates of the center pixel
				
				# we need to know and apply the current sky angle
				telescopeStatus = self.getStatus()
				rotpos = float(telescopeStatus.rotator.position)
				parang = self.parangle(useCurrent=True)
				rotoff = float(self.rotatoroffset[m3port])
				skypa = (float(parang) + float(rotoff) - float(rotpos))*math.pi/180.0
				
				# apply the rotation matrix
				raoffset  = ((x-xcenter)*math.cos(-skypa) - (y-ycenter)*math.sin(-skypa))*platescale/math.cos(dec*math.pi/180.0)
				decoffset = ((x-xcenter)*math.sin(-skypa) + (y-ycenter)*math.cos(-skypa))*platescale

				# if it's too close to the edge, recenter and try again
				if x < edge or y < edge or xsize-x < edge or ysize-y < edge:
					self.mountOffsetRaDec(raoffset,decoffset)
						
					if self.inPosition(m3port=m3port, tracking=True, derotate=derotate):
						self.logger.info('T' + self.num + ': Finished jog')

					# take image
					imageName = camera.take_image(exptime=exptime, objname='Pointing', fau=fau, filterInd=filterName)

					# find the brightest star
					x,y = utils.findBrightest(datapath + imageName)
					if x==None or y==None: continue
					if x < edge or y < edge or xsize-x < edge or ysize-y < edge: continue
						
					# apply the rotation matrix
					raoffset  = ((x-xcenter)*math.cos(-skypa) - (y-ycenter)*math.sin(-skypa))*platescale/math.cos(dec*math.pi/180.0)
					decoffset = ((x-xcenter)*math.sin(-skypa) + (y-ycenter)*math.cos(-skypa))*platescale

				racen  =  ra - raoffset/240.0
				deccen = dec - decoffset/3600.0
								# add point to model
				self.logger.info("Adding point to model: RA_Center = " + str(racen) + ", Dec_center = " + str(deccen) + ", ra = " + str(ra) + ", dec = " + str(dec))
				self.mountAddToModel(racen,deccen)

#				# update the model file (so the new point doesn't get overwritten on port switch)
#				shutil.copyfile(self.modeldir + 'Default_Mount_Model.PXP',self.modeldir + self.model[m3port])
	
				pointsAdded += 1
				if pointsAdded >= npoints: return



	# this is designed to calibrate the rotator using a single bright star
	def calibrateRotator(self, camera, fau=True):

		# slew to bright star
		# brightstars = utils.brightStars()
		# do some other stuff (assume already on a bright star)
		
		# percent of maxmove
		gain = 0.75

		if fau: 
			m3port = self.port['FAU']
			platescale = camera.fau.platescale
			xsize = camera.fau.x2
			ysize = camera.fau.y2
			derotate=False
		else: 
			m3port = self.port['IMAGER']
			platescale = camera.platescale
			xsize = camera.x2
			ysize = camera.y2
			derotate=True

		filename = camera.take_image(exptime=1,objname="rotatorCal",fau=fau)

		# locate star
		datapath = '/Data/t' + self.num + '/' + self.night + '/'
		x1, y1 = utils.findBrightest(datapath + filename)
		if x1 == None or y1 == None: return False

		# the longer I can slew, the more accurate the calculation
		# calculate how far I can move before hitting the edge
		# must assume random orientation
		maxmove = min([x1,xsize-x1,y1,ysize-y1])*platescale

		# jog telescope by 80% of the maximum move in +RA
		status = self.getStatus()
		dec = utils.ten(status.mount.dec)*math.pi/180.0
		self.mountOffsetRaDec(-maxmove*gain/math.cos(dec),0.0)
		
		if self.inPosition(m3port=m3port, tracking=True, derotate=derotate):
			self.logger.info('T' + self.num + ': Finished jog')

		# take exposure
		filename = camera.take_image(exptime=1,objname="rotatorCal",fau=fau)

		# locate star
		datapath = '/Data/t' + self.num + '/' + self.night + '/'
		x2, y2 = utils.findBrightest(datapath + filename)
		if x2 == None or y2 == None: return False

		telescopeStatus = self.getStatus()
		rotpos = float(telescopeStatus.rotator.position)
		parang = self.parangle(useCurrent=True)

		# calculate rotator angle
		skypa = math.atan2(y2-y1,x2-x1)*180.0/math.pi
		rotoff = skypa - float(parang) + float(rotpos)
		
		self.logger.info("Found stars at (" + str(x1) + "," + str(y1) + " and (" + str(x2) + "," + str(y2) + ")")
		self.logger.info("Enter the sky position angle (" + str(skypa) + ") into the calibrate field")
		self.logger.info("The field rotation offset is " + str(rotoff))

		# update self.rotatoroffset 
		self.rotatoroffset[m3port] = rotoff

		# TODO: update telescope_?.ini

		# jog back to original position
		self.mountOffsetRaDec(maxmove*gain/math.cos(dec),0.0)


		return rotoff

	def inPosition(self,m3port=None, alt=None, az=None, ra=None, dec=None, pointingTolerance=60.0, tracking=True, derotate=True):

		# Wait for telescope to complete motion
		start = datetime.datetime.utcnow()
		timeout = 30.0
		elapsedTime = 0
		time.sleep(0.5) # needs time to start moving
		telescopeStatus = self.getStatus()

		#S want to make sure we are at the right port before mount, focuser, rotator slew.
		#S If an allowable port is specified
		if (str(m3port)=='1') or (str(m3port)=='2'):
			self.logger.info('T%s: Ensuring m3 port is at port %s.'%(self.num,str(m3port)))
			while telescopeStatus.m3.port != str(m3port) and elapsedTime < timeout:
				time.sleep(0.5)
				#S This returns a status xml, so sending it on repeat shouldnt matter
				telescopeStatus = self.getStatus()
				#S Need to track elapsed time.
				elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
				changedPort = True
			if elapsedTime > timeout: 
				self.logger.error('T%s: Failed to select correct M3 port (%s)'%(self.num,m3port))
				return False
				
		#S If a bad port is specified (e.g. 3) or no port (e.g. None)
		else:
			self.logger.info('T%s: No M3 port specified or bad, using current port(%s)'%(self.num,telescopeStatus.m3.port))


		self.logger.info('T' + self.num + ': Waiting for telescope to finish slew; moving = ' + telescopeStatus.mount.moving + str(telescopeStatus.mount.moving == 'True') + str(elapsedTime < timeout) + str(tracking))
		timeout = 60.0
		while telescopeStatus.mount.moving == 'True' and elapsedTime < timeout and tracking:
			time.sleep(0.1)
			elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
			telescopeStatus = self.getStatus()
			#? Has this condition ever be met? Why is this here?
			# JDE 2015-10-06: yes, windshake can fool the motor servo loop.
			# Tuning of "MAX RMS Encoder Error for Goto" in "mount" tab is
			# likely required if this message is seen
			if telescopeStatus.mount.moving == 'False':
				time.sleep(1)
				telescopeStatus = self.getStatus()
				if telescopeStatus.mount.moving == 'True':
					self.logger.error('T' + self.num + ': Telescope moving after it said it was done')

			if telescopeStatus.mount.alt_motor_error_code <> '0':
				self.logger.error('T' + self.num + ': Error with altitude drive: ' + telescopeStatus.mount.alt_motor_error_message)
				return False

			if telescopeStatus.mount.azm_motor_error_code <> '0':
				self.logger.info('T' + self.num + ': Error with azmimuth drive: ' + telescopeStatus.mount.azm_motor_error_message)
				return False

			if telescopeStatus.mount.alt_motor_error_code <> '0':
				self.logger.error('T' + self.num + ': Error with altitude drive: ' + telescopeStatus.mount.alt_motor_error_message)
				return False

			if telescopeStatus.mount.azm_motor_error_code <> '0':
				self.logger.info('T' + self.num + ': Error with azmimuth drive: ' + telescopeStatus.mount.azm_motor_error_message)
				return False

		# Make sure tracking is on
		if telescopeStatus.mount.tracking == 'False' and tracking:
			self.mountTrackingOn()
			self.logger.error('T%s: Tracking was off, turned tracking on.'%(self.num))
			#self.logger.info('T%s: Moving, but because tracking is OFF. Assuming in position'%(self.num))

		if elapsedTime > timeout or telescopeStatus.mount.on_target == False:
			self.logger.error('T%s: Failed to slew within timeout (%s)'%(self.num,timeout))
			return False

		self.logger.info('T' + self.num + ': Waiting for Focuser to finish slew; goto_complete = ' + telescopeStatus.focuser.goto_complete)
		timeout = 120.0
		while telescopeStatus.focuser.goto_complete == 'False' and elapsedTime < timeout:
			time.sleep(0.5)
			self.logger.debug('T%s: Focuser moving (%sum)'%(self.num,telescopeStatus.focuser.position))
			elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
			telescopeStatus = self.getStatus()
			if telescopeStatus.focuser.goto_complete == 'True':
				time.sleep(1)
				telescopeStatus = self.getStatus()
				if telescopeStatus.focuser.goto_complete == 'False':
					self.logger.error('T%s: Focuser moving after is said it was done'%(self.num))
		if elapsedTime > timeout:
			self.logger.error('T%s: Failed to get to focus position within timeout (%s)'%(self.num,timeout))
			return False

		# if alt/az is specified, make sure we're close to the right position
		if alt <> None and az <> None:
			ActualAz = float(telescopeStatus.mount.azm_radian)
			ActualAlt = float(telescopeStatus.mount.alt_radian)
			DeltaPos = math.acos( math.sin(ActualAlt)*math.sin(alt*math.pi/180.0)+math.cos(ActualAlt)*math.cos(alt*math.pi/180.0)\
						      *math.cos(ActualAz-az*math.pi/180.0) )*(180./math.pi)*3600.0
			if DeltaPos > pointingTolerance:
				self.logger.error('T' + self.num + ": Telescope reports it is " + str(DeltaPos)\
							  + " arcsec away from the requested postion (ActualAlt="\
							  + str(ActualAlt*180.0/math.pi) + " degrees, Requested Alt=" + str(alt) + ", ActualAz="\
							  + str(ActualAz*180.0/math.pi) + " degrees, Requested Az=" + str(az))
				self.nfailed += 1
				return False

		# if ra/dec is specified, make sure we're close to the right position
		if ra <> None and dec <> None:
			ActualRa = utils.ten(telescopeStatus.mount.ra_2000)*math.pi/12.0
			ActualDec = utils.ten(telescopeStatus.mount.dec_2000)*math.pi/180.0
			DeltaPos = math.acos( math.sin(ActualDec)*math.sin(dec*math.pi/180.0)+math.cos(ActualDec)*math.cos(dec*math.pi/180.0)\
						      *math.cos(ActualRa-ra*math.pi/12.0) )*(180.0/math.pi)*3600.0
			if DeltaPos > pointingTolerance:
				self.logger.error('T' + self.num + ": Telescope reports it is " + str(DeltaPos)\
							  + " arcsec away from the target postion (Dec="\
							  + str(ActualDec*180.0/math.pi) + " degrees, Requested Dec=" + str(dec) + ", RA="\
							  + str(ActualRa*12.0/math.pi) + " hours, Requested Ra=" + str(ra))
				self.nfailed += 1
				return False


                #S Make sure the derotating is on.
		if derotate:
			self.rotatorStartDerotating()
			timeout = 360.0
			self.logger.info('T' + self.num + ': Waiting for rotator to finish slew; goto_complete = ' + telescopeStatus.rotator.goto_complete)
			while telescopeStatus.rotator.goto_complete == 'False' and elapsedTime < timeout:
				time.sleep(0.5)
				self.logger.debug('T%s: rotator moving (%s degrees)'%(self.num,telescopeStatus.rotator.position))
				elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
				telescopeStatus = self.getStatus()
				if telescopeStatus.rotator.goto_complete == 'True':
					time.sleep(1)
					telescopeStatus = self.getStatus()
					if telescopeStatus.rotator.goto_complete == 'False':
						self.logger.error('T' + self.num + ': Rotator moving after it said it was done')

			# Make sure derotating is on.
			if telescopeStatus.rotator.altaz_derotate == 'False':
				self.rotatorStartDerotating()
				self.logger.error('T%s: Derotating was off, turned on.'%(self.num))
		else:
			if telescopeStatus.rotator.altaz_derotate == 'True':
				self.rotatorStopDerotating()
				self.logger.error('T%s: Derotating was on, turned off.'%(self.num))


		if elapsedTime > timeout:
			self.logger.error('T%s: Failed to get to rotator position within timeout (%s)'%(self.num,timeout))
			return False

		# if it gets here, we are in position
		self.nfailed = 0
		return True

	def starmotion(self,ra,dec,pmra,pmdec,px=0.0,rv=0.0,date=datetime.datetime.utcnow()):

                ## Constants
                #S Was using julian date of observation, but this was only to have a more general approach to
                #S what coordinate system we were using. I assume we are using on J2000 coordinates, so I made it only take that for now.
                #S It can be switched very easily though
                #epoch = 2451545.0
                j2000 = datetime.datetime(2000,01,01,12)
                days_since_j2000 = (date-j2000).days #[] = daya
                #jd_obs = days_since_j200 + jd_of_j2000
                #S One AU in meters
                AU  = 149597870700. #[] = meters
		days_in_year = 365.25
                #S the seconds in a year
                year_sec = days_in_year*24.*3600. #[] = seconds/year
                #S Parsecs in an AU
                pctoau = 3600.*180/math.pi #[] = AU
                #S km/sec to AU/year
                kmstoauy = year_sec*1000./AU

                #S We are expecting RA to come in as decimal hours, so need to convert to degrees then radians
                #S dec comes in as degrees.
                rarad = np.radians(ra*15.0)
                decrad = np.radians(dec)
                #S basically see what values we can make corrections for.
                        
                #S Unit vector pointing to star's epoch location
                r0hat = np.array([np.cos(rarad)*np.cos(decrad), np.sin(rarad)*np.cos(decrad), np.sin(decrad)])
                #S Vector pointingup at celestial pole
                up = np.array([0.,0.,1.])
                #S Vector pointing east
                east = np.cross(up, r0hat)
                #S Normalize east vector
                east = east/np.linalg.norm(east)
                #S Unit vector pointing north
                north =  np.cross(r0hat,east)
                #S Proper motion correction (Not 100% sure what is going on with this calculation)
		#S this is in AU/year??
                mu = (pmra*east+pmdec*north)/pctoau/1000.

                #S This can be used if we want to make our code more general and to be able to switch between epochs. I'm
                #S assuming were sticking with j2000
                ##epoch0 = 2000. + (epoch-2451545.0)/365.25
                ##yearnow = 2000. + (jd_obs - 2451545.0)/365.25
                #S Days since j2000
                T = days_since_j2000/days_in_year
                #S rv away from earth, with parallax
                vpi = (rv/1000.)*kmstoauy*(px/1000./pctoau)
                #S Total velocity of star on sky (proper motion plus rv away from earth)
                vel = mu + vpi*r0hat
                #S corrected vector from observer to object
                r = vel*T + r0hat
                #S Unit vector from observer to object
                rhat = r/np.linalg.norm(r)

                #S so we know rhat = [cos(dec)cos(ra),cos(dec)sin(ra),sin(dec)] for our corrected ra,dec
                #S all we need to do is arcsin for declination, returns between [-pi/2,pi/2], converted to degrees
                dec_corrected = np.degrees(np.arcsin(rhat[2]))
                #S The tricky one is to get ra on [0,2pi], but this takes care of it. Converted to degrees in either case
                #S arctan2 is rctan but chooses quadrant based on signs of arguements. Giving us ra on [-pi,pi]
                ra_intermed  = np.arctan2(rhat[1],rhat[0])
                #S Check to see if less than zero, add 2pi if so to make sure all angles are of ra on [0,2pi]
                #S We do want to convert to decimal hours though

                if ra_intermed < 0:
                        ra_corrected = np.degrees(ra_intermed + 2*np.pi)/15.
                else:
                        ra_corrected = np.degrees(ra_intermed)/15.

		return ra_corrected,dec_corrected
		

	#TODO Search #TODOACQUIRE in control.py for all(?) calls on this function to be edited
        #S This has not been incorporated anywhere yet, and if it is all calls on the function will
	#S need to be edited to mathc the arguements. It is expecting a target dictionary now.
	def acquireTarget(self,target,pa=None, tracking=True, derotate=True, m3port=None):

		telescopeStatus = self.getStatus()

                try: pmra = target['pmra']
                except: pmra = 0.0
                try: pmdec = target['pmdec']
                except: pmdec = 0.0
                try: px = target['px']
                except: px = 0.0                    
                try: rv = target['rv']
                except: rv = 0.0

		ra_corrected,dec_corrected = self.starmotion(target['ra'],target['dec'],pmra,pmdec,px=px,rv=rv)

		# make sure the coordinates are within the telescope's limits
		alt,az = self.radectoaltaz(ra_corrected,dec_corrected)
		if alt < self.horizon:
			self.logger.error("Coordinates out of bounds; object not acquired! (Alt,Az) = (" + str(alt) + "," + str(az) + "), (RA,Dec) = (" + str(ra_corrected) + ',' + str(dec_corrected) + ")")
			self.logger.info("... but something is going wrong with these calculations; I'm going to try to acquire anyway")
#			return False

		#S make sure the m3 port is in the correct orientation
		if 'spectroscopy' in target.keys():
			if target['spectroscopy']:
				if m3port == None: m3port = self.port['FAU']
				#S Initialize the telescope
				self.initialize(tracking=True,derotate=False)
			else: 
				if m3port == None: m3port = self.port['IMAGER']
				#S Initialize the telescope
				self.initialize(tracking=True,derotate=True)
				rotator_angle = self.solveRotatorPosition(target)
				self.rotatorMove(rotator_angle,port=m3port)

		else:
			if m3port == None: m3port = self.port['IMAGER']
			self.initialize(tracking=True,derotate=True)
			rotator_angle = self.solveRotatorPosition(target)
			self.rotatorMove(rotator_angle,port=m3port)

		self.m3port_switch(m3port)
		self.logger.info('T' + self.num + ': Starting slew to J2000 ' + str(ra_corrected) + ',' + str(dec_corrected))
		self.mountGotoRaDecJ2000(ra_corrected,dec_corrected)

		if self.inPosition(m3port=m3port, ra=ra_corrected, dec=dec_corrected, tracking=tracking, derotate=derotate):
			self.logger.info('T' + self.num + ': Finished slew to J2000 ' + str(ra_corrected) + ',' + str(dec_corrected))
		else:
			self.logger.error('T' + self.num + ': Slew failed to J2000 ' + str(ra_corrected) + ',' + str(dec_corrected))
			self.recover(tracking=tracking, derotate=derotate)
			#XXX Something bad is going to happen here (recursive call, potential infinite loop).
			self.acquireTarget(target,pa=pa, tracking=tracking, derotate=derotate, m3port=m3port)
			return

	def radectoaltaz(self,ra,dec,date=datetime.datetime.utcnow()):
		obs = ephem.Observer()
		obs.lat = str(self.latitude)
		obs.long = str(self.longitude)
		obs.elevation = self.elevation
		obs.date = str(date)
		star = ephem.FixedBody()
		star._ra = ephem.hours(str(ra))
		star._dec = ephem.degrees(str(dec))
		star.compute(obs)
		alt = utils.ten(str(star.alt))
		az = utils.ten(str(star.az))
		self.logger.info("Alt/Az = " + str(alt) + "," + str(az) + " at RA/Dec = " + str(ra) + ',' + str(dec) + ", date = " + str(date) + ', lat=' + str(obs.lat) + ', lon = ' + str(obs.long))
		return alt,az

	def m3port_switch(self,m3port, force=False):

		#S want to make sure we are at the right port before mount, focuser, rotator slew.
		#S If an allowable port is specified	
		telescopeStatus = self.getStatus()
		if (str(m3port)=='1') or (str(m3port)=='2'):
			self.logger.info('T%s: Ensuring m3 port is at port %s.'%(self.num,str(m3port)))
			if telescopeStatus.m3.port != str(m3port) or force:
				if telescopeStatus.m3.port != str(m3port):
					self.logger.info('T%s: Port changed, loading pointing model'%(self.num))
				
					# load the pointing model
					modelfile = self.modeldir + self.model[m3port]
					if os.path.isfile(modelfile):
						self.logger.info('changing model file')
						self.mountSetPointingModel(self.model[m3port])
					else:
						self.logger.error('T%s: model file (%s) does not exist; using current model'%(self.num, modelfile))
						mail.send('T%s: model file (%s) does not exist; using current model'%(self.num, modelfile),'',level='serious')

					telescopeStatus = self.m3SelectPort(port=m3port)
					time.sleep(0.5)
					
					telescopeStatus = self.m3SelectPort(port=m3port)

					# TODO: add a timeout here!
					while telescopeStatus.m3.moving_rotate == 'True':
						time.sleep(0.1)
						telescopeStatus = self.getStatus()
						
				
		#S If a bad port is specified (e.g. 3) or no port (e.g. None)
		else:
			self.logger.error('T%s: Bad M3 port specified (%s); using current port(%s)'%(self.num,m3port,telescopeStatus.m3.port))
					   
	def isReady(self,tracking=False,port=None,ra=None,dec=None,pa=None):
		if not self.isInitialized():
			#TODO
			#S This is not smart, need to work in a recovery process some how
			while not self.initialize(tracking=tracking):
				pass
		self.inPostion()
		status = self.getStatus()
		if port == None:
			self.logger.info('T%s: No M3 port specified, using current port(%s)'%(self.num,status.m3.port))
		if (ra == None) or (dec == None) :
			self.logger.info('T%s: No target coordinates given, maintaining ra=%s,dec=%s'%(self.num,str(ra),str(dec)))
		

	def park(self):
		# park the scope (no danger of pointing at the sun if opened during the day)
		self.initialize(tracking=True, derotate=False)
		parkAlt = 45.0
		parkAz = 0.0 

		self.logger.info('T' + self.num + ': Parking telescope (alt=' + str(parkAlt) + ', az=' + str(parkAz) + ')')
		self.mountGotoAltAz(parkAlt, parkAz)

#		self.initialize(tracking=False, derotate=False)
#		self.logger.info('T' + self.num + ': Turning rotator tracking off')
#		self.rotatorStopDerotating()
		
		if not self.inPosition(alt=parkAlt,az=parkAz, pointingTolerance=3600.0,derotate=False):
			if self.recover(tracking=False, derotate=False): self.park()

		self.logger.info('T' + self.num + ': Turning mount tracking off')
		self.mountTrackingOff()

	def recoverFocuser(self, focus, m3port):
		timeout = 60.0

		self.m3port_switch(m3port)

		self.logger.info('T' + self.num + ': Beginning focuser recovery')

		self.focuserStop()
		self.rotatorStopDerotating()
		self.focuserDisconnect()
		self.restartPWI(email=False)
		time.sleep(5)

		self.initialize()
		self.focuserConnect()

		status = self.getStatus()
		if self.focuserMoveAndWait(self.focus[m3port],m3port):
			self.logger.info('T' + self.num + ': Focuser recovered')			
		else:
			self.logger.error('T' + self.num + ': Focus timed out')
			mail.send('T' + self.num + ': Focuser failed on ' + str(self.logger_name),"Try powercycling?",level='serious')
			return
					
	def shutdown(self):
		self.rotatorStopDerotating()
		self.focuserDisconnect()
		self.mountTrackingOff()
		self.mountDisconnect()
		self.mountDisableMotors()
		
	def powercycle(self):
		self.pdu.panel.off()
		time.sleep(60)
		self.pdu.panel.on()
		time.sleep(30) # wait for the panel to initialize

	def home(self, timeout=420.0):
                #S running into problems where we get recursion between mountconnecting failing and 
		#S homing. 
		# turning on mount tracking
		self.logger.info('T' + self.num + ': Connecting to mount')
		self.mountConnect()

		self.logger.info('T' + self.num + ': Enabling motors')
		self.mountEnableMotors()

                status = self.getStatus()
                if status.mount.encoders_have_been_set == 'True':
                        self.logger.info('T' + self.num + ': Mount already homed')
                        return True
                else:
                        self.mountHome()
                        time.sleep(5.0)
                        status = self.getStatus()
                        t0 = datetime.datetime.utcnow()
                        elapsedTime = 0
                        while status.mount.is_finding_home == 'True' and elapsedTime < timeout:
                                elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
                                self.logger.info('T' + self.num + ': Homing Telescope (elapsed time = ' + str(elapsedTime) + ')')
                                time.sleep(5.0)
                                status = self.getStatus()
		
		time.sleep(5.0)
		status = self.getStatus()

		#S Let's force close PWI here (after a disconnect). What is happening I think is that 
		#S PWI freezes, and it can't home. While it's stuck in this loop of rehoming
		#S with no hope of exiting. All it does is continually hit time out. 
		#TODO Not entirely sure how to restart PWI, but will prioritize it.
		#S actual going to put an iteration limit of 2 on it for now, that way we'll get emails 
		#S and it won't keep spiralling downward.
		#TODO Need to think of a good way to setup iteration check... be right back to it
		if status.mount.encoders_have_been_set == 'False':
			return False
		else:
			return True

	def startPWI(self,email=True):
		self.send_to_computer('schtasks /Run /TN "Start PWI"')
		time.sleep(5.0)

	def restartPWI(self,email=True):
		self.killPWI()
		time.sleep(5.0)
		return self.startPWI(email=email)

        def killPWI(self):
		self.kill_remote_task('PWI.exe')
		self.kill_remote_task('PXPAX532.exe')
		self.kill_remote_task('PXPAX533.exe')
		self.kill_remote_task('PXPAX534.exe')
		self.kill_remote_task('PXPAX535.exe')
		return self.kill_remote_task('ComACRServer.exe')

	def kill_remote_task(self,taskname):
                return self.send_to_computer("taskkill /IM " + taskname + " /f")
 

        def send_to_computer(self, cmd):
                f = open(self.base_directory + '/credentials/authentication.txt','r')
                username = f.readline().strip()
                password = f.readline().strip()
                f.close()

                process = subprocess.Popen(["winexe","-U","HOME/" + username + "%" + password,"//" + self.HOST, cmd],stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                out,err = process.communicate()
                self.logger.info('T' + self.num + ': cmd=' + cmd + ', out=' + out + ', err=' + err)

                if 'NT_STATUS_HOST_UNREACHABLE' in out:
                        self.logger.error('T' + self.num + ': the host is not reachable')
                        mail.send("T" + self.num + ' is unreachable',
                                  "Dear Benevolent Humans,\n\n"+
                                  "I cannot reach T" + self.num + ". Can you please check the power and internet connection?\n\n" +
                                  "Love,\nMINERVA",level="serious")
                        return False
                elif 'NT_STATUS_LOGON_FAILURE' in out:
                        self.logger.error('T' + self.num + ': invalid credentials')
                        mail.send("Invalid credentials for T" + self.num,
                                  "Dear Benevolent Humans,\n\n"+
                                  "The credentials in " + self.base_directory +
                                  '/credentials/authentication.txt (username=' + username +
                                  ', password=' + password + ') appear to be outdated. Please fix it.\n\n' +
                                  'Love,\nMINERVA',level="serious")
                        return False
                elif 'ERROR: The process' in err:
                        self.logger.info('T' + self.num + ': task already dead')
                        return True
                return True


#test program
if __name__ == "__main__":

	if socket.gethostname() == 'Main':
		base_directory = '/home/minerva/minerva-control'
		config_file = 'telescope_3.ini'
        else: 
		base_directory = 'C:/minerva-control/'
		config_file = 'telescope_' + socket.gethostname()[1] + '.ini'

	telescope = CDK700(config_file, base_directory)
	ipdb.set_trace()

	while True:
		print telescope.logger_name + ' test program'
		print ' a. move to alt az'
		print ' b. auto focus'
		print ' c. kill pwi'
		print ' d. start pwi'
		print ' e. n/a'
		print ' f. n/a'
		print '----------------------------'
		choice = raw_input('choice:')

		if choice == 'a':
			telescope.mountGotoAltAz(45,45)
		elif choice == 'b':
			telescope.autoFocus()
		elif choice == 'c':
			telescope.killPWI()
		elif choice == 'd':
			telescope.startPWI()
		elif choice == 'e':
			pass
		elif choice == 'f':
			pass
		else:
			print 'invalid choice'
	
	
	
	
	
