from configobj import ConfigObj
from scp import SCPClient
from win32com.client import Dispatch
from scipy import stats
import numpy as np
import os,sys,glob, socket, logging, datetime, ipdb, time, json, threading, pyfits, subprocess, collections

# full API at http://www.cyanogen.com/help/maximdl/MaxIm-DL.htm#Scripting.html

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
		self.set_data_path()
		self.connect_camera()
		
#==============utility functions=================#
#these methods are not directly called by client

	def load_config(self):
		try:
			config = ConfigObj(self.base_directory+ '/config/' + self.config_file)
			self.host = config['HOST']
			self.port = int(config['PORT'])
			self.data_path_base = config['DATA_PATH']
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

		'''
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
		'''

	def get_index(self,param):
		files = glob.glob(self.data_path + "/*.fits*")
		return 'success ' + str(len(files)+1)
			
	def get_status(self,param):

                try:
                        status = {}
                        status['CoolerOn'] = self.cam.CoolerOn
                        status['CurrentTemp'] = self.cam.Temperature
                        status['SetTemp'] = self.cam.TemperatureSetpoint
                        status['BinX'] = self.cam.BinX
                        status['BinY'] = self.cam.BinY
                        status['filter'] = self.cam.Filter
                        status['connected'] = self.cam.LinkEnabled
                        status['X1'] = self.cam.StartX
                        status['X2'] = self.cam.StartX + self.cam.NumX - 1
                        status['Y1'] = self.cam.StartY
                        status['Y2'] = self.cam.StartY + self.cam.NumY - 1
		except:
                        self.logger.exception("error getting camera status")
                        self.connect_camera()
                        return self.get_status(param)

		return 'success ' + json.dumps(status)
		
	#return true if temperature settles successfully, false if it fails
	def set_temperature(self,param):
		
		try:
			setTemp = param.split()
			if len(setTemp) != 1:
				self.logger.error('parameter error')
				return 'fail'
			setTemp = float(setTemp[0])
			self.cam.TemperatureSetpoint = setTemp
			self.cam.CoolerOn = True
			return 'success'
		except:
			self.logger.exception("Failed to set the temperature")
			return 'fail'
		
	def get_temperature(self):
		try:
			return 'success '+ str(self.cam.Temperature)
		except:
			return 'fail'
#==========command functions==============#
#methods directly called by client

	def connect_camera(self):

		try:
			# Connect to an instance of Maxim's camera control.
			# (This launches the app if needed)
			self.cam = Dispatch("MaxIm.CCDCamera")

			# Connect to the camera 
			self.logger.info('Connecting to camera') 
			self.cam.LinkEnabled = True

			# Prevent the camera from disconnecting when we exit
			self.logger.info('Preventing the camera from disconnecting when we exit') 
			self.cam.DisableAutoShutdown = True

			# If we were responsible for launching Maxim, this prevents
			# Maxim from closing when our application exits
			self.logger.info('Preventing maxim from closing upon exit')
			maxim = Dispatch("MaxIm.Application")
			maxim.LockApp = True
			return 'success'
		except:
			return 'fail'

	def disconnect(self):
		
		try:
			# Turn the cooler off 
			self.logger.info('Turning cooler off')
			self.cam.CoolerOn = False

			time.sleep(1)

			# Disconnect from the camera 
			self.logger.info('Disconnecting from the camera') 
			self.cam.LinkEnabled = False
			return 'success'
		except:
			return 'fail'
		
	#set binning
	def set_binning(self,param):
		
		param = param.split()
		if len(param) != 2:
			return 'fail'
		try:
			self.logger.info('Setting binning to ' + param[0] + ',' + param[1] )
			self.cam.BinX = int(param[0])
			self.cam.BinY = int(param[1])
			return 'success'
		except:
			self.logger.error('Setting binning to ' + param[0] + ',' + param[1] + ' failed')
			return 'fail'
			
	def set_size(self,param):
		param = param.split()
		if len(param) != 4:
			return 'fail'
		try:
			# Set to full frame
			xsize = int(param[1])-int(param[0])+1
			ysize = int(param[3])-int(param[2])+1
			self.logger.info('Setting subframe to [' + param[0] + ':' + param[1] + ',' +
						 param[2] + ':' + param[3] + ']')
			self.cam.StartX = int(param[0])
			self.cam.StartY = int(param[2])
			self.cam.NumX = xsize # CENTER_SUBFRAME_WIDTH
			self.cam.NumY = ysize # CENTER_SUBFRAME_HEIGHT
			return 'success'
		except:
			return 'fail'
		
	def get_filter_name(self,param):
		res = 'success '
		
		try:
			num = int(param)
			for i in range(int(param)):
				res += self.cam.FilterNames[i] + ' '
			return res
		except:
			return 'fail'
		
	def expose(self,param):
		try:
			param = param.split()
			exptime = int(param[0])
			exptype = int(param[1])
			filter_num = int(param[2])
			self.cam.Expose(exptime,exptype,filter_num)
			return 'success'
		except:
			return 'fail'
	
	def save_image(self,param):
		
		if len(param.split()) != 1:
			self.logger.error('parameter mismatch')
			return 'fail'
		try:
			while not self.cam.ImageReady:
				time.sleep(0.1)
			self.logger.info('saving image to:' + param)
			self.file_name = self.data_path + '\\' + param
			self.cam.SaveImage(self.file_name)
			return 'success'
		except:
			return 'fail'

	def write_header(self,param):
		
		self.header_buffer = self.header_buffer + param
		return 'success'
		
	def write_header_done(self,param):

		try: 
			self.logger.info("Writing header for " + self.file_name)
		except: 
			self.logger.error("self.file_name not defined; saving failed earlier")
			return 'fail'

		try:
			header_info = self.header_buffer + param
			self.header_buffer = ''
			f = pyfits.open(self.file_name, mode='update')
			for key,value in json.loads(header_info,object_pairs_hook=collections.OrderedDict).iteritems():
				if isinstance(value, (str, unicode)):
					f[0].header[key] = value
				else:
					f[0].header[key] = (value[0],value[1])
			f.flush()
			f.close()
		except:
			return 'fail'
		return 'success'
		
	def set_data_path(self):
		self.data_path = self.data_path_base + '\\' + self.night
		if not os.path.exists(self.data_path):
			os.makedirs(self.data_path)
		return 'success'
		
	def compress_data(self):
		try:
			#S This will throw if it doesn;t have data path, which
			#S seems like the only place how compression won't work now. 
			#S Still need to practice caution though, as the thread that 
			#S this function starts may still barf. I'm not sure if this should
			#S be communicated back to Main, but am still thinking about it.
			#TODO
			files = glob.glob(self.data_path + "/*.fits")
			compress_thread = threading.Thread(target = self.compress_thread,args = (files,))
			compress_thread.start()
			return 'success'
		
		except:
                        self.logger.exception('Compress thread failed to start')
			return 'fail'

	def compress_thread(self, files):
		for filename in files:
			logging.info('Compressing ' + filename)
			subprocess.call([self.base_directory + '/cfitsio/fpack.exe','-D',filename])
		

	def getMean(self):
		try:
			mean = pyfits.getdata(self.file_name,0).mean()
			mean = str(mean)
			res = 'success ' + mean
		except:
			res = 'fail'
		return res
	
	def getMode(self):
		try:
			image = pyfits.getdata(self.file_name,0)
			# mode is slow; take the central 100x100 region
			# (or the size of the image, which ever is smaller)
			nx = len(image)
			ny = len(image[1])
			size = 100
			x1 = max(nx/2.0 - size/2.0,0)
			x2 = min(nx/2.0 + size/2.0,nx-1)
			y1 = max(ny/2.0 - size/2.0,0)
			y2 = min(ny/2.0 + size/2.0,ny-1)
			
			mode = stats.mode(image[x1:x2,y1:y2],axis=None)[0][0]
			res = 'success ' + str(mode)
		except:
			res = 'fail'
		return res
		
	def isSuperSaturated(self):
		try:
			image = pyfits.getdata(self.file_name,0)
			# mode is slow; take the central 100x100 region
			# (or the size of the image, which ever is smaller)
			nx = len(image)
			ny = len(image[1])
			size = 100
			x1 = max(nx/2.0 - size/2.0,0)
			x2 = min(nx/2.0 + size/2.0,nx-1)
			y1 = max(ny/2.0 - size/2.0,0)
			y2 = min(ny/2.0 + size/2.0,ny-1)

			photonNoise = 10.0 # made up, should do this better
			if np.std(image[x1:x2,y1:y2],axis=None) < photonNoise:
				return 'success true'
			else:
				return 'success false'
		except:
			return 'fail'
			
	def remove(self):
		try:
			os.remove(self.file_name)
			return 'success'
		except:
			return 'fail'

	def restart_maxim(self):
		try:
			subprocess.call(['Taskkill','/IM','MaxIm_DL.exe','/F'])
			time.sleep(5)
			self.logger.info('Reconnecting')
			self.connect()
			return 'success'
		except:
			return 'fail'
	
	def disconnect_camera(self):
		try:
			self.logger.info('turning cooler off')
			self.cam.CoolerOn = False
			time.sleep(1)
			self.logger.info('disconnecting camera')
			self.cam.LinkEnabled = False 
			return 'success'
		except:
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
		elif tokens[0] == 'get_filter_name':
			response = self.get_filter_name(tokens[1])
		elif tokens[0] == 'expose':
			response = self.expose(tokens[1])
		elif tokens[0] == 'save_image':
			response = self.save_image(tokens[1])
		elif tokens[0] == 'set_camera_param':
			response = self.set_camera_param(tokens[1])
		elif tokens[0] == 'set_data_path':
			response = self.set_data_path()
		elif tokens[0] == 'get_status':
			response = self.get_status(tokens[1])
		elif tokens[0] == 'get_index':
			response = self.get_index(tokens[1])
		elif tokens[0] == 'set_binning':
			response = self.set_binning(tokens[1])
		elif tokens[0] == 'set_size':
			response = self.set_size(tokens[1])
		elif tokens[0] == 'write_header':
			response = self.write_header(tokens[1])
		elif tokens[0] == 'write_header_done':
			response = self.write_header_done(tokens[1])
		elif tokens[0] == 'compress_data':
			response = self.compress_data()
		elif tokens[0] == 'getMean':
			response = self.getMean()
		elif tokens[0] == 'getMode':
			response = self.getMode()
		elif tokens[0] == 'isSuperSaturated':
			response = self.isSuperSaturated()
		elif tokens[0] == 'remove':
			response = self.remove()
		elif tokens[0] == 'connect_camera':
			response = self.connect_camera()
		elif tokens[0] == 'disconnect_camera':
			response = self.disconnect_camera()
		elif tokens[0] == 'set_temperature':
			response = self.set_temperature(tokens[1])
		elif tokens[0] == 'get_temperature':
			response = self.get_temperature()
		elif tokens[0] == 'restart_maxim':
			response = self.restart_maxim()
		else:
			self.logger.info('command not recognized: (' + tokens[0] +')')
			response = 'fail'
		try:
			conn.settimeout(3)
			conn.sendall(response)
			conn.close()
		except:
			self.logger.exception('failed to send response, connection lost')
			return
			
		if response.split()[0] == 'fail':
			self.logger.info('command failed: (' + tokens[0] +')')
		else:
			self.logger.info('command succeeded(' + tokens[0] +')')
			
	#server loop that handles incoming command
	def run_server(self):
		
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try: s.bind((self.host, self.port))
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
    if socket.gethostname() == 'Minervared2-PC':
        config_file = 'imager_server_red.ini'
    else:
	config_file = 'imager_server.ini'
    base_directory = 'C:\minerva-control'
	
    test_server = server(config_file,base_directory)
    test_server.run_server()
	
	
	
	
	
	
	
