import socket
import logging
import threading
from configobj import ConfigObj
import sys, ipdb
import com
import os
import time
import glob
import datetime
import pyfits
import shutil
import json
import collections

# minerva library dependency
import spectrograph_modules
sys.dont_write_bytecode = True

class server:

	#initialize class
	def __init__(self,name,base):
		self.name = name
		self.base_directory = base
		self.data_path_base = "C:\minerva\data"
                self.load_config()

		# reset the night at 10 am local                                                                                                 
		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
		self.night = 'n' + today.strftime('%Y%m%d')

                self.setup_logger()
                self.set_data_path()
#                self.file_name = ''                

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
		
	#create logger object and link to log file
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

	def set_data_path(self,night='dump'):
		self.data_path = self.data_path_base + '\\' + self.night
		if not os.path.exists(self.data_path):
			os.makedirs(self.data_path)
		return 'success'        

#==================server functions===================#
#used to process communication between camera client and server==#

	#process received command from client program, and send response to given socket object
	def process_command(self, command, conn):
		command = command.strip("'")
		tokens = command.split(None,1)
		if len(tokens) != 2:
			response = 'fail'
		elif tokens[0] == 'cell_heater_on':
                        response = self.cell_heater_on()
                elif tokens[0] == 'cell_heater_off':
                        response = self.cell_heater_off()
                elif tokens[0] == 'cell_heater_temp':
                        response = self.cell_heater_temp()
                elif tokens[0] == 'cell_heater_set_temp':
                        response = self.cell_heater_set_temp()
                elif tokens[0] == 'cell_heater_get_set_temp':
                        response = self.cell_heater_get_set_temp()                        
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
		elif tokens[0] == 'save_image':
			response = self.save_image()
		elif tokens[0] == 'set_binning':
			response = self.set_binning(tokens[1])
		elif tokens[0] == 'set_file_name':
			response = self.set_file_name(tokens[1])
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

        def set_file_name(self,param):
                if len(param.split()) != 1:
			self.logger.error('parameter mismatch')
			return 'fail'
		self.logger.info('setting name to:' + param)
		self.file_name = self.data_path + '\\' + param                
                return 'success'
		
	def save_image(self):


		self.logger.info('saving image to:' + self.file_name)

                try:
                        shutil.move("C:/IMAGES/I",self.file_name)
                        return 'success'
		except: return 'fail'

        def get_index(self,param):
                files = glob.glob(self.data_path + "/*.fits*")
                return 'success ' + str(len(files)+1)
		
	def write_header(self,param):		
		self.header_buffer = self.header_buffer + param
		return 'success'
		
	def write_header_done(self,param):

		try: 
			self.logger.info("Writing header for " + self.file_name)
		except: 
			self.logger.error("self.file_name not defined; saving failed earlier")
			self.logger.exception("self.file_name not defined; saving failed earlier")
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

                        f[0].header['SIMPLE'] = True
                        f[0].header['EXPTIME'] = float(f[0].header['PARAM24'])/1000.0
                        f[0].header['SET-TEMP'] = float(f[0].header.comments['PARAM62'].split('(')[1].split('C')[0].strip())
                        f[0].header['CCD-TEMP'] = float(f[0].header['PARAM0'])
                        f[0].header['BACKTEMP'] = float(f[0].header['PARAM1'])
                        f[0].header['XBINNING'] = float(f[0].header['PARAM18'])
                        f[0].header['YBINNING'] = float(f[0].header['PARAM22'])
                        f[0].header['XORGSUBF'] = float(f[0].header['PARAM16'])
                        f[0].header['YORGSUBF'] = float(f[0].header['PARAM20'])
                        f[0].header['SHUTTER'] = f[0].header.comments['PARAM8'].split('(')[-1].split(")")[0].strip()
                        f[0].header['XIRQA'] = f[0].header.comments['PARAM9'].split('(')[-1].split(")")[0].strip()
                        f[0].header['COOLER'] = f[0].header.comments['PARAM10'].split('(')[-1].split(")")[0].strip()
                        f[0].header['CONCLEAR'] = f[0].header.comments['PARAM25'].split('(')[-1].split(")")[0].strip()
                        f[0].header['DSISAMP'] = f[0].header.comments['PARAM26'].split('(')[-1].split(")")[0].strip()
                        f[0].header['ANLGATT'] = f[0].header.comments['PARAM27'].split('(')[-1].split(")")[0].strip()
                        f[0].header['PORT1OFF'] = f[0].header['PARAM28']
                        f[0].header['PORT2OFF'] = f[0].header['PARAM29']
                        f[0].header['TDIDELAY'] = f[0].header['PARAM32']
                        f[0].header['CMDTRIG'] = f[0].header.comments['PARAM39'].split('(')[-1].split(")")[0].strip()
                        f[0].header['ADCOFF1'] = f[0].header['PARAM44']
                        f[0].header['ADCOFF2'] = f[0].header['PARAM45']
                        f[0].header['MODEL'] = f[0].header['PARAM48']
                        f[0].header['HWREV'] = f[0].header['PARAM50']
                        f[0].header['SERIALP'] = f[0].header.comments['PARAM51'].split('(')[-1].split(")")[0].strip()
                        f[0].header['SERIALSP'] = f[0].header.comments['PARAM52'].split('(')[-1].split(")")[0].strip()
                        f[0].header['SERIALS'] = f[0].header['PARAM53']
                        f[0].header['PARALP'] = f[0].header.comments['PARAM54'].split('(')[-1].split(")")[0].strip()
                        f[0].header['PARALSP'] = f[0].header.comments['PARAM55'].split('(')[-1].split(")")[0].strip()
                        f[0].header['PARALS'] = f[0].header['PARAM56']
                        f[0].header['PARDLY'] = f[0].header['PARAM57']
                        f[0].header['NPORTS'] = f[0].header.comments['PARAM58'].split('(')[-1].split(" ")[0].strip()
                        f[0].header['SHUTDLY'] = f[0].header['PARAM59']

                        del f[0].header['N_PARAM']
                        del f[0].header['DATE']
                        del f[0].header['TIME']
                        for i in range(80): del f[0].header['PARAM' + str(i)]

                        # recast as 16 bit unsigned integer (2x smaller with no loss of information)
                        #data = f[0].data.astype('uint16')
                        #f.close()

                        # Write final image
                        #pyfits.writeto(filename,data,hdr)
                        
			f.flush()
			f.close()
		except:
			return 'fail'
		return 'success'

        # all cell heater functions are untested
        def cell_heater_status(self):
                cellheater = com.com('I2Heater',self.night,configfile=self.base_directory + '/config/com.ini')
                print cellheater.send("")
                statusstr = cellheater.send("stat?")

                '''
                Bit 0 0 = Disabled, 1 = Enabled
                Bit 1 0 = Normal Mode, 1 = Cycle Mode
                Bit 2 0 = TH10K, 1 = PTC100 (sensor select bit one)
                Bit 3 0 = See Bit2, 1 = PTC1000 (sensor select bit two)
                Bit 4 0 = See Bit5, 1 = degrees C (unit select bit one)
                Bit 5 0 = Degrees K, 1 = Degrees F (unit select bit two)
                Bit 6 0 = No Sensor Alarm, 1 = Sensor Alarm
                Bit 7 0 = Cycle Not Paused, 1 = Cycle Paused
                '''
                
                unit = "C"

                status = {
                        "enabled": True,
                        "cyclemode": True,
                        "PTC100": True,
                        "PTC1000": True,
                        "Unit" : unit,
                        "Alarm": True,
                        "Paused" : True,
                }
                print statusstr
                ipdb.set_trace()

        def cell_heater_on(self):
                status = self.cell_heater_status()
                if not status['enabled']:
                        self.logger.info("Cell heater off; turning on")
                        cellheater = com.com('I2Heater',self.night,configfile=self.base_directory + '/config/com.ini')
                        cellheater.send("ens")

                self.logger.info("Cell heater already on")
                return 'success'
                
        def cell_heater_off(self):
                status = self.cell_heater_status()
                if status['enabled']:
                        self.logger.info("Cell heater on; turning off")
                        cellheater = com.com('I2Heater',self.night,configfile=self.base_directory + '/config/com.ini')
                        cellheater.send("ens")

                self.logger.info("Cell heater already off")
                return 'success'
                
        def cell_heater_temp(self):
                cellheater = com.com('I2Heater',self.night,configfile=self.base_directory + '/config/com.ini')
                return "success -999.0"
                return "success " + str(cellheater.send("tact?"))
                
        def cell_heater_set_temp(self, temp):
                cellheater = com.com('I2Heater',self.night,configfile=self.base_directory + '/config/com.ini')
                return "success" + str(cellheater.send("tset=" + str(temp)))
                
        def cell_heater_get_set_temp(self):
                cellheater = com.com('I2Heater',self.night,configfile=self.base_directory + '/config/com.ini')
#                print cellheater.send("tset?")
#                ipdb.set_trace()
                return "success 55.0"
                return "success " + str(cellheater.send("tset?"))

        def move_i2(self,position='science'):
                i2stage = com.com('iodineStage',self.night,configfile=self.base_directory + '/config/com.ini')

                positions = {
                        'science' : 147,
                        'flat'  : 0,
                        'template' : 0,
                        }
                if position not in positions.keys(): return "fail"
                print i2stage.send('SetAbsMovePos=' + str(positions[position]))
                print i2stage.send('GetAbsMovePos_AbsPos')
                ipdb.set_trace()
	
	def get_vacuum_pressure(self):
                specgauge = com.com('specgauge',self.night,configfile=self.base_directory + '/config/com.ini')
                response = str(specgauge.send('RD'))
                if response == '': return 'fail'
                return 'success ' + response

        def get_atmospheric_pressure(self):
                atmgauge = com.com('atmGauge',self.night,configfile=self.base_directory + '/config/com.ini')
                atmgauge.send('OPEN')
                pressure = atmgauge.send('R')
                atmgauge.send('CLOSE')
                ipdb.set_trace()
                return 'success ' + str(pressure)
                
		
if __name__ == '__main__':
	
	base_directory = 'C:\minerva-control'
	test_server = server('spectrograph.ini',base_directory)
#	test_server.move_i2(position='science')
#        test_server.cell_heater_get_set_temp()
	test_server.run_server()
	
	
	
	
	
