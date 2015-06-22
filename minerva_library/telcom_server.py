from configobj import ConfigObj
from scp import SCPClient
import numpy as np
import os,sys,glob, socket, logging, datetime, ipdb, time, json, threading, psutil, subprocess


class server:

	def __init__(self, config, base=''):

		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.setup_logger()
		
#==============utility functions=================#
#these methods are not directly called by client

	def load_config(self):
		try:
			config = ConfigObj(self.base_directory+ '/config/' + self.config_file)
			self.host = config['HOST']
			self.port = int(config['PORT'])
			self.logger_name = config['LOGNAME']
			self.header_buffer = ''
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()
			

		
	def setup_logger(self,night ='dump'):
		
		log_directory = self.base_directory + '/log/' + night
		self.logger = logging.getLogger(self.logger_name)
		formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
		if os.path.exists(log_directory) == False:
			os.mkdir(log_directory)
		self.logger.handlers = []
		fileHandler = logging.FileHandler(log_directory + '/' + self.logger_name + '.log', mode='a+')
		fileHandler.setFormatter(formatter)
		streamHandler = logging.StreamHandler()
		streamHandler.setFormatter(formatter)
		self.logger.setLevel(logging.DEBUG)
		self.logger.addHandler(fileHandler)
		self.logger.addHandler(streamHandler)

	def killPWI(self):
		for p in psutil.process_iter():
			try:
				pinfo = p.as_dict(attrs=['pid','name'])
				if pinfo['name'] == 'PWI.exe':
					self.logger.info('Killing PWI')
					p.kill()
					return True
			except psutil.Error:
				return False
		return True
			
#==========command functions==============#
#methods directly called by client
	def start_pwi(self):
		for p in psutil.process_iter():
			try:
				pinfo = p.as_dict(attrs=['pid','name'])
				if pinfo['name'] == 'PWI.exe':
					self.logger.info('PWI already running')
					return 'success'
			except psutil.Error:
				pass

		self.logger.info('PWI not running, starting now')
		try:
			subprocess.Popen(["C:\Program Files\PlaneWave Instruments\PlaneWave Interface\PWI.exe"])
		except:
			subprocess.Popen(["C:\Program Files (x86)\PlaneWave Instruments\PlaneWave Interface\PWI.exe"])
		time.sleep(5)   
		return 'success'
		
	def restart_pwi(self):
		if self.killPWI() == True:
			self.logger.info('PWI not running, starting now')
			if self.start_pwi() == 'success':
				return 'success'
		return 'fail'
		
#==================server functions===================#
#used to process communication between camera client and server==#

	#process received command from client program, and send response to given socket object
	def process_command(self, command, conn):
		tokens = command.split(None,1)
		if len(command) < 100:
			self.logger.info('command received: ' + command)
		if len(tokens) != 2:
			response = 'fail'
		elif tokens[0] == 'start_pwi':
			response = self.start_pwi()
		elif tokens[0] == 'kill_pwi':
			if self.kill_pwi():
				response = 'success'
			else:
				response = 'fail'
		elif tokens[0] == 'restart_pwi':
			response = self.restart_pwi()
		else:
			response = 'fail'
		try:
			conn.settimeout(3)
			conn.sendall(response)
			conn.close()
		except:
			self.logger.error('failed to send response, connection lost')
			return
			
		if response.split()[0] == 'fail':
			self.logger.info('command failed: (' + tokens[0] +')')
		else:
			self.logger.info('command succeeded(' + tokens[0] +')')
			
			
	#server loop that handles incoming command
	def run_server(self):
		
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.bind((self.host, self.port))
		s.listen(True)
		while True:
			print 'listening to incoming connection on port ' + str(self.port)
			conn, addr = s.accept()
			try:
				conn.settimeout(3)
				data = conn.recv(1024)
			except:
				break
			if not data:break
			self.process_command(repr(data).strip("'"),conn)
		s.close()
		self.run_server()

if __name__ == '__main__':
	config_file = 'telcom_server.ini'
	base_directory = 'C:\minerva_control'
	
	test_server = server(config_file,base_directory)
	test_server.run_server()
	
	
	
	
	
	
	