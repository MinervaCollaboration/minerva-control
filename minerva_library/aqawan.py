import os
import telnetlib
import socket
import ipdb
import sys
import os
import datetime
import logging
import json
import threading 
import time
import mail
from configobj import ConfigObj
sys.dont_write_bytecode = True


class aqawan:

	#initialize class by specify configuration file and software base directory
	def __init__(self,config,base):

		self.base_directory = base
		self.config_file = config
		self.load_config()
		self.setup_logger()
		self.setup_command_lib()
		
		self.initialized = False
		self.lock = threading.Lock()
		self.status_lock = threading.Lock()
		
	def load_config(self):
		#create configuration file object
	   
		try:
			config = ConfigObj(self.base_directory+'/config/' + self.config_file)
			self.IP = config['Setup']['IP']
			self.PORT = config['Setup']['PORT']
			self.logger_name = config['Setup']['LOGNAME']
			self.mailsent = False
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit() 
		
		self.isOpen = False
		self.lastClose = datetime.datetime.utcnow() - datetime.timedelta(days=1)
		
	def setup_logger(self,night='dump'):
			
		log_path = self.base_directory + '/log/' + night
		if os.path.exists(log_path) == False:os.mkdir(log_path)
		
		self.logger = logging.getLogger(self.logger_name)
		self.logger.setLevel(logging.INFO)

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
		
	def setup_command_lib(self):
		self.messages = ['HEARTBEAT','STOP','OPEN_SHUTTERS','CLOSE_SHUTTERS',
			'CLOSE_SEQUENTIAL','OPEN_SHUTTER_1','CLOSE_SHUTTER_1',
			'OPEN_SHUTTER_2','CLOSE_SHUTTER_2','LIGHTS_ON','LIGHTS_OFF',
			'ENC_FANS_HI','ENC_FANS_MED','ENC_FANS_LOW','ENC_FANS_OFF',
			'PANEL_LED_GREEN','PANEL_LED_YELLOW','PANEL_LED_RED',
			'PANEL_LED_OFF','DOOR_LED_GREEN','DOOR_LED_YELLOW',
			'DOOR_LED_RED','DOOR_LED_OFF','SON_ALERT_ON',
			'SON_ALERT_OFF','LED_STEADY','LED_BLINK',
			'MCB_RESET_POLE_FANS','MCB_RESET_TAIL_FANS',
			'MCB_RESET_OTA_BLOWER','MCB_RESET_PANEL_FANS',
			'MCB_TRIP_POLE_FANS','MCB_TRIP_TAIL_FANS',
			'MCB_TRIP_PANEL_FANS','STATUS','GET_ERRORS','GET_FAULTS',
			'CLEAR_ERRORS','CLEAR_FAULTS','RESET_PAC']
		
	#send message to aqawan
	def send(self,message):

		self.lock.acquire()
		# not an allowed message
		if not message in self.messages:
			self.logger.error('Message not recognized: ' + message)
			self.lock.release()
			return 'error'

		try:
			tn = telnetlib.Telnet(self.IP,self.PORT,1)
		except:
			self.logger.error('Error attempting to connect to the aqawan')
			self.lock.release()
			return 'error'

		tn.write("vt100\r\n")

		# why is this necessary!? this is quite unsettling
		response = ''
		while response == '':
			tn.write(message + "\r\n")
			response = tn.read_until(b"/r/n/r/n#>",0.5)
			
		tn.close()
		self.logger.debug('command(' + message +') sent')
		self.lock.release()

		return response
		
	def heartbeat(self):
		self.send('HEARTBEAT')
		
	# get aqawan status
	def status(self):
		response = self.send('STATUS').split(',')
		status = {}
		for entry in response:
			if '=' in entry:
				status[(entry.split('='))[0].strip()] = (entry.split('='))[1].strip()

		# check to make sure it has everything we use
		requiredKeys = ['Shutter1', 'Shutter2', 'SWVersion', 'EnclHumidity',
				'EntryDoor1', 'EntryDoor2', 'PanelDoor', 'Heartbeat',
				'SystemUpTime', 'Fault', 'Error', 'PanelExhaustTemp',
				'EnclTemp', 'EnclExhaustTemp', 'EnclIntakeTemp', 'LightsOn']
        
		for key in requiredKeys:
			if not key in status.keys():
				self.logger.error("Required key " + str(key) + " not present; trying again")
				status = self.status() # potential infinite loop!
                
#		with open(self.currentStatusFile,'w') as outfile:
#			json.dump(status,outfile)

		return status
		
	#write Aqawan status into a json file
	def write_status(self):
		response = self.status()
		self.status_lock.acquire()
		status_file = open(self.base_directory + '/status/aqawan_' + self.logger_name + '.json','w')
		status_file.write(json.dumps(response))
		status_file.close()
		self.status_lock.release()
		
	def open_shutter(self,shutter):
		# make sure this is an allowed shutter
		if shutter not in [1,2]:
			self.logger.error('Invalid shutter specified (' + str(shutter) + ')')
			return -1

		status = self.status()
		timeout = 180.0
		elapsedTime = 0.0

		# if it's already open, return
		if status['Shutter' + str(shutter)] == 'OPEN':
			self.logger.debug('Shutter ' + str(shutter) + ' already open')
			return

		# open the shutter
		start = datetime.datetime.utcnow()
		response = self.send('OPEN_SHUTTER_' + str(shutter))                
		self.logger.info(response)
		if not 'Success=TRUE' in response:
			# did the command fail?
			self.logger.warning('Failed to open shutter ' + str(shutter) + ': ' + response)
			return -1
			# need to reset the PAC? ("Enclosure not in AUTO"?)
		
		# Wait for it to open
		self.logger.info('Waiting for shutter ' + str(shutter) + ' to open')
		status = self.status()
		while status['Shutter' + str(shutter)] == 'OPENING' and elapsedTime < timeout:
			status = self.status()
			elapsedTime = (datetime.datetime.utcnow()-start).total_seconds()

		# Did it fail to open?
		if status['Shutter' + str(shutter)] <> 'OPEN':
			self.logger.error('Error opening Shutter ' + str(shutter) )
			return -1

		self.logger.info('Shutter ' + str(shutter) + ' open')
			
	#open both shutters
	def open_both(self):

		self.logger.debug('Shutting off lights')
		response = self.send('LIGHTS_OFF')
		if response == -1:
			self.logger.error('Could not turn off lights')

		self.logger.debug('Opening shutter 1')
		response = self.open_shutter(1)
		if response == -1: return -1
		self.logger.debug('Shutter 1 open')

		self.logger.debug('Opening shutter 2')
		response = self.open_shutter(2)
		if response == -1: return -1
		self.logger.debug('Shutter 2 open')

		self.isOpen = True
			

	def close_shutter(self,shutter):
		# make sure this is an allowed shutter
		if shutter not in [1,2]:
			self.logger.error('Invalid shutter specified (' + str(shutter) + ')')
			return -1

		status = self.status()
		timeout = 180.0
		elapsedTime = 0.0

		# if it's already open, return
		if status['Shutter' + str(shutter)] == 'CLOSED':
			logging.info('Shutter ' + str(shutter) + ' already open')
			return

		# open the shutter
		start = datetime.datetime.utcnow()
		response = self.send('OPEN_SHUTTER_' + str(shutter))                
		self.logger.info(response)
		if not 'Success=TRUE' in response:
			# did the command fail?
			self.logger.info('Failed to open shutter ' + str(shutter) + ': ' + response)
			ipdb.set_trace()
			# need to reset the PAC? ("Enclosure not in AUTO"?)
		
			# Wait for it to open
			status = self.status()
			while status['Shutter' + str(shutter)] == 'OPENING' and elapsedTime < timeout:
				status = self.status()
				elapsedTime = (datetime.datetime.utcnow()-start).total_seconds()

			# Did it fail to open?
			if status['Shutter' + str(shutter)] <> 'OPEN':
				self.logger.error('Error opening Shutter ' + str(shutter) )
				return -1

			self.logger.info('Shutter ' + str(shutter) + ' open')
			
	#close both shutter
	def close_both(self):
		timeout = 500
		elapsedTime = 0
		self.isOpen = False
		status = self.status()      
		if status['Shutter1'] == "CLOSED" and status['Shutter2'] == "CLOSED":
			self.logger.debug('Both shutters already closed')
			if self.mailsent:
				mail.send("Aqawan " + str(self.num) + " closed!","Love,\nMINERVA",level="critical")
				self.mailsent = False
		elif status['EnclOpMode'] == "MANUAL":
			self.logger.warning("Enclosure in manual; can't close")
			if self.mailsent:
				mail.send("Aqawan " + str(self.num) + " in manual","Please turn to 'AUTO' for computer control.\n Love,\nMINERVA")
				self.mailsent = False
		else:
			response = self.send('CLOSE_SEQUENTIAL')
			if not 'Success=TRUE' in response:
				self.logger.error('Aqawan failed to close!')
				self.isOpen = True
				if not self.mailsent:
					mail.send("Aqawan " + str(self.num) + " failed to close!","Love,\nMINERVA",level="critical")
					self.mailsent = True
				self.logger.info('Trying to close again!')
				self.close_both() # keep trying!
			else:
				self.logger.info(response)    
				start = datetime.datetime.utcnow()
				while (status['Shutter1'] <> "CLOSED" or status['Shutter2'] <> "CLOSED") and elapsedTime < timeout:
					elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
					status = self.status()
				if status['Shutter1'] <> "CLOSED" or status['Shutter2'] <> "CLOSED":
					self.logger.error('Aqawan failed to close after ' + str(elapsedTime) + 'seconds!')
					self.isOpen = True
					if not self.mailsent:
						mail.send("Aqawan " + str(self.num) + " failed to within the timeout!","Love,\nMINERVA",level="critical")
						self.mailsent = True
					self.close_both() # keep trying!
				else:
					self.logger.info('Closed both shutters')
					self.lastClose = datetime.datetime.utcnow()
					if self.mailsent:
						mail.send("Aqawan " + str(self.num) + " closed; crisis averted!","Love,\nMINERVA",level="critical")
						self.mailsent = False
			
if __name__ == '__main__':

	base_directory = '/home/minerva/minerva_control'
	dome = aqawan('aqawan_1.ini',base_directory)
	# while True:
		# print dome.logger_name + ' test program'
		# print ' a. open shutter 1'
		# print ' b. close shutter 1'
		# print ' c. open shutter 2'
		# print ' d. close shutter 2'
		# print ' e. open both shutters'
		# print ' f. close both shutters'
		# print '----------------------------'
		# choice = raw_input('choice:')

		# if choice == 'a':
			# dome.open_shutter(1)
		# elif choice == 'b':
			# dome.close_shutter(1)
		# elif choice == 'c':
			# dome.open_shutter(2)
		# elif choice == 'd':
			# dome.close_shutter(2)
		# elif choice == 'e':
			# dome.open_both()
		# elif choice == 'f':
			# dome.close_both()
		# else:
			# print 'invalid choice'
	
	

