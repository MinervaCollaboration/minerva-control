import sys
import os
import socket
import errno
import logging
import time
import threading
import pdu
import pdu_thach
import telcom_client
import mail
import datetime
from configobj import ConfigObj
import ipdb
import subprocess
import cdk700
import fau
sys.dont_write_bytecode = True
import utils


class Dome:

	def __init__(self, config="ashdome_thach.ini", base='/home/thacher/minerva-control'):

		self.config_file = config
		self.base_directory = base
		self.id = "thacher"
		self.mailsent = False
		self.load_config()
                self.pdu = pdu_thach.pdu('pdu_dome1_thach.ini', base)

		# reset the night at 10 am local
		today = datetime.datetime.utcnow()
		if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                        today = today + datetime.timedelta(days=1)
		night = 'n' + today.strftime('%Y%m%d')

		self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)
                self.dome = None
                self.initialize()
                self.telcom = telcom_client.telcom_client(self.telcom_client_config,base)
                self.nserver_failed = 0

        def initialize(self):
            if not self.connect_server(): pass #self.recover() This is lower on the priority list at the moment.
            if not self.at_park():
                self.park()

        def load_config(self):
		try:
		    config = ConfigObj(self.base_directory+ '/config/' + self.config_file)
	       	    self.host = config['Setup']['IP']
		    self.port = int(config['Setup']['PORT'])
		    self.logger_name = config['Setup']['LOGNAME']
		    self.azoffset = int(config['Setup']['AZOFFSET'])
                    self.telcom_client_config = config['Setup']['TELCOM']
                    self.nserver_failed = 0
		except:
		    print('ERROR accessing configuration file: ' + self.config_file)
		    sys.exit()

                today = datetime.datetime.utcnow()
                if datetime.datetime.now().hour >= 10 and datetime.datetime.now().hour <= 16:
                    today = today + datetime.timedelta(days=1)
                self.night = 'n' + today.strftime('%Y%m%d')


        def connect_server(self):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((self.host,self.port))
            except socket.error as e:
                if e.errno == errno.ECONNREFUSED:
                    self.loggrecoverer.error('Connection failed (socket.error)')
                else: self.logger.exception('Connection failed')
                return False
            except:
				self.logger.exception('Connection failed')
				return False
            self.nserver_failed = 0
            return s

        def send(self,msg,timeout):
            self.logger.debug("Beginning serial communications with the dome server")
            if True:
                try:
                    s = self.connect_server()
                except:
                    self.logger.error("Connection lost")

                    if self.recover_server():
                        return self.send(msg,timeout)
                    return "fail"
                try:
                    s.settimeout(3)
                except:
                    self.logger.error("Failed to set timeout")
                    if self.recover_server():
                        return self.send(msg,timeout)
                    return "fail"
                try:
                    s.sendall(msg)
                except:
                    self.logger.error("Failed to send message (" + msg + ")")
                    if self.recover_server(): return self.send(msg,timeout)
                    return 'fail'

                try:
                    s.settimeout(timeout)
                    data = s.recv(1024)
                except:
                    self.logger.error("Connection timed out")
                    if self.recover_server(): return self.send(msg,timeout)
                    return 'fail'

                try:
                    command = msg.split()[0]
                    #data = repr(data).strip('"')
                    data_ret = data.split()[0]
                except:
                    self.logger.error("Error processing server response")
                    if self.recover_server(): return self.send(msg,timeout)
                    return 'fail'

                if data_ret == 'fail':
                    self.logger.error("Command failed("+command+')')
                    return 'fail'

                return data

		def recover(self):
			self.logger.warning("Dome failed, beginning recover")
			self.disconnect_dome()
			time.sleep(5)
			if self.connect_dome():
				self.logger.info("Dome recovered by reconnecting")
				return True

			filename = self.base_directory + '/minerva_library/dome.error'
			while not self.connect_dome():
				mail.send("Dome failed to connect",
					  "You must connect the dome and delete the file " +
					  filename + " to restart operations.",level="serious")
				fh = open(filename,'w')
				fh.close()
				while os.path.isfile(filename):
					time.sleep(1)
			return self.connect_dome()

        def  disconnect_dome(self):
            if self.send("disconnect_dome", 15) == 'success': return True
            else: return False

        def connect_dome(self):
            if self.send("connect_dome", 15) == 'success': return True
            else: return False

        def slave(self):
            if self.send("slave", 15) == 'success': return True
            else: return False

        def find_home(self):
            if self.send("find_home", 15) == 'success': return True
            else: return False

        def park(self):
            if self.send("park", 15) == 'success': return True
            else: return False

        def at_park(self):
            res = self.send("at_park", 15).split()
            if res[0] == 'success' and res[1] == 'true':
                return True
            else: return False

        def at_home(self):
            res = self.send("at_home",15).split()
            if res[0] == 'success' and res[1] == 'true':
                return True
            else:
                return False

        def get_azimuth(self):
            res = self.send("get_azimuth",15).split()
            if res[0]=='success':
                return float(res[1])
            else:
                return -9999

        def is_connected(self):
            res = self.send("is_connected",15).split()
            if res[0] == 'success' and res[1] == "true":
                return True
            else:
                return False

        def get_shutter_status(self):
            res = self.send("get_shutter_status", 15).split()
            if res[0] == 'success':
                return " ".join(res[1:])
            else: return False

        def is_slewing(self):
            res = self.send("is_slewing",15).split()
            if res[0] == 'success' and res[1] == 'trudomee':
                return True
            else:
                return False

        def is_slaved(self):
            res = self.send("is_slaved",15).split()
            if res[0] == 'success' and res[1] == 'true':
                return True
            else:
                return False

        def slew_to_az(self, az):
            if self.send("slew_to_az %d" %(az), 15) == 'success':
                return True
            return False

        def unslave(self):
            if self.send("unslave", 15) == "success":
                return True
            else:
                return False

        def open_shutter(self):
            if self.send("open_shutter", 15) == "success":
                return True
            else:
                return False

        def close_shutter(self):
            if self.send("close_shutter", 15) == "success":
                return True
            else:
                return False

        def disconnect_dome(self):
            if self.send("disconnect_dome", 15) == 'success':
                return True
            else:
                return False

        def recover_server(self):
            self.nserver_failed += 1

            # If it's failed more than 3 times, something is seriously wrong -- give up
            if self.nserver_failed > 3:
				if not self.mailsent: mail.send('dome server failed','',level='serious')
				self.mailsent = True
				sys.exit()

            self.logger.warning('Server failed, beginning recovery')

            if not self.kill_server():
                return Falsedome

            time.sleep(10)
            self.logger.warning("Restarting server")
            if not self.start_server():
                self.logger.error("Failed to start server")
                return False
            return True

        def send_to_computer(self, cmd):
			f = open(self.base_directory + '/credentials/authentication.txt','r')
			username = f.readline().strip()
			password = f.readline().strip()
			f.close()

			out = ''
			err = ''
			cmdstr = "cat </dev/null | winexe -U HOME/" + username + "%" + password + " //" + self.host + " '" + cmd + "'"
			os.system(cmdstr)
			self.logger.info('cmd=' + cmd + ', out=' + out + ', err=' + err)
			self.logger.info(cmdstr)

			if 'NT_STATUS_HOST_UNREACHABLE' in out:
					self.logger.error('host not reachdomeable')
					mail.send('dome is unreachable',
							  "Dear Benevolent Humans,\n\n"+
							  "I cannot reach dome. Can you please check the power and internet connection?\n\n" +
							  "Love,\nMINERVA",level="serious")
					return False
			elif 'NT_STATUS_LOGON_FAILURE' in out:
					self.logger.error('Invalid credentials')
					mail.send("Invalid credentials for dome",
							  "Dear Benevolent Humans,\n\n"+
							  "The credentials in " + self.base_directory +
							  '/credentials/authentication.txt (username=' + username +
							  ', password=' + password + ') appear to be outdated. Please fix it.\n\n' +
							  'Love,\nMINERVA',level="serious")
					return False
			elif 'ERROR: The process' in err:
					self.logger.info('Task already dead')
					return True
			return True


        def kill_server(self):
            return self.send_to_computer('schtasks /Run /TN "kill dome"')

        def kill_remote_task(self, taskname):
            return self.send_to_computer("taskkill /IM " + taskname + " /f")

        def start_server(self):
            ret_val = self.send_to_computer('schtasks /Run /TN "dome server"')
            time.sleep(30)
            return ret_val

        def isAligned(self, telescope_az):
                if self.is_slaved():
                        azimuth = self.get_azimuth()
			#if the azimuth of telescope and dome are say 359 and 1, the Distance
			#should be 2 not 358. these 2 if statements mend that.
                        if (azimuth-self.azoffset) < 0 and telescope_az > 300:
                                azimuth += 360
		        elif (azimuth+self.azoffset) > 360 and telescope_az < 100:
				azimuth -= 360
				#check to make sure telescope and dome slit are aligned, +/-
				#dome offset for tracking.
			if abs(azimuth-telescope_az) < self.azoffset:
				return True
		return False

        def isOpen(self):
                if self.get_shutter_status() == "open":
		        return True
		return False
