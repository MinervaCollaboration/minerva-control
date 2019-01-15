from configobj import ConfigObj
from win32com.client import Dispatch
import os,sys,glob, socket, logging, datetime, ipdb, time, json, threading, pyfits, subprocess, collections
import utils

class server(object):

    def __init__(self, config, base=''):
        self.config_file = config
        self.base_directory = base
        self.load_config()

        today = datetime.datetime.utcnow()
        if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
            today = today + datetime.timedelta(days=1)
        self.night = 'n' + today.strftime('%Y%m%d')

        self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)

        self.shutterStates = {0:'open', 1:'closed', 2:'opening', 3:'closing', 4:'error'}
        self.dome = None
        self.tel = None

        self.connect_dome()

    def load_config(self):
		try:
			config = ConfigObj(self.base_directory+ '/config/' + self.config_file)
			self.host = config['HOST']
			self.port = int(config['PORT'])
			self.logger_name = config['LOGNAME']
		except:
			print('ERROR accessing configuration file: ' + self.config_file)
			sys.exit()
    def connect_dome(self):
         try:
             # Connect to an instance of ASCOM's dome control.
             # (This launches the control panel if needed)
             if self.dome == None:
                 self.dome = Dispatch('ASCOMDome.Dome')
             if self.tel == None:
                 self.tel = Dispatch('ASCOM.PWI_Tele_20.Telescope')

			# Connect to the dome
             self.logger.info('Connecting to dome')
             self.dome.Connected = True
             self.logger.info('Connecting to telescope')
             self.tel.Connected = True
             return 'success'
         except:
             self.logger.exception('Failed to connect to the camera')
             return 'fail'

    def slave(self):
        try:
            self.logger.info('Slaving dome to telescope')
            self.dome.Slaved = True
            return 'success'
        except:
            self.logger.info('Slaving failed')
            return 'fail'

    def find_home(self):
        try:
            self.logger.info('Finding dome home')
            self.dome.FindHome()
            return 'success'
        except:
            self.logger.info('Finding home failed')
            return 'fail'

    #TODO: does this need to have a sleep in it?
    def park(self):
        try:
            self.logger.info('Parking dome')
            self.dome.Park()
            return 'success'
        except:
            self.logger.info('Parking failed')
            return 'fail'

    def at_park(self):
        try:
            if self.dome.AtPark:
                return 'success true'
            else:
                return 'success false'
        except:
            return 'fail'

    def at_home(self):
        try:
            if self.dome.AtHome:
                return 'success true'
            else:
                return 'success false'
        except:
            return 'fail'

    def get_azimuth(self):
        try:
            return 'success %d' %(self.dome.Azimuth)
        except:
            return 'fail'

    def is_connected(self):
        try:
            if self.dome.Connected:
                return 'success true'
            else:
                return 'success false'
        except:
            return 'fail'

    def get_shutter_status(self):
        try:
            return 'success '+ self.shutterStates[self.dome.ShutterStatus]
        except:
            return 'fail'

    def is_slewing(self):
        try:
            if self.dome.Slewing:
                return 'success true'
            else:
                return 'success false'
        except:
            return 'fail'

    def is_slaved(self):
        try:
            if self.dome.Slaved:
                return 'success true'
            else:
                return 'success false'
        except:
            return 'fail'

    def slew_to_az(self, az):
        try:
            self.logger.info('Slewing dome to azimuth %.6f' %az)
            self.dome.SlewToAzimuth(az)
            return 'success'
        except:
            self.logger.info('Slewing dome to azimuth %.6f failed' %az)
            return 'fail'

    def unslave(self):
        try:
            self.logger.info('Slaving dome to telescope')
            self.dome.Slaved = False
            return 'success'
        except:
            self.logger.info('Slaving failed')
            return 'fail'

    def open_shutter(self):
        try:
            self.logger.info('opening shutter')
            self.dome.OpenShutter()
            return 'success'
        except:
            self.logger.info('open failed')
            return 'fail'

    def close_shutter(self):
        try:
            self.logger.info('closing shutter')
            self.dome.CloseShutter()
            return 'success'
        except:
            self.logger.info('close failed')
            return 'fail'

    def disconnect_dome(self):
         try:
             self.close_shutter()
             self.park()
             self.logger.info('disconnecting dome')
             self.dome.Connected = False
             return 'success'
         except:
             self.logger.exception('disconnect failed')
             return 'fail'

    def process_command(self, command, conn):
        tokens = command.split(None, 1)
        if len(command) < 100:
		self.logger.info('command received: ' + command)
        if tokens[0] == 'disconnect_dome':
            response = self.disconnect_dome()
        elif tokens[0] == 'connect_dome':
            response = self.connect_dome()
        elif tokens[0] == 'slave':
            response = self.slave()
        elif tokens[0] == 'find_home':
            response = self.find_home()
        elif tokens[0] == 'park':
            response = self.park()
        elif tokens[0] == 'at_park':
            response = self.at_park()
        elif tokens[0] == 'at_home':
            response = self.at_home()
        elif tokens[0] == 'get_azimuth':
            response = self.get_azimuth()
        elif tokens[0] == 'is_connected':
            response = self.is_connected()
        elif tokens[0] == 'get_shutter_status':
            response = self.get_shutter_status()
        elif tokens[0] == 'is_slewing':
            response = self.is_slewing()
        elif tokens[0] == 'is_slaved':
            response = self.is_slaved()
        elif tokens[0] == 'slew_to_az':
            response = self.slew_to_az(float(tokens[1]))
        elif tokens[0] == 'unslave':
            response = self.unslave()
        elif tokens[0] == 'open_shutter':
            response = self.open_shutter()
        elif tokens[0] == 'close_shutter':
            response = self.close_shutter()
        elif tokens[0] == 'disconnect_dome':
            response = self.disconnect_dome()
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
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #; s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((self.host, self.port))
        except:
			self.logger.exception('Error connecting to dome server')
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
    config_file = 'dome_server_thach.ini'
    base_directory = 'C:\minerva-control'
    test_server = server(config_file, base_directory)
    test_server.run_server()
