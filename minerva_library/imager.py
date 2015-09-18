import sys
import os
import socket
import errno
import logging
import time
import threading
import powerswitch
import telcom_client
import mail
import datetime
from configobj import ConfigObj
sys.dont_write_bytecode = True

class imager:

	def __init__(self,config, base =''):

		self.config_file = config
		self.base_directory = base
		self.load_config()
		self.setup_logger()
		self.nps = powerswitch.powerswitch(self.nps_config,base)
		self.initialize()
		self.telcom = telcom_client.telcom_client(self.telcom_client_config,base)
		self.status_lock = threading.RLock()
		# threading.Thread(target=self.write_status_thread).start()

	def initialize(self):
		self.connect_camera()
		self.set_binning()
		self.set_size()
		self.set_temperature()
		
	def load_config(self):
	
		try:
			config = ConfigObj(self.base_directory + '/config/' + self.config_file)
			self.ip = config['Setup']['SERVER_IP']
			self.port = int(config['Setup']['SERVER_PORT'])
			self.logger_name = config['Setup']['LOGNAME']
			self.nps_config = config['Setup']['POWERSWITCH']
			self.nps_port = config['Setup']['PSPORT']
			self.telcom_client_config = config['Setup']['TELCOM']
						
			self.platescale = float(config['Setup']['PLATESCALE'])
			self.filters = config['FILTERS']
			self.setTemp = float(config['Setup']['SETTEMP'])
			self.maxcool = float(config['Setup']['MAXCOOLING'])
			self.maxdiff = float(config['Setup']['MAXTEMPERROR'])
			self.xbin = int(config['Setup']['XBIN'])
			self.ybin = int(config['Setup']['YBIN'])
			self.x1 = config['Setup']['X1']
			self.x2 = config['Setup']['X2']
			self.y1 = config['Setup']['Y1']
			self.y2 = config['Setup']['Y2']

			self.biaslevel = float(config['Setup']['BIASLEVEL'])
			self.saturation = float(config['Setup']['SATURATION'])

			self.xcenter = config['Setup']['XCENTER']
			self.ycenter = config['Setup']['YCENTER']
			self.pointingModel = config['Setup']['POINTINGMODEL']
			self.datapath = ''
			self.gitpath = ''
			self.telescope_name = config['Setup']['TELESCOPE']
			self.telnum = self.telescope_name[1]
			self.exptypes = {'Dark' : 0,'Bias' : 0,'SkyFlat' : 1,}
			self.file_name = 'test'
			self.night = 'test'
			self.nfailed = 0
		except:
			print('ERROR accessing config file: ' + self.config_file)
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
		
	#return a socket object connected to the camera server
	def connect_server(self):
		telescope_name = 'T(' + self.telnum + '): '

		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.settimeout(5)
			s.connect((self.ip, self.port))
		except socket.error as e:
			if e.errno == errno.ECONNREFUSED:
				self.logger.exception(telescope_name + 'connection failed (socket.error)')
			self.logger.exception(telescope_name + 'connection failed')
			self.recover()
			return self.connect_server()
		except:
			self.logger.exception(telescope_name + 'connection failed')
			self.recover()
			return self.connect_server()

		return s
	#send commands to camera server
	def send(self,msg,timeout):
		telescope_name = 'T(' + self.telnum + '): '
		try:
			s = self.connect_server()
			s.settimeout(3)
			s.sendall(msg)
		except:
			self.logger.error(telescope_name + "connection lost")
			return 'fail'
		try:
			s.settimeout(timeout)
			data = s.recv(1024)
		except:
			self.logger.error(telescope_name + "connection timed out")
			return 'fail'
		try:
			command = msg.split()[0]
			data = repr(data).strip("'")
			data_ret = data.split()[0]
		except:
			self.logger.error(telescope_name + "error processing server response")
			return 'fail'

		if data_ret == 'fail': self.logger.error(telescope_name + "command failed("+command+')')
		return data
		
	def cool(self):
		telescope_name = 'T(' + self.telnum + '): '

		settleTime = 1200
                oscillationTime = 120.0
		
                self.logger.info(telescope_name + 'Turning cooler on')
		self.set_temperature()

                start = datetime.datetime.utcnow()
                currentTemp = self.get_temperature()
                if currentTemp == -999.0:
                        self.logger.warning(telescope_name + 'The camera failed to connect properly; beginning recovery')
                        self.recover()
                        return self.cool()

                elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()
                lastTimeNotAtTemp = datetime.datetime.utcnow() - datetime.timedelta(seconds=oscillationTime)
                elapsedTimeAtTemp = oscillationTime

		# Wait for temperature to settle (timeout of 15 minutes)                                                                           
                while elapsedTime < settleTime and ((abs(self.setTemp - currentTemp) > self.maxdiff) or elapsedTimeAtTemp < oscillationTime):
                        self.logger.info(telescope_name + 'Current temperature (' + str(currentTemp) +
                                         ') not at setpoint (' + str(self.setTemp) +
                                         '); waiting for CCD Temperature to stabilize (Elapsed time: '
                                         + str(elapsedTime) + ' seconds)')

			# has to maintain temp within range for 1 minute
			if (abs(self.setTemp - currentTemp) > self.maxdiff):
                                lastTimeNotAtTemp = datetime.datetime.utcnow()
			elapsedTimeAtTemp = (datetime.datetime.utcnow() - lastTimeNotAtTemp).total_seconds()

                        time.sleep(10)
                        currentTemp = self.get_temperature()
                        elapsedTime = (datetime.datetime.utcnow() - start).total_seconds()

                # Failed to reach setpoint 
                if (abs(self.setTemp - currentTemp)) > self.maxdiff:
                        self.logger.error(telescope_name + 'The camera was unable to reach its setpoint (' +
                                          str(self.setTemp) + ') in the elapsed time (' +
                                          str(elapsedTime) + ' seconds)')
                        return False

                return True

	# ask server to connect to camera
	def connect_camera(self):
		telescope_name = 'T(' + self.telnum + '): '

		if (self.send('connect_camera none',30)).split()[0] == 'success':
			if self.check_filters()==False:
				self.logger.error(telescope_name + 'mismatch filter')
				return False
			self.logger.info(telescope_name + 'successfully connected to camera')
			return True
		else:
			self.logger.error(telescope_name + 'failed to connected to camera, trying to recover')
			self.recover()
			return self.connect_camera()
			
	def disconnect_camera(self):
		
		telescope_name = 'T(' + self.telnum + '): '
		if self.send('disconnect_camera none',5) == 'success':
			self.logger.info(telescope_name + 'successfully disconnected camera')
			return True
		else:
			self.logger.error(telescope_name + 'failed to disconnect camera')
			return False
			
	#get camera status and write into a json file with name == (self.logger_name + 'json')
	def write_status(self):
		res = self.send('get_status none',5).split(None,1)
		if res[0] == 'success':
			self.status_lock.acquire()
			status = open(self.base_directory+'/status/' + self.logger_name + '.json','w')
			status.write(res[1])
			status.close()
			self.status_lock.release()
			return True
		else:
			return False
	#status thread
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
			
	#set path for which new images will be saved,if not set image will go into dump folder
	def set_dataPath(self):
		
		if self.send('set_data_path',3) == 'success':
			return True
		else:
			return False
	#get index of new image
	def get_index(self):
		res = self.send('get_index none',5).split()
		if res[0] == 'success': return int(res[1])
		else: return -1
	def get_filter_name(self):
		return self.send('get_filter_name ' + str(len(self.filters)),5)
	
	def getMean(self):
		res = self.send('getMean none',15).split()
		if res[0] == 'success':
			return float(res[1])
		else:
			return -9999
	
	def getMode(self):
		res = self.send('getMode none',15).split()
		if res[0] == 'success':
			return float(res[1])
		else:
			return -1
	
	def isSuperSaturated(self):
		res = self.send('isSuperSaturated none', 15).split()
		if res[0] == 'success':
			if res[1] == 'true':
				return True
		return False
	
	def remove(self):
		res = self.send('remove none',5).split()
		if res[0] == 'success':
			return True
		else:
			return False
	
	def check_filters(self):
		filter_names = self.get_filter_name().split()
			
		if len(filter_names) != len(self.filters)+1:
			return False
		for i in range(len(self.filters)):
			if filter_names[i+1] not in self.filters.keys():
				return False
		return True
			
	def set_binning(self):
		if self.send('set_binning ' + str(self.xbin) + ' ' + str(self.ybin), 5) == 'success': return True
		else: return False
		
	def set_size(self):
		if self.send('set_size '+ self.x1 + ' ' + self.x2 + ' ' + self.y1 + ' ' + self.y2,5) == 'success': return True
		else: return False
			
	def set_temperature(self):
		if self.send('set_temperature '+ str(self.setTemp),5) == 'success': return True
		else: return False

	def get_temperature(self):
		telescope_name = 'T(' + self.telnum + '): '

		result = self.send('get_temperature none',5)
		try:
			if 'success' in result:
				temp = result.split()
				if len(temp) != 2:
					self.logger.error(telescope_name + 'parameter error')
					return False
				return float(temp[1])
			else: return False
		except: 
			self.logger.exception(telescope_name + 'Unknown error getting temperature')
			return False

	#start exposure
	def expose(self, exptime=1, exptype=0, filterInd=1):
		if (self.send('expose ' + str(exptime) + ' ' + str(exptype) + ' ' + str(filterInd),30)).split()[0] == 'success': return True
		else: return False
	#block until image is ready, then save it to file_name
	def save_image(self,file_name):
		if self.send('save_image ' + file_name,30) == 'success': return True
		else: return False
	def image_name(self):
		return self.file_name
	#write fits header for self.file_name, header_info must be in json format
	def write_header(self, header_info):
		if self.file_name == '':
			return False
		i = 800
		length = len(header_info)
		while i < length:
			if self.send('write_header ' + header_info[i-800:i],3) == 'success':
				i+=800
			else:
				return False

		if self.send('write_header_done ' + header_info[i-800:length],10) == 'success':
			return True
		else:
			return False
	#returns file name of the image saved, return 'false' if error occurs
	def take_image(self,exptime=1,filterInd='zp',objname = 'test' ):
		
		telescope_name = 'T(' + self.telnum + '): '

		exptime = int(float(exptime)) #python can't do int(s) if s is a float in a string, this is work around
		#put together file name for the image
		ndx = self.get_index()
		if ndx == -1:
			self.logger.error(telescope_name + "Error getting the filename index")
			self.recover()
			return self.take_image(exptime=exptime, filterInd=filterInd,objname=objname)

		self.file_name = self.night + "." + self.telescope_name + "." + objname + "." + filterInd + "." + str(ndx).zfill(4) + ".fits"
		self.logger.info(telescope_name + 'start taking image: ' + self.file_name)
		#chose exposure type
		if objname in self.exptypes.keys():
			exptype = self.exptypes[objname] 
		else: exptype = 1 # science exposure

		#chose appropriate filter
		if filterInd not in self.filters:
			self.logger.error(telescope_name + "Requested filter (" + filterInd + ") not present")
			return 'false'
		
		
		if self.expose(exptime,exptype,self.filters[filterInd]):
			self.write_status()
			time.sleep(exptime)
			if self.save_image(self.file_name):
				self.logger.info(telescope_name + 'finish taking image: ' + self.file_name)
				self.nfailed = 0 # success; reset the failed counter
				return
			else: 
				self.logger.error(telescope_name + 'failed to save image: ' + self.file_name)
				self.file_name = ''
				self.recover()
				return self.take_image(exptime=exptime, filterInd=filterInd,objname=objname) 
			
		self.logger.error(telescope_name + 'taking image failed, image not saved: ' + self.file_name)
		self.file_name = ''
		return 'false'		

	def compress_data(self):
		#S I think we've given this too short of a time to reasonably compress
		#S the amount of data? On a few instances the thread died from connection being lost
		#S due to timeout.
		#TODO Increase tiimeout
		if self.send('compress_data none',30) == 'success': return True
		else: return False

	def powercycle(self):
		self.nps.cycle(self.nps_port)
		time.sleep(30)
		self.connect_camera()

	def restartmaxim(self):
		telescope_name = 'T(' + self.telnum + '): '
		self.logger.info(telescope_name + 'Killing maxim') 
		if self.send('restart_maxim none',15) == 'success': return True
		else: return False
		
	def recover(self):
		telescope_name = 'T(' + self.telnum + '): '
		self.nfailed = self.nfailed + 1

		try: self.disconnect_camera()
		except: pass

		if self.nfailed == 1:
			# attempt to reconnect
			self.logger.warning(telescope_name + 'Camera failed to connect; retrying') 
			self.connect_camera()
		elif self.nfailed == 2:
			# then restart maxim
			self.logger.warning(telescope_name + 'Camera failed to connect; restarting maxim') 
			self.restartmaxim()
		elif self.nfailed == 3:
			# then power cycle the camera
			self.logger.warning(telescope_name + 'Camera failed to connect; powercycling the imager') 
			self.powercycle()
		elif self.nfailed == 4:
			self.logger.error(telescope_name + 'Camera failed to connect!') 
			mail.send("Camera " + self.logger_name + " failed to connect","please do something",level="serious")
			sys.exit()

		
#test program, edit camera name to test desired camera
if __name__ == '__main__':
	
	base_directory = '/home/minerva/minerva-control'
	test_imager = imager('imager_t1.ini',base_directory)
	while True:
		print 'camera_control test program'
		print ' a. take_image'
		print ' b. expose'
		print ' c. set_data_path'
		print ' d. set_binning'
		print ' e. set_size'
		print ' f. settle_temp'
		print ' g. compress_data'
		print ' h. getMean'
		print ' i. getMode'
		print ' j. isSuperSaturated'
		print ' k. remove'
		print ' l. write_header'
		print ' m. connect_camera'
		print ' n. disconnect_camera'
		print ' o. powercycle'
		print ' p. restart_maxim'
		print '----------------------------'
		choice = raw_input('choice:')

		if choice == 'a':
			test_imager.take_image(1.0,'zp','test')
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
			test_imager.compress_data()
		elif choice == 'h':
			test_imager.getMean()
		elif choice == 'i':
			test_imager.getMode()
		elif choice == 'j':
			test_imager.isSuperSaturated()
		elif choice == 'k':
			test_imager.remove()
		elif choice == 'l':
			test_imager.write_header('{"status":["normal","abnormal"]}')
		elif choice == 'm':
			test_imager.connect_camera()
		elif choice == 'n':
			test_imager.disconnect_camera()
		elif choice == 'o':
			test_imager.powercycle()
		elif choice == 'p':
			test_imager.restartmaxim()
		else:
			print 'invalid choice'
			
			
	
