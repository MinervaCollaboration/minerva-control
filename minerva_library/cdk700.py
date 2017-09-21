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
import random
import pyfits
from astropy import wcs

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
				self.focus[port] = self.default_focus[port]  #focuserStatus.position
				
			
	#additional higher level routines
	#tracking and detrotating should be on by default
	#much worse to be off when it should be on than vice versa
	def isInitialized(self,tracking=True, derotate=True):

		# check to see if it's properly initialized
		telescopeStatus = self.getStatus()

		#if telescopeStatus.mount.encoders_have_been_set <> 'True':
		#	self.logger.info('encoders not set (' + telescopeStatus.mount.encoders_have_been_set + '), telescope not initialized')
		#	return False
		if telescopeStatus.mount.alt_enabled <> 'True':
			self.logger.info('altitude motor not enabled (' + telescopeStatus.mount.alt_enabled + '), telescope not initialized')
			return False
		if telescopeStatus.mount.alt_motor_error_message <> 'No error': 
			self.logger.info('altitude motor error present (' + telescopeStatus.mount.alt_motor_error_message + '), telescope not initialized')
			return False
		if telescopeStatus.mount.azm_enabled <> 'True':
			self.logger.info('azimuth motor not enabled (' + telescopeStatus.mount.azm_enabled + '), telescope not initialized')
			return False
		if telescopeStatus.mount.azm_motor_error_message <> 'No error': 
			self.logger.info('azimuth motor error present (' + telescopeStatus.mount.azm_motor_error_message + '), telescope not initialized')
			return False
		if telescopeStatus.mount.connected <> 'True': 
			self.logger.info('mount not connected (' + telescopeStatus.mount.connected + '), telescope not initialized')
			return False
		if telescopeStatus.rotator.connected <> 'True': 
			self.logger.info('rotator not connected (' + telescopeStatus.rotator.connected + '), telescope not initialized')
			return False
		if telescopeStatus.focuser.connected <> 'True': 
			self.logger.info('focuser not connected (' + telescopeStatus.focuser.connected + '), telescope not initialized')
			return False


		if tracking:
			if telescopeStatus.mount.tracking <> 'True': 
				self.logger.info('mount not tracking (' + telescopeStatus.mount.tracking + '), telescope not initialized')
				return False
		else:
			if telescopeStatus.mount.tracking <> 'False': 
				self.logger.info('mount tracking (' + telescopeStatus.mount.tracking + '), telescope not initialized')
				return False
			
		if derotate:
			if telescopeStatus.rotator.altaz_derotate <> 'True': 
				self.logger.info('rotator not tracking (' + telescopeStatus.rotator.altaz_derotate + '), telescope not initialized')
				return False
		else:
			if telescopeStatus.rotator.altaz_derotate <> 'False': 
				self.logger.info('rotator tracking (' + telescopeStatus.rotator.altaz_derotate + '), telescope not initialized')
				return False
					
		return True

	# by default, set tracking and derotating
	# it's much worse to have it off when it should be on than vice versa
	def initialize(self,tracking=True, derotate=True):

		telescopeStatus = self.getStatus()

		# connect to the mount if not connected
		if telescopeStatus.mount.connected <> 'True': 
			self.logger.info('Connecting to mount')
			if not self.mountConnect(): return False
			time.sleep(0.25)
			telescopeStatus = self.getStatus()

		# enable motors if not enabled
		if telescopeStatus.mount.alt_enabled <> 'True' or telescopeStatus.mount.azm_enabled <> 'True':
			self.logger.info('Enabling motors')
			if not self.mountEnableMotors(): return False
			time.sleep(0.25)
			telescopeStatus = self.getStatus()

		# connect to the focuser if not connected
		if telescopeStatus.focuser.connected <> 'True' or telescopeStatus.rotator.connected <> 'True':
			self.logger.info('Connecting to focuser')
			if not self.focuserConnect(): return False
			time.sleep(0.25)
			telescopeStatus = self.getStatus()

### Usually not necessary -- now part of the recovery procedure 
#		# home if not homed
#                if telescopeStatus.mount.encoders_have_been_set <> 'True':
#			self.logger.info('Homing telescope')
#                        if not self.home(): return False
#			time.sleep(0.25)
#			telescopeStatus = self.getStatus()

		# reload the pointing model
		self.logger.info('re-loading pointing model for the current port')
		self.m3port_switch(telescopeStatus.m3.port,force=True)
		telescopeStatus = self.getStatus()

		# turning on/off mount tracking, rotator tracking if not already on/off
		if tracking:
			if telescopeStatus.mount.tracking <> 'True': 
				self.logger.info('Turning mount tracking on')
				self.mountTrackingOn()
		else:
			if telescopeStatus.mount.tracking <> 'False': 
				self.logger.info('Turning mount tracking off')
				self.mountTrackingOff()
		
		if derotate:
			if telescopeStatus.rotator.altaz_derotate <> 'True': 
				self.logger.info('Turning rotator tracking on')
				self.rotatorStartDerotating()
		else:
			if telescopeStatus.rotator.altaz_derotate <> 'False': 
				self.logger.info('Turning rotator tracking off')
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
			self.id = config['Setup']['ID']
			self.pdu_config = config['Setup']['PDU']
			self.latitude = float(config['Setup']['LATITUDE'])
			self.longitude = float(config['Setup']['LONGITUDE'])
			self.elevation = float(config['Setup']['ELEVATION'])
			self.horizon = float(config['Setup']['HORIZON'])
			self.nfailed = 0
			self.port = config['PORT']
			self.modeldir = config['Setup']['MODELDIR']
			self.datadir = config['Setup']['DATADIR']
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
		status = xmltodict.parse(self.getStatusXml())['system']

		with open(self.currentStatusFile,'w') as outfile:
			json.dump(status,outfile)

		ipdb.set_trace()

		return status    

	def getStatus(self):
		"""
		Return a status object representing the tree structure of the XML text.
		Example: getStatus().mount.tracking --> "False"
		"""
		try: status = self.parseXml(self.getStatusXml())
		except: 
			xmlfile = open(self.base_directory + '/dependencies/telstateunknown.xml','r')
			errxml = xmlfile.readline()
			status = self.parseXml(errxml)

		self.logger.debug('Alt/Az RMS error: ' + status.mount.alt_rms_error_arcsec + ',' + status.mount.azm_rms_error_arcsec)
		return status

	def getFocuserStatus(self,m3port):
		telescopeStatus = self.getStatus()
		if str(m3port) == '1': return telescopeStatus.focuser1
		return telescopeStatus.focuser2

	def getRotatorStatus(self,m3port):
		telescopeStatus = self.getStatus()
		if str(m3port) == '1': return telescopeStatus.rotator1
		return telescopeStatus.rotator2

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
	def focuserConnect(self, m3port):
		"""
		Connect to the focuser on the specified Nasmyth port (1 or 2).
		"""

		return self.pwiRequestAndParse(device="focuser"+str(m3port), cmd="connect")

	def focuserDisconnect(self, m3port):
		"""
		Disconnect from the focuser on the specified Nasmyth port (1 or 2).
		"""

		return self.pwiRequestAndParse(device="focuser"+str(m3port), cmd="disconnect")

	def focuserMove(self, position, m3port):
		"""
		Move the focuser to the specified position in microns
		"""

		# make sure it's a legal move first
		if position < 0 or position > 33000: return False

		# port 2 on T1 is less forgiving and cannot go below 455 um...
		if self.id == 'T1' and str(m3port) == '2' and position < 455: return False

		return self.pwiRequestAndParse(device="focuser"+str(m3port), cmd="move", position=position)

	def focuserMoveAndWait(self,position,port=1,timeout=300.0):
		if not self.focuserMove(position,port=port):
			self.logger.warning('Focuser on port ' + str(port) + ' could not move to requested position (' + str(position) + ')')
			return False

		# wait for the focuser to start moving
		time.sleep(3.0) 
		focuserStatus = getFocuserStatus(port)

		t0 = datetime.datetime.utcnow()
		elapsedTime = 0.0
		
		# wait for the focuser to finish moving
		# or the timeout (90 seconds is about how long it takes to go from one extreme to the other)
		while focuserStatus.moving == 'True' and elapsedTime < timeout:
			self.logger.info('Focuser on port ' + str(port) + ' moving (' + str(focuserStatus.position) + ')')
			time.sleep(0.3)
			focuserStatus = getFocuserStatus(port)
			elapsedTime = (datetime.datetime.utcnow()-t0).total_seconds()

		if abs(float(focuserStatus.position) - float(position)) > 10:
			self.logger.warning('Focuser on port ' + str(port) + ' (' + focuserStatus.position + ') not at requested position (' + str(position) + ') after ' + str(elapsedTime) + ' seconds')
			return False

		self.logger.info('Focuser completed move in ' + str(elapsedTime) + ' seconds')
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

	def focuserHome(self, port=1):
		return self.pwiRequestAndParse(device="focuser" + str(port), cmd="findhome")

	def focuserHomeAndWait(self, port=1, timeout=300.0):

		# make sure it's not homing in another thread first
		focuserStatus = self.getFocuserStatus(port)
		if not focuserStatus.finding_home == 'True': self.focuserHome(port=port)

		time.sleep(5.0)
		focuserStatus = self.getFocuserStatus(port)

		t0 = datetime.datetime.utcnow()
		elapsedTime = 0
		while focuserStatus.finding_home == 'True' and elapsedTime < timeout:
			elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
			self.logger.info('Homing focuser ' + str(port) + ' (elapsed time = ' + str(elapsedTime) + ')')
			time.sleep(5.0)
			focuserStatus = self.getFocuserStatus(port)
			
		if elapsedTime > timeout:
			self.logger.error('Homing focuser ' + str(port) + ' failed')
			return False

		self.logger.info('Homing focuser ' + str(port) + ' complete; moving to nominal position (elapsed time = ' + str(elapsedTime) + ')')

		t0 = datetime.datetime.utcnow()
		elapsedTime = 0
		
		while focuserStatus.moving == 'True' and elapsedTime < 20.0:
			elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
			self.logger.info('Moving focuser ' + str(port) + ' to nominal position (elapsed time = ' + str(elapsedTime) + ')')
			time.sleep(1.0)
			focuserStatus = self.getFocuserStatus(port)
			
		if focuserStatus.moving == 'True':
			self.logger.error('Homing focuser ' + str(port) + ' failed')
			return False

		self.logger.info('Homing focuser ' + str(port) + ' complete')
		return True


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

	def rotatorHome(self, port=1):
		return self.pwiRequestAndParse(device="rotator" + str(port), cmd="findhome")	

	def rotatorHomeAndWait(self, port=1, timeout=400.0):

		# make sure it's not homing in another thread first
		rotatorStatus = self.getRotatorStatus(port)
		if not rotatorStatus.finding_home == 'True': self.rotatorHome(port=port)

		time.sleep(5.0)
		rotatorStatus = self.getRotatorStatus(port)

		t0 = datetime.datetime.utcnow()
		elapsedTime = 0
		while rotatorStatus.finding_home == 'True' and elapsedTime < timeout:
			elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
			self.logger.info('Homing rotator ' + str(port) + ' (elapsed time = ' + str(elapsedTime) + ')')
			time.sleep(5.0)
			rotatorStatus = self.getRotatorStatus(port)

		if elapsedTime > timeout:
			self.logger.error('Homing rotator ' + str(port) + ' failed')
			return False

		self.logger.info('Homing rotator ' + str(port) + ' complete; moving to nominal position (elapsed time = ' + str(elapsedTime) + ')')

		t0 = datetime.datetime.utcnow()
		elapsedTime = 0
		
		while rotatorStatus.moving == 'True' and elapsedTime < 20.0:
			elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
			self.logger.info('Moving rotator ' + str(port) + ' to nominal position (elapsed time = ' + str(elapsedTime) + ')')
			time.sleep(1.0)
			rotatorStatus = self.getRotatorStatus(port)
			
		if rotatorStatus.moving == 'True':
			self.logger.error('Homing rotator ' + str(port) + ' failed')
			return False

		self.logger.info('Homing rotator ' + str(port) + ' complete')
		return True


			
		if elapsedTime > timeout:
			return False

		return True



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


	### MOUNT ###
	def mountConnect(self):
		status = self.pwiRequestAndParse(device="mount", cmd="connect")
		if status.mount.connected == 'False':
			self.logger.error('Failed to connect to mount')
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

	def mountOffsetAltAzFixed(self,deltaAltArcseconds, deltaAzArcseconds):

		t0 = datetime.datetime.utcnow()

		# take 5 seconds to slew the Azimuth axis
		slewtimeAz = 2.0
		self.pwiRequestAndParse(device="mount",cmd="jog",
					axis1rate=str(deltaAzArcseconds/slewtimeAz/3600.0))
		# wait for the slew
		sleeptime = slewtimeAz - (datetime.datetime.utcnow()-t0).total_seconds()
		time.sleep(sleeptime)

		# take 5 seconds less the time it took to slew the Az Axis to slew the Altitude axis
		t0 = datetime.datetime.utcnow()
		slewtimeAlt = 2.0#slewtimeAz - (datetime.datetime.utcnow() - t0).total_seconds()
		self.pwiRequestAndParse(device="mount",cmd="jog",
					axis2rate=str(deltaAltArcseconds/slewtimeAlt/3600.0))
		
		# wait for the slew
		sleeptime = slewtimeAlt - (datetime.datetime.utcnow()-t0).total_seconds()
		time.sleep(sleeptime)

		# stop the axes
		return self.pwiRequestAndParse(device="mount",cmd="stop")

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

	def mountSaveModel(self,filename):
		return self.pwiRequestAndParse(device="mount",cmd="savemodel",filename=filename)

	def mountSync(self,ra,dec):
		return self.pwiRequestAndParse(device="mount",cmd="sync",ra2000=ra,dec2000=dec)

	### M3 ###
	def m3SelectPort(self, port):
		return self.pwiRequestAndParse(device="m3", cmd="select", port=port)

	def m3Stop(self):
		return self.pwiRequestAndParse(device="m3", cmd="stop")

	def recover(self, tracking=True, derotate=True):
		#S need to make sure all these functions don't call recover
		#S shutdown looks clear, all basePWI functions
		self.nfailed += 1

		# reconnect
		if self.nfailed <= 1:
			self.logger.warning('failed; trying to reconnect')
			try: self.shutdown()
			except: pass
		
			if self.initialize(tracking=tracking, derotate=derotate):
				self.logger.info('recovered after reconnecting')
				return True


		if self.nfailed >= 2:
			telescopeStatus = self.getStatus()
			if telescopeStatus.mount.encoders_have_been_set <> 'True':
				self.logger.info('Homing telescope')
				if not self.home(): return False
				time.sleep(0.25)
				telescopeStatus = self.getStatus()

		# restart PWI
		self.logger.warning('reconnecting failed; restarting PWI')
		try: self.shutdown()
		except: pass
		self.restartPWI()
		
		if self.initialize(tracking=tracking, derotate=derotate):
			self.logger.info('recovered after restarting PWI')
			return True
		
		# power cycle and rehome the scope
		self.logger.info('restarting PWI failed, power cycling the mount')
		try: self.shutdown()
		except: pass
		self.killPWI()
		self.powercycle()
		self.startPWI()
		if self.initialize():
			self.logger.info('recovered after power cycling the mount')
			return True

		'''
		# reboot the telcom machine
		self.logger.info('power cycling the mount failed, rebooting the machine')
		try: self.shutdown()
		except: pass
		self.killPWI()
		self.pdu.panel.off()
		self.pdu.inst.off()
		self.reboot_telcom()
		time.sleep(60)
		self.pdu.panel.on()
		self.pdu.inst.on()
		time.sleep(180)
		self.startPWI()
		if self.initialize():
			self.logger.warning('recovered after rebooting the machine')
			return True
		'''

		# unrecoverable error
		filename = "telescope" + self.id + '.error'
		body = "Dear benevolent humans,\n\n" + \
		    "I have failed to recover automatially. Please recover me, then delete " + filename + " to restart operations.\n\n" + \
		    "Love,\n" + \
		    "MINERVA"			
		while not self.initialize(tracking=tracking, derotate=derotate):
			self.logger.error('Telescope has failed to automatically recover; intervention required')
			mail.send(self.id + " has failed",body,level='serious')
			fh = open(filename,'w')
			fh.close()
			while os.path.isfile(filename):
				time.sleep(1)
		return True

	def addPointToModel():
		pass
	
	'''
	makes a pointing model
	'''
	def makePointingModel(self, minerva, npoints=100, maxmag=4.0, 
			      fau=True, brightstar=True, random=False, grid=False, 
			      nalt=5, naz=20, exptime=5.0, filterName='V', shuffle=True, 
			      minalt=-999, maxalt=80.0,minaz=0.0,maxaz=360.0):
		
		# can't set defaults using self...
		if minalt == -999: minalt = self.horizon

		camera = utils.getCamera(minerva,self.id)
		datapath = self.datadir + self.night + '/'

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
			nstars = len(brightstars['dec'])
		elif random:			
			pass
		elif grid:
			npoints = nalt*naz
			x = np.linspace(minalt,maxalt,nalt)
			y = np.linspace(minaz,maxaz,naz,endpoint=False)
			alt,az = np.meshgrid(x,y)
			alts = np.reshape(alt,npoints)
			azs = np.reshape(az,npoints)
			
			# randomize the order of the grid points in case we have to stop early
			shufflendx = range(npoints)
			if shuffle: random.shuffle(shufflendx)
		else:
			self.logger.error("brightstar, random, or grid must be set to make a pointing model")
			
		pointsAdded = 0
		ntried = 50
		while pointsAdded < npoints:

			ntried += 1

			# create the pointing model by pointing to a series of bright stars
			if brightstar:
				# apply proper motion to coordinates
				raj2000 = float(brightstars['ra'][ntried % nstars])
				decj2000 = float(brightstars['dec'][ntried % nstars])
				pmra = float(brightstars['pmra'][ntried % nstars])
				pmdec = float(brightstars['pmdec'][ntried % nstars])
				ra,dec = self.starmotion(raj2000,decj2000,pmra,pmdec)
				self.logger.info("J2000 " + str(raj2000) + ',' + str(decj2000) + 
						 " adding proper motion " + str(pmra) + "," + str(pmdec) + 
						 " is " + str(ra) + "," + str(dec))

				# if the star is not above the horizon, skip to the next one
				alt,az = self.radectoaltaz(ra,dec)
				if alt < minalt or alt > maxalt: continue
			# create the pointing model by slewing to random alt/az coordinates
			elif random:
				alt = random.uniform(minalt,maxalt)
				az = random.uniform(minaz,maxaz)
				# TODO: convert to ra/dec
			# create the pointing model by slewing to to a grid of alt/az coordinates
			elif grid:
				if ntried > npoints: return
				alt = alts[shufflendx[ntried]]
				az = azs[shufflendx[ntried]]
				# TODO: convert to ra/dec
				
			target = {
				'ra':ra,
				'dec':dec,
				'spectroscopy':fau,
				'fauexptime': exptime,
				'name':'Pointing',
				}

			# slew to coordinates
			self.acquireTarget(target, derotate=derotate, m3port=m3port)

			#'''
			camera.fau.guiding=True
			camera.fau.acquisition_tolerance=1.5
			if minerva.fauguide(target,int(self.num),acquireonly=True,xfiber=xcenter,yfiber=ycenter,skiponfail=True):
				# add point to model
				self.logger.info("Adding point to model: ra = " + str(ra) + ", dec = " + str(dec))
				self.mountAddToModel(ra,dec)
				
				# save to the model file
				self.mountSaveModel(self.model[m3port])

				pointsAdded += 1
				if pointsAdded >= npoints: return
			continue
		        #'''

			imageName = minerva.takeFauImage(target,telescope_num=int(self.num))
			x,y = utils.findBrightest(datapath + imageName)
			if x==None or y==None: continue

			# update the reference pixel to the brightest (target) star
			f = pyfits.open(datapath + imageName, mode='update')
			f[0].header['CRVAL1'] = ra*15.0
			f[0].header['CRVAL2'] = dec
			f[0].header['CRPIX1'] = x
			f[0].header['CRPIX2'] = y
			f.flush()
			f.close()


			# call xy2sky to determine the J2000 coordinates of the center pixel
			p = subprocess.Popen(["xy2sky",datapath+imageName,str(xcenter),str(ycenter)],
					     stderr=subprocess.PIPE,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
			output,err = p.communicate()
			racen = utils.ten(output.split()[0])
			deccen = utils.ten(output.split()[1])


			'''
			ipdb.set_trace()


			f = pyfits.open(datapath + imageName)
			w = wcs.WCS(f[0].header)
			w.wcs.print_contents()



			w = wcs.WCS(naxis=2)
			w.wcs.crpix = [x,y]
			w.wcs.cdelt = [-platescale,platescale]
			w.wcs.crval = [ra,dec]
			w.wcs.ctype = ['RA---TAN','DEC--TAN']
#			w.wcs.set_pv([(2,1,45.0)])
			pixcrd = np.array([[xcenter,ycenter]],np.float)
			world = w.wcs_pix2world(pixcrd,1)

			ipdb.set_trace()

#			racen2  =  ra - raoffset/240.0
#			deccen2 = dec - decoffset/3600.0


		      
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
			rotatorStatus = self.getRotatorStatus(m3port)
			rotpos = float(rotatorStatus.position)
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
					self.logger.info('Finished jog')

				# take image
				imageName = camera.take_image(exptime=exptime, objname='Pointing', fau=fau, filterInd=filterName)

				# find the brightest star
				x,y = utils.findBrightest(datapath + imageName)
				if x==None or y==None: continue
				if x < edge or y < edge or xsize-x < edge or ysize-y < edge: continue
				
				# apply the rotation matrix
				raoffset  = ((x-xcenter)*math.cos(-skypa) - (y-ycenter)*math.sin(-skypa))*platescale/math.cos(dec*math.pi/180.0)
				decoffset = ((x-xcenter)*math.sin(-skypa) + (y-ycenter)*math.cos(-skypa))*platescale

			cd = [[-platescale*math.cos(skypa),platescale*math.sin(skypa)],\
			      [ platescale*math.sin(skypa),platescale*math.cos(skypa)]]
				
			xdiff = xcenter-x
			ydiff = ycenter-y
			xsi = cd[0,0]*xdiff + cd[0,1]*ydiff
			eta = cd[1,0]*xdiff + cd[1,1]*ydiff
			latitude = atan(math.pi/180.0/sqrt(xsi^2+eta^2) # theta in WCSXY2SPH 
			longitude = atan(xsi,-eta) # phi in WCSXY2SPH
			

			w = wcs.WCS(naxis=2)
			w.wcs.crpix = [x,y]
			w.wcs.cdelt = [-platescale,platescale]
			w.wcs.crval = [ra,dec]
			w.wcs.ctype = ['RA---TAN','DEC--TAN']
			w.wcs.set_pv([(0.0,0,90.0,180.0,90.0)])
			pixcrd = np.array([[xcenter,ycenter]],np.float)
			world = w.wcs_pix2world(pixcrd,1)

			racen2  =  ra - raoffset/240.0
			deccen2 = dec - decoffset/3600.0

			

			ipdb.set_trace()
			'''
			


			# add point to model
			self.logger.info("Adding point to model: RA_Center = " + str(racen) + ", Dec_center = " + str(deccen) + ", ra = " + str(ra) + ", dec = " + str(dec))
			self.mountAddToModel(racen,deccen)

			# save to the model file
			self.mountSaveModel(self.model[m3port])
		
			pointsAdded += 1

	# this is designed to calibrate the rotator using a single bright star
	def calibrateRotator(self, camera, fau=True, exptime=1):

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

		filename = camera.take_image(exptime=exptime,objname="rotatorCal",fau=fau)

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
			self.logger.info('Finished jog')

		# take exposure
		filename = camera.take_image(exptime=exptime,objname="rotatorCal",fau=fau)

		# locate star
		datapath = '/Data/t' + self.num + '/' + self.night + '/'
		x2, y2 = utils.findBrightest(datapath + filename)
		if x2 == None or y2 == None: return False

		rotatorStatus = self.getRotatorStatus(m3port)
		rotpos = float(rotatorStatus.position)
		parang = self.parangle(useCurrent=True)

		# calculate rotator angle
		skypa = math.atan2(y2-y1,x2-x1)*180.0/math.pi
		rotoff = (skypa - float(parang) + float(rotpos) + 360.0) % 360
		
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
			self.logger.info('Ensuring m3 port is at port ' + str(m3port) )
			while telescopeStatus.m3.port != str(m3port) and elapsedTime < timeout:
				time.sleep(0.5)
				#S This returns a status xml, so sending it on repeat shouldnt matter
				telescopeStatus = self.getStatus()
				#S Need to track elapsed time.
				elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
				changedPort = True
			if elapsedTime > timeout: 
				self.logger.error('Failed to select correct M3 port (' + str(m3port) + ')')
				return False
				
		#S If a bad port is specified (e.g. 3) or no port (e.g. None)
		else:
			self.logger.info('No M3 port specified or bad, using current port (' + telescopeStatus.m3.port + ')')
			m3port = telescopeStatus.m3.port


		self.logger.info('Waiting for telescope to finish slew; moving = ' + telescopeStatus.mount.moving + str(telescopeStatus.mount.moving == 'True') + str(elapsedTime < timeout) + str(tracking))
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
					self.logger.error('Telescope moving after it said it was done')

			if telescopeStatus.mount.alt_motor_error_code <> '0':
				self.logger.error('Error with altitude drive: ' + telescopeStatus.mount.alt_motor_error_message)
				return False

			if telescopeStatus.mount.azm_motor_error_code <> '0':
				self.logger.info('Error with azmimuth drive: ' + telescopeStatus.mount.azm_motor_error_message)
				return False

			if telescopeStatus.mount.alt_motor_error_code <> '0':
				self.logger.error('Error with altitude drive: ' + telescopeStatus.mount.alt_motor_error_message)
				return False

			if telescopeStatus.mount.azm_motor_error_code <> '0':
				self.logger.info('Error with azmimuth drive: ' + telescopeStatus.mount.azm_motor_error_message)
				return False

		# Make sure tracking is on
		if telescopeStatus.mount.tracking == 'False' and tracking:
			self.mountTrackingOn()
			self.logger.error('Tracking was off, turned tracking on')

		if elapsedTime > timeout or telescopeStatus.mount.on_target == False:
			self.logger.error('Failed to slew within timeout (' + str(timeout) + ')')
			return False

		# wait for Focuser
		focuserStatus = self.getFocuserStatus(m3port)
		self.logger.info('Waiting for Focuser to finish slew; goto_complete = ' + focuserStatus.goto_complete)
		timeout = 300.0
		while focuserStatus.goto_complete == 'False' and elapsedTime < timeout:
			time.sleep(0.5)
			self.logger.debug('Focuser moving (' + str(focuserStatus.position) + ')')
			elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
			focuserStatus = self.getFocuserStatus(m3port)

		if elapsedTime > timeout:
			self.logger.error('Failed to get to focus position within timeout (' + str(timeout) + ')')
			return False

		# if alt/az is specified, make sure we're close to the right position
		if alt <> None and az <> None:
			ActualAz = float(telescopeStatus.mount.azm_radian)
			ActualAlt = float(telescopeStatus.mount.alt_radian)
			DeltaPos = math.acos( math.sin(ActualAlt)*math.sin(alt*math.pi/180.0)+math.cos(ActualAlt)*math.cos(alt*math.pi/180.0)\
						      *math.cos(ActualAz-az*math.pi/180.0) )*(180./math.pi)*3600.0
			if DeltaPos > pointingTolerance:
				self.logger.error("Telescope reports it is " + str(DeltaPos)\
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
				self.logger.error("Telescope reports it is " + str(DeltaPos)\
							  + " arcsec away from the target postion (Dec="\
							  + str(ActualDec*180.0/math.pi) + " degrees, Requested Dec=" + str(dec) + ", RA="\
							  + str(ActualRa*12.0/math.pi) + " hours, Requested Ra=" + str(ra))
				self.nfailed += 1
				return False


                #S Make sure the derotating is on.
		rotatorStatus = self.getRotatorStatus(m3port)
		if derotate:
			self.rotatorStartDerotating(port=m3port)
			timeout = 360.0
			self.logger.info('Waiting for rotator to finish slew; goto_complete = ' + rotatorStatus.goto_complete)
			while rotatorStatus.goto_complete == 'False' and elapsedTime < timeout:
				time.sleep(0.5)
				self.logger.debug('rotator moving (' + str(rotatorStatus.position) + ' degrees)')
				elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
				rotatorStatus = self.getRotatorStatus(m3port)

			# Make sure derotating is on.
			if rotatorStatus.altaz_derotate == 'False':
				self.rotatorStartDerotating(port=m3port)
				self.logger.error('Derotating was off, turned on')
		else:
			if rotatorStatus.rotator.altaz_derotate == 'True':
				self.rotatorStopDerotating(port=m3port)
				self.logger.error('Derotating was on, turned off')


		if elapsedTime > timeout:
			self.logger.error('Failed to get to rotator position within timeout (' + str(timeout) + ')')
			return False

		# if it gets here, we are in position
		self.nfailed = 0
		return True

	def starmotion(self,ra,dec,pmra,pmdec,px=0.0,rv=0.0,date=None):

		if date == None: date = datetime.datetime.utcnow()

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
		if alt < self.horizon or alt > 85:
			self.logger.error("Coordinates out of bounds; object not acquired! (Alt,Az) = (" + str(alt) + "," + str(az) + "), (RA,Dec) = (" + str(ra_corrected) + ',' + str(dec_corrected) + ")")
#			self.logger.info("... but something is going wrong with these calculations; I'm going to try to acquire anyway")
			return 'out of bounds'
			return False

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
		self.logger.info('Starting slew to J2000 ' + str(ra_corrected) + ',' + str(dec_corrected))
		self.mountGotoRaDecJ2000(ra_corrected,dec_corrected)

		if self.inPosition(m3port=m3port, ra=ra_corrected, dec=dec_corrected, tracking=tracking, derotate=derotate):
			self.logger.info('Finished slew to J2000 ' + str(ra_corrected) + ',' + str(dec_corrected))
			return True
		else:
			self.logger.error('Slew failed to J2000 ' + str(ra_corrected) + ',' + str(dec_corrected))
			self.recover(tracking=tracking, derotate=derotate)
			self.m3port_switch(m3port,force=True)
			#XXX Something bad is going to happen here (recursive call, potential infinite loop).
			return self.acquireTarget(target,pa=pa, tracking=tracking, derotate=derotate, m3port=m3port)

	def radectoaltaz(self,ra,dec,date=None):

		# if set as a default, it evaluates once when the function is initialized
		# not every time the function is called
		if date == None: date = datetime.datetime.utcnow()

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
			self.logger.info('Ensuring m3 port is at port %s.'%(str(m3port)))
			if telescopeStatus.m3.port != str(m3port) or force:
				if telescopeStatus.m3.port != str(m3port):
					self.logger.info('Port changed, loading pointing model')
				
					# load the pointing model
					modelfile = self.modeldir + self.model[m3port]
					if os.path.isfile(modelfile):
						self.logger.info('changing model file')
						self.mountSetPointingModel(self.model[m3port])
					else:
						self.logger.error('model file (%s) does not exist; using current model'%(modelfile))
						mail.send('model file (%s) does not exist; using current model'%(modelfile),'',level='serious')
					
					telescopeStatus = self.m3SelectPort(port=m3port)
					time.sleep(0.5)
					
					telescopeStatus = self.m3SelectPort(port=m3port)

					# TODO: add a timeout here!
					while telescopeStatus.m3.moving_rotate == 'True':
						time.sleep(0.1)
						telescopeStatus = self.getStatus()
						
				
		#S If a bad port is specified (e.g. 3) or no port (e.g. None)
		else:
			self.logger.error('Bad M3 port specified (%s); using current port(%s)'%(m3port,telescopeStatus.m3.port))
					   
	def isReady(self,tracking=False,port=None,ra=None,dec=None,pa=None):
		if not self.isInitialized():
			#TODO
			#S This is not smart, need to work in a recovery process some how
			while not self.initialize(tracking=tracking):
				pass
		self.inPostion()
		status = self.getStatus()
		if port == None:
			self.logger.info('No M3 port specified, using current port(%s)'%(status.m3.port))
		if (ra == None) or (dec == None) :
			self.logger.info('No target coordinates given, maintaining ra=%s,dec=%s'%(str(ra),str(dec)))
		

	def park(self):
		# park the scope (no danger of pointing at the sun if opened during the day)
		self.initialize(tracking=True, derotate=False)
		parkAlt = 45.0
		parkAz = 0.0 

		self.logger.info('Parking telescope (alt=' + str(parkAlt) + ', az=' + str(parkAz) + ')')
		self.mountGotoAltAz(parkAlt, parkAz)

#		self.initialize(tracking=False, derotate=False)
#		self.logger.info('Turning rotator tracking off')
#		self.rotatorStopDerotating()
		
		if not self.inPosition(alt=parkAlt,az=parkAz, pointingTolerance=3600.0,derotate=False):
			if self.recover(tracking=False, derotate=False): self.park()

		self.logger.info('Turning mount tracking off')
		self.mountTrackingOff()

	def recoverFocuser(self, focus, m3port):
		timeout = 60.0

		self.m3port_switch(m3port)

		self.logger.info('Beginning focuser recovery')

		self.focuserStop()
		self.rotatorStopDerotating()
		self.focuserDisconnect()
		self.restartPWI(email=False)
		time.sleep(5)

		self.initialize()
		self.focuserConnect()

		status = self.getStatus()
		if self.focuserMoveAndWait(self.focus[m3port],m3port):
			self.logger.info('Focuser recovered')			
			return

		# simple reconnecting failed, recover PWI
		self.nfailed += 2 # skip reconnecting step
		self.recover()
		if self.focuserMoveAndWait(self.focus[m3port],m3port):
			self.logger.info('Focuser recovered')			
			return
		self.logger.error('Focus timed out')
		mail.send('Focuser failed on ' + str(self.logger_name),"Try powercycling?",level='serious')

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

	#S increased default timeout to ten minutes due to pokey t2
	#S we can probably set this to be only for t2, but just a quick edit
	#TODO work on real timout
	def home(self, timeout=600):#420.0):
		
		# make sure it's not homing in another thread first (JDE 2017-06-09)
		telescopeStatus = self.getStatus()
		if not telescopeStatus.mount.is_finding_home == 'True': self.mountHome()

		time.sleep(5.0)
		telescopeStatus = self.getStatus()
		t0 = datetime.datetime.utcnow()
		elapsedTime = 0
		while telescopeStatus.mount.is_finding_home == 'True' and elapsedTime < timeout:
			elapsedTime = (datetime.datetime.utcnow() - t0).total_seconds()
			self.logger.info('Homing Telescope (elapsed time = ' + str(elapsedTime) + ')')
			time.sleep(5.0)
			telescopeStatus = self.getStatus()
		
		#S Let's force close PWI here (after a disconnect). What is happening I think is that 
		#S PWI freezes, and it can't home. While it's stuck in this loop of rehoming
		#S with no hope of exiting. All it does is continually hit time out. 
		#TODO Not entirely sure how to restart PWI, but will prioritize it.
		#S actual going to put an iteration limit of 2 on it for now, that way we'll get emails 
		#S and it won't keep spiralling downward.
		#TODO Need to think of a good way to setup iteration check... be right back to it
		# JDE 2016-04-20: self.home is and should remain a low-level function. Any recovery should be handled at a higher level (self.recover)

		if telescopeStatus.mount.encoders_have_been_set == 'False':
			self.logger.error('Error homing telescope (elapsed time = ' + str(elapsedTime) + ')')
			return False
		else:
			self.logger.info('Done homing telescope (elapsed time = ' + str(elapsedTime) + ')')
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
		return self.kill_remote_task('ComACRServer.exe')

	def kill_remote_task(self,taskname):
                return self.send_to_computer("taskkill /IM " + taskname + " /f")
 
	def reboot_telcom(self):
                return self.send_to_computer("python C:/minerva-control/minerva_library/reboot.py")

        def send_to_computer(self, cmd):
                f = open(self.base_directory + '/credentials/authentication.txt','r')
                username = f.readline().strip()
                password = f.readline().strip()
                f.close()

#                process = subprocess.Popen(["winexe","-U","HOME/" + username + "%" + password,"//" + self.HOST, cmd],stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#                out,err = process.communicate()
                out = ''
                err = ''
                cmdstr = "cat </dev/null | winexe -U HOME/" + username + "%" + password + " //" + self.HOST + " '" + cmd + "'"
                os.system(cmdstr)
                self.logger.info('cmd=' + cmd + ', out=' + out + ', err=' + err)
                self.logger.info(cmdstr)

                if 'NT_STATUS_HOST_UNREACHABLE' in out:
                        self.logger.error('the host is not reachable')
                        mail.send("T" + self.num + ' is unreachable',
                                  "Dear Benevolent Humans,\n\n"+
                                  "I cannot reach T" + self.num + ". Can you please check the power and internet connection?\n\n" +
                                  "Love,\nMINERVA",level="serious")
                        return False
                elif 'NT_STATUS_LOGON_FAILURE' in out:
                        self.logger.error('invalid credentials')
                        mail.send("Invalid credentials for T" + self.num,
                                  "Dear Benevolent Humans,\n\n"+
                                  "The credentials in " + self.base_directory +
                                  '/credentials/authentication.txt (username=' + username +
                                  ', password=' + password + ') appear to be outdated. Please fix it.\n\n' +
                                  'Love,\nMINERVA',level="serious")
                        return False
                elif 'ERROR: The process' in err:
                        self.logger.info('task already dead')
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
	
	
	
	
	
