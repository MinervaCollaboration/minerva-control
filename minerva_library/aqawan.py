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
from filelock import FileLock
import utils

class aqawan:

	#initialize class by specify configuration file and software base directory
	def __init__(self,config,base):

		self.base_directory = base
		self.config_file = config
		self.load_config()
		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
		self.setup_command_lib()
		
		self.initialized = False
		self.lock = threading.Lock()
		self.status_lock = threading.RLock()
		# threading.Thread(target=self.write_status_thread).start()
		
		self.estopmail = "The emergency stop is active in the Aqawan, which prevents us from remotely controlling it.\n\n" +\
		"To reset the E-stop:\n\n" +\
		"1) Find the aqawan panel on center of the inside of the north wall. The code to get into the door is the same as the gate code.\n" +\
		"2) A blue light, labeled 'E-stop reset' on the top left of the panel will be flashing. Push it. " +\
		"The light should go off when pressed. If so, you're done. If not, continue to step 3.\n" +\
		"3) One of the E-stops was physically pushed. There's one next to each door and another on the hand paddle to the left of the aqawan panel."+\
		"Find the one that is depressed, turn it counter clockwise until it pops up, then repeat step 2.\n\n" + \
		"Love,\nMINERVA"
		
		self.rainChangeDate = datetime.datetime.utcnow()
		self.lastRain = 0.0

	def load_config(self):
		#create configuration file object
	   
		try:
			config = ConfigObj(self.base_directory+'/config/' + self.config_file)
			self.IP = config['Setup']['IP']
			self.PORT = config['Setup']['PORT']
			self.logger_name = config['Setup']['LOGNAME']
			self.num = config['Setup']['NUM']
			self.id = config['Setup']['ID']
			self.mailsent = False
			self.estopmailsent = False
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit() 
		
		today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')

	def isOpen(self):
		filename = self.base_directory + '/minerva_library/aqawan' + str(self.num) + '.stat'
		#with FileLock(filename):
		if True:	
			with open(filename,'r') as fh: line = fh.readline().split()
			try:
				lastUpdate = datetime.datetime.strptime(' '.join(line[0:2]),'%Y-%m-%d %H:%M:%S.%f')
				if (datetime.datetime.utcnow() - lastUpdate).total_seconds() > 300:
					self.logger.error("Dome status hasn't updated in 5 minutes; assuming closed")
					return False
				return line[2] == 'True'
			except:
				self.logger.exception("Failed to read aqawan status file")
				return False
		return False

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
		# not an allowed message
		if not message in self.messages:
			self.logger.error('Message not recognized: ' + message)
			return 'error'

		#self.logger.debug("Beginning serial communications with the aqawan")
		with self.lock:

			# connect to the aqawan
			try:
				tn = telnetlib.Telnet(self.IP,self.PORT,1)
			except:
				self.logger.error('Error connecting to the aqawan')
				return 'error'

			# configure the telnet terminal type
			tn.write("vt100\r\n")

			# send the message
			# repeatedly?! why is this necessary? this is quite unsettling...
			response = ''
			try:
				while response == '':
					tn.write(message + "\r\n")
					response = tn.read_until(b"/r/n/r/n#>",0.5)
			except:
				self.logger.exception('Error reading response from the aqawan')
				return 'error'
				
			# close the connection
			tn.close()
			self.logger.debug('command(' + message +') sent')
			return response
		
	def heartbeat(self):
		return self.send('HEARTBEAT')
		
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
			# need to reset the PAC? ("Enclosure not in AUTO"?)
			if "Estop active" in response:
				if not self.mailsent:
					mail.send("Aqawan " + str(self.num) + " Estop has been pressed!",self.estopmail,level='serious')
					self.mailsent = True
			return -1

		
		# Wait for it to open
		self.logger.info('Waiting for shutter ' + str(shutter) + ' to open')
		status = self.status()
		while status['Shutter' + str(shutter)] == 'OPENING' and elapsedTime < timeout:
			status = self.status()
			elapsedTime = (datetime.datetime.utcnow()-start).total_seconds()
			time.sleep(15.0) # make sure we don't block heartbeats

		# Did it fail to open?
		if status['Shutter' + str(shutter)] <> 'OPEN':
			self.logger.error('Error opening Shutter ' + str(shutter) + ', status=' + status['Shutter' + str(shutter)] )
			return -1

		self.logger.info('Shutter ' + str(shutter) + ' open')
			
	#open both shutters
	def open_both(self, reverse=False):
		if reverse:
			first = 2
			second = 1
		else:
			first = 1
			second = 2
			

		self.logger.debug('Shutting off lights')
		response = self.send('LIGHTS_OFF')
		if response == 'error':
			self.logger.error('Could not turn off lights')

		self.logger.debug('Opening shutter ' + str(first))
		response = self.open_shutter(first)
		if response == -1: return -1
		self.logger.debug('Shutter ' + str(first) + ' open')

		self.logger.debug('Opening shutter ' + str(second))
		response = self.open_shutter(second)
		if response == -1: return -1
		self.logger.debug('Shutter ' + str(second) + ' open')

	def lights_off(self):
		self.logger.debug('Shutting off lights')
		response = self.send('LIGHTS_OFF')
		if response == 'error':
			self.logger.error('Could not turn off lights')
		

	#close both shutter
	def close_both(self):
		timeout = 500
		elapsedTime = 0
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
				if "Estop active" in response:
					self.logger.error('Estop has been pressed!')					
					if not self.estopmailsent:
						mail.send("Aqawan " + str(self.num) + " Estop has been pressed, the aqawan is open, and it should be closed!",self.estopmail,level='critical')
						self.estopmailsent = True
				else:
					self.logger.error('Aqawan failed to close! Response = ' + response)
					if not self.mailsent:
						mail.send("Aqawan " + str(self.num) + " failed to close!","Love,\nMINERVA",level="critical")
						self.mailsent = True
					self.logger.info('Trying to close again!')
					self.close_both() # keep trying!
				return -1
			else:
				self.logger.info(response)    
				start = datetime.datetime.utcnow()
				while (status['Shutter1'] <> "CLOSED" or status['Shutter2'] <> "CLOSED") and elapsedTime < timeout:
					elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
					status = self.status()
				if status['Shutter1'] <> "CLOSED" or status['Shutter2'] <> "CLOSED":
					self.logger.error('Aqawan failed to close after ' + str(elapsedTime) + 'seconds!')
					if not self.mailsent:
						mail.send("Aqawan " + str(self.num) + " failed to close within the timeout!","Love,\nMINERVA",level="critical")
						self.mailsent = True
					self.close_both() # keep trying!
				else:
					self.logger.info('Closed both shutters')
					if self.mailsent or self.estopmailsent:
						mail.send("Aqawan " + str(self.num) + " closed; crisis averted!","Love,\nMINERVA",level="critical")
						self.mailsent = False
			
if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
	dome = aqawan('aqawan_1.ini',base_directory)
	ipdb.set_trace()
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
	
	

