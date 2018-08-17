import socket
import sys
import subprocess
import logging
import os
import datetime
import threading
from configobj import ConfigObj
sys.dont_write_bytecode = True
import utils

class telcom_client:
	
	def __init__(self,config,base):
		
		self.lock = threading.Lock()
		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)

	def load_config(self):
		try:
			config = ConfigObj(self.base_directory+ '/config/' + self.config_file)
			self.ip = config['SERVER']
			self.port = int(config['PORT'])
			self.logger_name = config['LOGNAME']

		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()

                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')
			
	#return a socket object connected to the server
	def connect_server(self):
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.settimeout(1)
			s.connect((self.ip, self.port))
		except:
			self.logger.error('connection failed')
		return s
	#send commands to server
	def send(self,msg,timeout):
		self.logger.info("Beginning serial communications with the telcom server")
		with self.lock:
			try:
				s = self.connect_server()
				s.settimeout(3)
				s.sendall(msg)
			except:
				self.logger.error("connection lost")
				return 'fail'
			try:
				s.settimeout(timeout)
				data = s.recv(1024)
			except:
				self.logger.error("connection timed out")
				return 'fail'
			try:
				command = msg.split()[0]
				data = repr(data).strip("'")
				data_ret = data.split()[0]
			except:
				self.logger.error("error processing server response")
				return 'fail'
			if data_ret == 'fail':
				self.logger.error("command failed("+command+')')
			return data

	def home(self):
		if (self.send('home none',15)).split()[0] == 'success':
			return True
		else:
			return False

	def home_rotator(self):
		if (self.send('home_rotator none',15)).split()[0] == 'success':
			return True
		else:
			return False

	def initialize_autofocus(self):
		if (self.send('initialize_autofocus none',15)).split()[0] == 'success':
			return True
		else:
			return False
			
	def startPWI(self):
		if (self.send('start_pwi none',15)).split()[0] == 'success':
			return True
		else:
			return False
	def killPWI(self):
		if (self.send('kill_pwi none',15)).split()[0] == 'success':
			return True
		else:
			return False
	def restartPWI(self):
		if (self.send('restart_pwi none',15)).split()[0] == 'success':
			return True
		else:
			return False
	def setxmlfile(self, filename):
		if (self.send('setxmlfile '+filename,15)).split()[0] == 'success':
			return True
		else:
			return False
	def checkPointingModel(self, filename):
		if (self.send('checkPointingModel '+filename,15)).split()[0] == 'success':
			return True
		else:
			return False


if __name__ == '__main__':
	
	config_file = 'telcom_client_2.ini'
	base_d = '/home/minerva/minerva-control'
	
	client = telcom_client(config_file,base_d)
	if client.restartPWI():
		print 'success'
	else:
		print 'fail'
	
	
	
  
