'''basic Aqawan control class, writes log to aqawan_(1 or 2).log file
create class object by aqawan(aqawan_num), where aqawan_num specify which aqawan
test program creates aqawan(1) object and send keyboard commands'''

import time, telnetlib, socket, threading, logging


#To Do: change log to appropriate format, log open/close failure by reading status, add more functionality as needed 
class aqawan:

	#aqawan class init method, create an aqawan object by passing either 1 or 2 to specify which aqawan
	def __init__(self,aqawan_num):
	
		#set appropriate parameter based on aqawan_num
		if aqawan_num == 1:
			self.IP = '192.168.1.10'
			logger_name = 'aqawan_1'
			log_file = 'aqawan_1.log'
		elif aqawan_num == 2:
			self.IP = '192.168.1.14'
			logger_name = 'aqawan_2'
			log_file = 'aqawan_2.log'
			
		#setting up aqawan logger
		self.logger = logging.getLogger(logger_name)
		formatter = logging.Formatter('%(asctime)s : %(message)s')
		fileHandler = logging.FileHandler(log_file, mode='w')
		fileHandler.setFormatter(formatter)
		streamHandler = logging.StreamHandler()
		streamHandler.setFormatter(formatter)

		self.logger.setLevel(logging.DEBUG)
		self.logger.addHandler(fileHandler)
		self.logger.addHandler(streamHandler)   
	
		#start heartbeat thread, create lock object to prevent multiple PAC connection at same time
		self.h_thread = threading.Thread(target=self.heartbeat, args=())
		self.lock = threading.Lock()
		self.h_thread.start()
		
	#heartbeat thread function
	def heartbeat(self):
		while True:
			self.send('HEARTBEAT')
			time.sleep(15)
	#send message to aqawan
	def send(self,message):
		
		messages = ['HEARTBEAT','STOP','OPEN_SHUTTERS','CLOSE_SHUTTERS',
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
		# not an allowed message
		if not message in messages:
			self.logger.error('Message not recognized: ' + message)
			return -1
		
		port = 22004
		self.lock.acquire()
		try:
			tn = telnetlib.Telnet(self.IP,port,1)
		except socket.timeout:
			self.logger.error('Timeout attempting to connect to the aqawan')
			self.lock.release()
			return -1

		tn.write("vt100\r\n")
		tn.write(message + "\r\n")

		response = tn.read_until(b"/r/n/r/n#>",0.5)
		tn.close()
		self.lock.release()
		return response

		return response.split("=")[1].split()[0]
		return tn.read_all()
	#open both shutter
	def open_both(self):
		self.send('OPEN_SHUTTERS')
	#close both shutter
	def close_both(self):
		self.send('CLOSE_SEQUENTIAL')
	#get aqawan status
	def status(self):
		response = self.send('STATUS').split(',')
		status = {}
		for entry in response:
			if '=' in entry:
				status[(entry.split('='))[0].strip()] = (entry.split('='))[1].strip()

		return status
		

if __name__ == '__main__':

	aqawan_1 = aqawan(1)
	while True:
		command = raw_input('enter Aqawan command: ')
		print aqawan_1.send(command)