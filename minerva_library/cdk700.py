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
import telcom_client
import threading
import numpy as np
import socket

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
		#S Set up logger
		self.setup_logger()
		#TODO Not really sure what powerswitch is really for yet.
		self.pdu = pdu.pdu(self.pdu_config,base)
		#TODO Get reading telcom as well
		self.telcom = telcom_client.telcom_client(self.telcom_client_config,base)
		#TODO I think I understand threading to some degre, but need to do some
		#TODO of my own experimenting to get a good grasp on it.
		self.status_lock = threading.RLock()
		# threading.Thread(target=self.write_status_thread).start()
		
		# initialize to the most recent best focus
		if os.path.isfile('focus.' + self.logger_name + '.txt'):
			f = open('focus.' + self.logger_name + '.txt','r')
			self.focus = float(f.readline())
			f.close()
		else:
			# if no recent best focus exists, initialize to 25000. (old: current value)
			status = self.getStatus()
			self.focus = 25000.0  #status.focuser.position

		self.num = self.logger_name[-1]
			
	#additional higher level routines
	def isInitialized(self,tracking=False):
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
				self.logger.warning('T' + self.num + ': mount not tracking (' + telescopeStatus.mount.tracking + '), telescope not initialized')
				return False
			if telescopeStatus.rotator.altaz_derotate <> 'True': 
				self.logger.warning('T' + self.num + ': rotator not tracking (' + telescopeStatus.altaz_derotate + '), telescope not initialized')
				return False
		
		return True

	def initialize(self,tracking=False):

		# turning on mount tracking
		self.logger.info('T' + self.num + ': Connecting to mount')
		self.mountConnect()
                #S Start yer engines
		self.logger.info('T' + self.num + ': Enabling motors')
		self.mountEnableMotors()

		self.logger.info('T' + self.num + ': Connecting to focuser')
		self.focuserConnect()
		
		self.logger.info('T' + self.num + ': Homing telescope')
		self.home()

		# turning on mount tracking, rotator tracking
		#S I'm defaulting this off, but including an argument in case we do want it
		#S This could be for initializing at 4PM start, or for testing. 
		if tracking:
			self.logger.info('T' + self.num + ': Turning mount tracking on')
			self.mountTrackingOn()
			self.logger.info('T' + self.num + ': Turning rotator tracking on')
			self.rotatorStartDerotating()

		return self.isInitialized(tracking=tracking)
		
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
			self.telcom_client_config = config['Setup']['TELCOM']
			self.nfailed = 0
			self.port = config['PORT']
			self.modeldir = config['Setup']['MODELDIR']
			self.model = config['MODEL']
		except:
			print("ERROR accessing configuration file: " + self.config_file)
			sys.exit() 

                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')

	def setup_logger(self):
			
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

	def mountSetPointingModel(self, filename):
		return self.pwiRequestAndParse(device="mount", cmd="setmodel", filename=filename)

	### M3 ###
	def m3SelectPort(self, port):
		return self.pwiRequestAndParse(device="m3", cmd="select", port=port)

	def m3Stop(self):
		return self.pwiRequestAndParse(device="m3", cmd="stop")

	def recover(self):
		self.logger.warning('T' + self.num + ': failed; trying to reconnect')
		try: self.shutdown()
		except: pass
		if self.initialize():
			self.logger.info('T' + self.num + ': recovered after reconnecting')
			return True

		self.logger.warning('T' + self.num + ': reconnecting failed; restarting PWI')
		try: self.shutdown()
		except: pass
		self.restartPWI()
		
		if self.initialize():
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
		while not self.initialize():
			self.logger.error('T' + self.num + ': Telescope has failed to automatically recover; intervention required')
			mail.send('T' + self.num + " has failed",body,level='serious')
			fh = open(filename,'w')
			fh.close()
			while os.path.isfile(filename):
				time.sleep(1)
		return self.initialize()

		# TODO
                # we never reset self.nfailed
		self.nfailed = self.nfailed + 1
		if self.nfailed == 1:
                        # just try to reconnect
			self.logger.info('T' + self.num + ': Failed 1 times; trying to reconnect')
                        try: self.shutdown()
                        except: pass
                        self.initialize()
                elif self.nfailed == 2:
                        # restart PWI and reconnect
			self.logger.info('T' + self.num + ': Failed 2 times; trying to restarting PWI')
                        try: self.shutdown()
                        except: pass
                        self.restartPWI()
                        self.initialize()
                elif self.nfailed == 3:
                        # power cycle and rehome the scope
			self.logger.info('T' + self.num + ': Failed 3 times; power cycling the mount')
 			try: self.shutdown()
			except: pass
			self.killPWI()
			self.powercycle()
			self.startPWI()
			self.initialize()
		if self.nfailed > 3:  
			self.logger.error('T' + self.num + ': Telescope has failed ' + str(self.nfailed) + ' times; something is probably seriously wrong...')
			body = "Dear benevolent humans,\n\n" + \
			    "I'm broken and have failed to recover automatially. Please help!\n\n" + \
			    "Love,\n" + \
			    "MINERVA"			
			mail.send('T' + self.num + " has failed " + str(self.nfailed) + " times",body,level='serious')
			ipdb.set_trace()

	def inPosition(self,m3port=None):

		# Wait for telescope to complete motion
		start = datetime.datetime.utcnow()
		timeout = 30.0
		elapsedTime = 0
		time.sleep(0.25) # needs time to start moving
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


		self.logger.info('T' + self.num + ': Waiting for telescope to finish slew; moving = ' + telescopeStatus.mount.moving)
		timeout = 60.0
		while telescopeStatus.mount.moving == 'True' and elapsedTime < timeout:
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

			#S Actually make sure tracking is on for both mount.
			if telescopeStatus.mount.tracking == 'False':
				#S or something like that.
				self.mountTrackingOn()
				self.logger.info('T%s: Tracking was off, turned tracking on.'%(self.num))
#				self.logger.info('T%s: Moving, but because tracking is OFF. Assuming in position'%(self.num))
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


		#S Make sure the derotating is on.
		self.rotatorStartDerotating()
		#S Let it finish derotating.
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

		if elapsedTime > timeout:
			self.logger.error('T%s: Failed to get to rotator position within timeout (%s)'%(self.num,timeout))
			return False

		# if it gets here, we are in position
		return True

	#TODO Search #TODOACQUIRE in control.py for all(?) calls on this function to be edited
        #S This has not been incorporated anywhere yet, and if it is all calls on the function will
	#S need to be edited to mathc the arguements. It is expecting a target dictionary now.
	def acquireTarget(self,target,pa=None):

		telescopeStatus = self.getStatus()

                ## Constants
                #S Was using julian date of observation, but this was only to have a more general approach to
                #S what coordinate system we were using. I assume we are using on J2000 coordinates, so I made it only take that for now.
                #S It can be switched very easily though
                #epoch = 2451545.0
                now = datetime.datetime.utcnow()
                j2000 = datetime.datetime(2000,01,01,12)
                days_since_j2000 = (now-j2000).days #[] = daya
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
                ra = np.radians(target['ra']*15.)
                dec = np.radians(target['dec'])
                #S basically see what values we can make corrections for.
                try: pmra = target['pmra']
                except: pmra = 0.
                try: pmdec = target['pmdec']
                except: pmdec = 0.
                try: px = target['px']
                except: px = 0.                        
                #S Need rv if available, in m/s
                try: rv = target['rv']
                except: rv = 0.
                        
                #S Unit vector pointing to star's epoch location
                r0hat = np.array([np.cos(ra)*np.cos(dec), np.sin(ra)*np.cos(dec), np.sin(dec)])
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

		#S make sure the m3 port is in the correct orientation
		self.m3port_check(target)

                	
		#S Initialize the telescope
                self.initialize(tracking=True)

		self.logger.info('T' + self.num + ': Starting slew to J2000 ' + str(ra_corrected) + ',' + str(dec_corrected))
		self.mountGotoRaDecJ2000(ra_corrected,dec_corrected)

		if pa <> None:
			self.logger.info('T' + self.num + ': Slewing rotator to PA=' + str(pa) + ' deg')
			self.rotatorMove(pa)

		if self.inPosition(m3port=m3port):
			self.logger.info('T' + self.num + ': Finished slew to J2000 ' + str(ra_corrected) + ',' + str(dec_corrected))
		else:
			self.logger.error('T' + self.num + ': Slew failed to J2000 ' + str(ra_corrected) + ',' + str(dec_corrected))
			self.recover()
			#XXX Something bad is going to happen here (recursive call, potential infinite loop).
			self.acquireTarget(target,pa=pa)
			return
	
	def m3port_check(self,target):

		if 'spectroscopy' in target.keys():
			if target['spectroscopy']:
				m3port = self.port['FAU']
			else: 
				m3port = self.port['IMAGER']
		else:
			m3port = self.port['IMAGER']

		#S want to make sure we are at the right port before mount, focuser, rotator slew.
		#S If an allowable port is specified
		if (str(m3port)=='1') or (str(m3port)=='2'):
			self.logger.info('T%s: Ensuring m3 port is at port %s.'%(self.num,str(m3port)))
			if telescopeStatus.m3.port != str(m3port):
				self.logger.info('T%s: Port changed, loading pointing model and restarting PWI'%(self.num))
				# load the pointing model
				modelfile = self.modeldir + self.model[m3port]
				if os.path.isfile(modelfile):
					self.mountSetPointingModel(modelfile)
				else:
					self.logger.error('T%s: model file (%s) does not exist; using current model'%(self.num, modelfile))
				telescopeStatus = self.m3SelectPort(port=m3port)
				
		#S If a bad port is specified (e.g. 3) or no port (e.g. None)
		else:
			self.logger.error('T%s: Bad M3 port specified (%s); using current port(%s)'%(self.num,m3port,telescopeStatus.m3.port))
					   

	def acquireTarget_old(self,ra,dec,pa=None):
		self.initialize(tracking=True)
	
		self.logger.info('T' + self.num + ': Starting slew to J2000 ' + str(ra) + ',' + str(dec))
		self.mountGotoRaDecJ2000(ra,dec)

		if pa <> None:
			self.logger.info('T' + self.num + ': Slewing rotator to PA=' + str(pa) + ' deg')
			self.rotatorMove(pa)

		if self.inPosition():
			self.logger.info('T' + self.num + ': Finished slew to J2000 ' + str(ra) + ',' + str(dec))
		else:
			self.logger.error('T' + self.num + ': Slew failed to J2000 ' + str(ra) + ',' + str(dec))
			self.recover()
			self.acquireTarget(ra,dec,pa=pa)
			return

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
		self.initialize(tracking=True)
		parkAlt = 45.0
		parkAz = 0.0 

		self.logger.info('T' + self.num + ': Parking telescope (alt=' + str(parkAlt) + ', az=' + str(parkAz) + ')')
		self.mountGotoAltAz(parkAlt, parkAz)
		self.inPosition()

		self.logger.info('T' + self.num + ': Turning mount tracking off')
		self.mountTrackingOff()
	
		self.logger.info('T' + self.num + ': Turning rotator tracking off')
		self.rotatorStopDerotating()

	def recoverFocuser(self):
		timeout = 60.0

		self.logger.info('T' + self.num + ': Beginning focuser recovery')

		self.focuserStop()
		self.rotatorStopDerotating()
		self.focuserDisconnect()
		self.restartPWI(email=False)
		time.sleep(5)

		self.initialize()
		self.focuserConnect()
		self.focuserMove(self.focus)
		t0 = datetime.datetime.utcnow()

		status = self.getStatus()
		while status.focuser.moving == 'True':
			self.logger.info('T' + self.num + ': Focuser moving (' + str(status.focuser.position) + ')')
			time.sleep(0.3)
			status = self.getStatus()
			if (datetime.datetime.utcnow() - t0).total_seconds() > timeout:
				self.logger.error('T' + self.num + ': Focus timed out')
				mail.send('T' + self.num + ': Focuser timed out on ' + str(self.logger_name),"Try powercycling?",level='serious')
				return
		self.logger.info('T' + self.num + ': Focuser recovered')
		
	def autoFocus(self):

		timeout = 360.0

		self.initialize()
		#S need tracking on for autofocus, not sure what will happen if we turn on while already on
		self.mountTrackingOn()

		self.logger.info('T' + self.num + ': Connecting to the focuser')
		self.focuserConnect()

		nominalFocus = self.focus
		self.logger.info('T' + self.num + ': Moving to nominal focus (' + str(nominalFocus) + ')')
		self.focuserMove(nominalFocus) # To get close to reasonable. Probably not a good general postion
		time.sleep(5.0)
		status = self.getStatus()
		while status.focuser.moving == 'True':
			self.logger.info('T' + self.num + ': Focuser moving (' + str(status.focuser.position) + ')')
			time.sleep(0.3)
			status = self.getStatus()
			
		self.logger.info('T' + self.num + ': Finished move to focus (' + str(status.focuser.position) + ')')


		self.logger.info('T' + self.num + ': Starting Autofocus')
		t0 = datetime.datetime.utcnow()
		self.startAutoFocus()
		status = self.getStatus()
		#TODO do we want to put this in a thread so we can run all four at the same time?
		while status.focuser.auto_focus_busy == 'True':
			time.sleep(1)
			status = self.getStatus()
			if (datetime.datetime.utcnow() - t0).total_seconds() > timeout:
				self.logger.error('T' + self.num + ': autofocus timed out')
				self.recoverFocuser()
				self.autoFocus()
				return
		
		status = self.getStatus()
		self.focus = float(status.focuser.position)
		alt = str(float(status.mount.alt_radian)*180.0/math.pi)

		try:    tm1 = str(status.temperature.primary)
		except:	tm1 = 'UNKNOWN'
		try:	tm2 = str(status.temperature.secondary)
		except:	tm2 = 'UNKNOWN'
		try:	tm3 = str(status.temperature.m3)
		except:	tm3 = 'UNKNOWN'
	        try:	tamb = str(status.temperature.ambient)
		except:	tamb = 'UNKNOWN'
		try:	tback = str(status.temperature.backplate)
		except: tback = 'UNKNOWN'
		
		self.logger.info('T' + self.num + ': Updating best focus to ' + str(self.focus) + ' (TM1=' + tm1 + ', TM2=' + tm2 + ', TM3=' + tm3 + ', Tamb=' + tamb + ', Tback=' + tback + ', alt=' + alt + ')' )
		f = open('focus.' + self.logger_name + '.txt','w')
		f.write(str(self.focus))
		f.close()
		
		self.logger.info('T' + self.num + ': Finished autofocus')

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
		#S Initialize here iterates home again, but it should catch and see
		#S that mount encoders are set. 
		self.initialize()
		status = self.getStatus()
		#S Let's force close PWI here (after a disconnect). What is happening I think is that 
		#S PWI freezes, and it can't home. While it's stuck in this loop of rehoming
		#S with no hope of exiting. All it does is continually hit time out. 
		#TODO Not entirely sure how to restart PWI, but will prioritize it.
		#S actual going to put an iteration limit of 2 on it for now, that way we'll get emails 
		#S and it won't keep spiralling downward.
		#TODO Need to think of a good way to setup iteration check... be right back to it
		if status.mount.encoders_have_been_set == 'False':
                        self.logger.error('T' + self.num + ': Mount failed to home; beginning recovery')
                        self.recover()
                        return self.home()
                else:
                        return True

		
		self.logger.info('T' + self.num + ': Homing the telscope')
		if self.telcom.home():return True
		else: 
			body = 'Dear humans,\n\n'\
			    'I failed to home correctly, and will need someone to help me through the process.'\
			    'Some investigation is in order to why this happened, and could be due to a number of reasons:\n'\
			    '1) Pywinauto may not have been able to get a hold of the correct windows.\n'\
			    '2) Hitting enter at the "OK" button on the pup-up DialogBox failed to get rid '\
			    'of the window after some attempts (should be five)\n'\
			    '3) I could have had an interruption in other software, causing a potential fail(?)\n\n'\
			    'Love,\n'\
			    '-MINERVA'
			mail.send('T' + self.num + ' failed to home correctly',body,level='serious')
			return False
		
	def home_rotator(self):
		self.logger.info('T' + self.num + ': Connecting to rotator')
		self.focuserConnect()

		self.logger.info('T' + self.num + ': Turning rotator tracking off')
		self.rotatorStopDerotating()

		self.logger.info('T' + self.num + ': Homing rotator')
		if self.telcom.home_rotator():return True
		else: return False
		
	def initialize_autofocus(self):
		if self.telcom.initialize_autofocus():return True
		else: return False

	def killPWI(self):
		if self.telcom.killPWI():return True
		else: return False
	def startPWI(self,email=True):
		if self.telcom.startPWI():
			time.sleep(5.0)
			return True
		else: return False
	def restartPWI(self,email=True):
		self.killPWI()
		time.sleep(5.0)
		return self.startPWI(email=email)

#test program
if __name__ == "__main__":

	if socket.gethostname() == 'Main':
		base_directory = '/home/minerva/minerva-control'
		config_file = 'telescope_1.ini'
        else: 
		base_directory = 'C:/minerva-control/'
		config_file = 'telescope_' + socket.gethostname()[-1] + '.ini'

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
	
	
	
	
	
