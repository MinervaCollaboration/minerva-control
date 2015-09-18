from configobj import ConfigObj
from scp import SCPClient
import numpy as np
import os,sys,glob, socket, logging, datetime, ipdb, time, json, threading, psutil, subprocess
import pywinauto, SendKeys

class server:

	def __init__(self, config, base=''):

		self.config_file = config
		self.base_directory = base
		self.load_config()

		# reset the night at 10 am local                                                                                                 
		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
		night = 'n' + today.strftime('%Y%m%d')

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
			
                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')
		
	def setup_logger(self):
		
		log_directory = self.base_directory + '/log/' + self.night
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

	def home(self):
		try:
			# attach to PWI
			pwa_app = pywinauto.application.Application()
			w_handle = pywinauto.findwindows.find_windows(title_re='PWI*', class_name=\
				'WindowsForms10.Window.8.app.0.33c0d9d')[0]
			window = pwa_app.window_(handle=w_handle)

			# select the mount tab
			window.SetFocus()
			ctrl = window['TabControl2']
			ctrl.Click()
			ctrl.Select(0)

			# select the Home option
			ctrl = window['ComboBox']
			ctrl.Click()
			ctrl.Select(0)
			# click OK on the "home" pop up window
			#S Get the window containing our button, which is technically a DialogBox
			w_handle2 = (pywinauto.findwindows.find_windows(title=u'Home'))[0]
			window2 = pwa_app.window_(handle=w_handle2)
			#S Counting iterations through trying to smash 'enter' for the dialogbox
			ok_iter = 0
			iter_limit = 15
			#S While this dialogbox exists, were going to keep on hitting enter at it,
			#S AFTER we reset the focus to the correct button.
			while window2.Exists() and ok_iter<iter_limit:
				#S Increment iterations
				ok_iter += 1
				#S This selects the 'OK' button, then will hit enter while the DialogBox exists.
				window2['OK'].SetFocus()
				#window2['OK'].Click()
                                SendKeys.SendKeys("{ENTER}")
				time.sleep(0.05)

				#TODO Do we want it to sleep for a millisecond too? 
			#S This is to throw an exception if we hit the iteration limit.
			if ok_iter == iter_limit:
				raise ValueError('Tried to HOME telescope '+str(ok_iter)+' times.')
			return 'success'
		except:
			self.logger.exception("homing telescope failed")
			return 'fail'
	def home_rotator(self):
		try:
			# attach to PWI
			pwa_app = pywinauto.application.Application()
			w_handle = pywinauto.findwindows.find_windows(title_re='PWI*', class_name='WindowsForms10.Window.8.app.0.33c0d9d')[0]
			window = pwa_app.window_(handle=w_handle)

			# select the rotate tab
			window.SetFocus()
			ctrl = window['TabControl2']
			ctrl.Click()
			ctrl.Select(2)

			# select the Home option
			ctrl = window['ComboBox']
			ctrl.Click()
			ctrl.Select(2)
			return 'success'
		except:
			self.logger.exception("homing rotator failed")
			return 'fail'

        def initialize_autofocus(self):

                try:
			# attach to PWI
			pwa_app = pywinauto.application.Application()
			w_handle = pywinauto.findwindows.find_windows(title_re='PWI*', class_name='WindowsForms10.Window.8.app.0.33c0d9d')[0]
			window = pwa_app.window_(handle=w_handle)

			# select the auto focus tab
			window.SetFocus()
			ctrl = window['TabControl2']
			ctrl.Click()
			ctrl.Select(5)

			# start the autofocus
			ctrl = window['START']
			ctrl.Click()

			# wait a few seconds
			time.sleep(5)

			# select the auto focus tab
			window.SetFocus()
			ctrl = window['TabControl2']
			ctrl.Click()
			ctrl.Select(5)

			# stop the autofocus
			ctrl = window['STOP']
			ctrl.Click()
			return 'success'
		except:
			self.logger.exception("intializing autofocus failed")
			return 'fail'

	def kill_pwi(self):
		for p in psutil.process_iter():
			try:
				pinfo = p.as_dict(attrs=['pid','name'])
				if pinfo['name'] == 'PWI.exe':
					self.logger.info('Killing PWI')
					p.kill()
					return 'success'
			except psutil.Error:
				return 'fail'
		return 'success'
			
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
			response = self.kill_pwi()
		elif tokens[0] == 'restart_pwi':
			response = self.restart_pwi()
		elif tokens[0] == 'home':
			response = self.home()
		elif tokens[0] == 'home_rotator':
			response = self.home_rotator()
		elif tokens[0] == 'initialize_autofocus':
			response = self.initialize_autofocus()
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
		try:
			s.bind((self.host, self.port))
		except:
			self.logger.exception("Error connecting to server")
			raise
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
	base_directory = 'C:\minerva-control'
	
	test_server = server(config_file,base_directory)
	test_server.run_server()
	
	
	
	
	
	
	
