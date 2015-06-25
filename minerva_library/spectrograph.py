import sys
import os
import socket
import logging
import time
import threading
from configobj import ConfigObj
sys.dont_write_bytecode = True

# spectrograph control class, control all spectrograph hardware
class spectrograph:

	def __init__(self,config, base =''):

		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.setup_logger()
		self.create_class_objects
		self.status_lock = threading.RLock()
		# threading.Thread(target=self.write_status_thread).start()
	#load configuration file
	def load_config(self):
	
		try:
			config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.ip = config['Setup']['SERVER_IP']
			self.port = int(config['Setup']['SERVER_PORT'])
			self.logger_name = config['Setup']['LOGNAME']
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()

	#set up logger object
	def setup_logger(self,night='dump'):
		
		log_path = self.base_directory + '/log/' + night
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
		
	def create_class_objects(self):
		pass
	#return a socket object connected to the camera server
	def connect_server(self):
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.settimeout(1)
			s.connect((self.ip, self.port))
			self.logger.info('succefully connected to spectrograph server')
		except:
			self.logger.error('failed to connect to spectrograph server')
		return s
	#send commands to camera server running on telcom that has direct control over instrument
	def send(self,msg,timeout):
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
		data = repr(data).strip("'")
		if data.split()[0] == 'success':
			self.logger.info("command completed")
		else:
			self.logger.error("command failed")
		return data
	#get camera status and write into a json file with name == (self.logger_name + '.json')
	def write_status(self):
		res = self.send('get_status none',5).split(None,1)
		if res[0] == 'success':
			self.status_lock.acquire()
			status = open(self.base_directory+'/status/' + self.logger_name+ '.json','w')
			status.write(res[1])
			status.close()
			self.status_lock.release()
			self.logger.info('successfully wrote status')
			return True
		else:
			self.logger.error('failed to write status')
			return False
	#loop function used in a separate status thread
	def write_status_thread(self):
		while True:
			self.wite_status()
			time.sleep(10)
	#set path for which new images will be saved,if not set image will go into dump folder
	def set_data_path(self,night='dump'):
		
		self.night = night
		if self.send('set_data_path ' + night,3) == 'success':
			self.logger.info('successfully set datapath') 
			return True
		else:
			self.logger.error('failed to set datapath')
			return False
	#get index of new image
	def get_index(self):
		res = self.send('get_index none',5).split()
		if res[0] == 'success': return int(res[1])
		else: return -1
	def get_filter_name(self):
		return self.send('get_filter_name none',5)
	def check_filters(self):
		filter_names = self.get_filter_name().split()
		if len(filter_names) != len(self.filters)+1:
			return False
		for i in range(len(self.filters)):
			if self.filters[i] != filter_names[i+1]:
				return False
		return True
	#ask remote telcom to connect to camera
	def connect_camera(self):
		if (self.send('connect_camera none',30)).split()[0] == 'success':
			if self.check_filters()==False:
				self.logger.error('mismatch filter')
				return False
			self.logger.info('successfully connected to camera')
			return True
		else:
			self.logger.error('failed to connected to camera')
			return False
			
	def set_binning(self):
		if self.send('set_binning ' + self.xbin + ' ' + self.ybin, 5) == 'success': return True
		else: return False
		
	def set_size(self):
		if self.send('set_size '+ self.x1 + ' ' + self.x2 + ' ' + self.y1 + ' ' + self.y2,5) == 'success': return True
		else: return False
			
	def settle_temp(self):
		threading.Thread(target = self.send,args=('settle_temp ' + self.setTemp,910)).start()
		
	#start exposure
	def expose(self, exptime=1, exptype=0, filterInd=1):
		if (self.send('expose ' + str(exptime) + ' ' + str(exptype) + ' ' + str(filterInd),5)).split()[0] == 'success': return True
		else: return False
	#block until image is ready, then save it to file_name
	def save_image(self,file_name):
		if self.send('save_image ' + file_name,5) == 'success': return True
		else: return False
	
		
if __name__ == '__main__':
	
	base_directory = '/home/minerva/minerva_control'
	test_spectrograph = spectrograph('S1',base_directory)
	while True:
		print 'camera_control test program'
		print ' a. take_image'
		print ' b. expose'
		print ' c. set_data_path'
		print ' d. set_binning'
		print ' e. set_size'
		print ' f. settle_temp'
		print ' g. dummy'
		print ' h. dummy'
		print ' i. dummy'
		print '----------------------------'
		choice = raw_input('choice:')

		if choice == 'a':
			pass
		elif choice == 'b':
			test_imager.expose()
		elif choice == 'c':
			test_imager.set_data_path()
		elif choice == 'd':
			test_imager.set_binning()
		elif choice == 'e':
			test_imager.set_size()
		elif choice == 'f':
			test_imager.settle_temp()
		elif choice == 'g':
			pass
		else:
			print 'invalid choice'
			
			
	
