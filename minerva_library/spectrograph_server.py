import socket
import logging
import threading
from configobj import ConfigObj
import sys, ipdb
import com
import os
import time

# minerva library dependency
import spectrograph_modules
sys.dont_write_bytecode = True

class server:

	#initialize class
	def __init__(self,name,base):
		self.name = name
		self.base_directory = base
		self.data_directory = "C:/minerva/data"
		self.create_class_objects()
                self.load_config()
                self.setup_logger()
                self.night='dump'

	def load_config(self):
	
		configfile = self.base_directory + '/config/spectrograph_server.ini'
		
		try:
			config = ConfigObj(configfile)
			self.port = int(config['PORT'])
			self.ip = config['HOST']
                        self.logger_name = config['LOGNAME']
                        self.header_buffer = ''
		except:
			print('ERROR accessing ', self.name, ".", 
				   self.name, " was not found in the configuration file", configfile)
			return 
			
	#create instrument control objects
	def create_class_objects(self):
		pass
		
	#create logger object and link to log file
	def setup_logger(self, night='dump'):

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

		'''
		self.logger = logging.getLogger(self.name)
		formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
		fileHandler = logging.FileHandler(self.base_directory + '/log/' + folder + '/telecom_server.log', mode='a')
		fileHandler.setFormatter(formatter)
		streamHandler = logging.StreamHandler()
		streamHandler.setFormatter(formatter)

		self.logger.setLevel(logging.DEBUG)
		self.logger.addHandler(fileHandler)
		self.logger.addHandler(streamHandler)
		'''

#==================server functions===================#
#used to process communication between camera client and server==#

	#process received command from client program, and send response to given socket object
	def process_command(self, command, conn):
		command = command.strip("'")
		tokens = command.split(None,1)
		if len(tokens) != 2:
			response = 'fail'
		elif tokens[0] == 'get_vacuum_pressure':
                        response = self.get_vacuum_pressure()
                elif tokens[0] == 'get_atmospheric_pressure':
                        response = self.get_atmospheric_pressure()
		elif tokens[0] == 'get_filter_name':
			response = self.get_filter_name(tokens[1])
		elif tokens[0] == 'expose':
			response = self.expose(tokens[1])
		elif tokens[0] == 'set_camera_param':
			response = self.set_camera_param(tokens[1])
		elif tokens[0] == 'set_data_path':
			response = self.set_data_path(tokens[1])
		elif tokens[0] == 'get_status':
			response = self.get_status(tokens[1])
		elif tokens[0] == 'get_fits_header':
			response = self.get_fits_header(tokens[1])
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
			
			
	#server loop that runs indefinitely and handle communication with client
	def run_server(self):
		
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.bind((self.ip, self.port))
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
			self.process_command(repr(data),conn)
		s.close()
		self.run_server()
		
	def save_image(self,file_name):

                filename = "C:/minerva/data/" + self.night + "/" + file_name
                try:
                        shutil.move("C:/IMAGES/I",filename)

                        '''
                        # Fill in values from SI header
                        f = pyfits.open(filename)
                        hdr['NAXIS'] = f[0].header['NAXIS']
                        hdr['NAXIS1'] = f[0].header['NAXIS1']
                        hdr['NAXIS2'] = f[0].header['NAXIS2']
                        hdr['DATE-OBS'] = f[0].header['DATE-OBS']
                        hdr['EXPTIME'] = float(f[0].header['PARAM24'])/1000.0
                        hdr['SET-TEMP'] = float(f[0].header.comments['PARAM62'].split('(')[1].split('C')[0].strip())
                        hdr['CCD-TEMP'] = float(f[0].header['PARAM0'])
                        hdr['BACKTEMP'] = float(f[0].header['PARAM1'])
                        hdr['XBINNING'] = float(f[0].header['PARAM18'])
                        hdr['YBINNING'] = float(f[0].header['PARAM22'])
                        hdr['XORGSUBF'] = float(f[0].header['PARAM16'])
                        hdr['YORGSUBF'] = float(f[0].header['PARAM20'])
                        hdr['SHUTTER'] = f[0].header.comments['PARAM8'].split('(')[-1].split(")")[0].strip()
                        hdr['XIRQA'] = f[0].header.comments['PARAM9'].split('(')[-1].split(")")[0].strip()
                        hdr['COOLER'] = f[0].header.comments['PARAM10'].split('(')[-1].split(")")[0].strip()
                        hdr['CONCLEAR'] = f[0].header.comments['PARAM25'].split('(')[-1].split(")")[0].strip()
                        hdr['DSISAMP'] = f[0].header.comments['PARAM26'].split('(')[-1].split(")")[0].strip()
                        hdr['ANLGATT'] = f[0].header.comments['PARAM27'].split('(')[-1].split(")")[0].strip()
                        hdr['PORT1OFF'] = f[0].header['PARAM28']
                        hdr['PORT2OFF'] = f[0].header['PARAM29']
                        hdr['TDIDELAY'] = f[0].header['PARAM32']
                        hdr['CMDTRIG'] = f[0].header.comments['PARAM39'].split('(')[-1].split(")")[0].strip()
                        hdr['ADCOFF1'] = f[0].header['PARAM44']
                        hdr['ADCOFF2'] = f[0].header['PARAM45']
                        hdr['MODEL'] = f[0].header['PARAM48']
                        hdr['HWREV'] = f[0].header['PARAM50']
                        hdr['SERIALP'] = f[0].header.comments['PARAM51'].split('(')[-1].split(")")[0].strip()
                        hdr['SERIALSP'] = f[0].header.comments['PARAM52'].split('(')[-1].split(")")[0].strip()
                        hdr['SERIALS'] = f[0].header['PARAM53']
                        hdr['PARALP'] = f[0].header.comments['PARAM54'].split('(')[-1].split(")")[0].strip()
                        hdr['PARALSP'] = f[0].header.comments['PARAM55'].split('(')[-1].split(")")[0].strip()
                        hdr['PARALS'] = f[0].header['PARAM56']
                        hdr['PARDLY'] = f[0].header['PARAM57']
                        hdr['NPORTS'] = f[0].header.comments['PARAM58'].split('(')[-1].split(" ")[0].strip()
                        hdr['SHUTDLY'] = f[0].header['PARAM59']

                        # recast as 16 bit unsigned integer (2x smaller with no loss of information)
                        data = f[0].data.astype('uint16')
                        f.close()

                        # Write final image
                        pyfits.writeto(filename,data,hdr)
                        '''

                        return True
		except: return False
		
	def write_header(self,param):
		
		self.header_buffer = self.header_buffer + param
		return 'success'
		
	def write_header_done(self,param):

                ipdb.set_trace()

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
	
	def get_vacuum_pressure(self):
                specgauge = com.com('specgauge',self.night,configfile=self.base_directory + '/config/com.ini')
                return 'success ' + str(specgauge.send('RD'))

        def get_atmospheric_pressure(self):
                atmgauge = com.com('atmGauge',self.night,configfile=self.base_directory + '/config/com.ini')
                atmgauge.send('OPEN')
                pressure = atmgauge.send('R')
                atmgauge.send('CLOSE')
                return 'success ' + str(pressure)
                
		
if __name__ == '__main__':
	
	base_directory = 'C:\minerva-control'
	test_server = server('spectrograph.ini',base_directory)
	test_server.run_server()
	
	
	
	
	
