import numpy as np
import win32com.client
from astropy.io import fits
import datetime, time
import ipdb

class ascomfw:

	def __init__(self, config, base='', driver=None):

                self.base_directory = base

                # if you don't know what your driver is called, use the ASCOM Chooser
                # this will give you a GUI to select it
		if driver==None:
                        x = win32com.client.Dispatch("ASCOM.Utilities.Chooser")
                        x.DeviceType = 'FilterWheel'
                        driver = x.Choose(None)
                        print("The driver is " + driver)

		# initialize the filter wheel
		self.fw = win32com.client.Dispatch(driver)

        def initialize(self):
                self.connect()
		self.npositions = len(self.fw.Names)

	def connect(self):
                self.fw.connected = True
                return self.fw.connected

	def move(self, position=None, filter_name=None):
		if filter_name != None:
			if filter_name not in self.fw.Names:
				self.logger.error("Requested filter does not exist")
				return False
			self.fw.Position = fw.Names.index(filter_name)+1
			return True

		if position != None:
			if position < 1 or position > self.npositions:
				self.logger.error("Requested position out of range")
				return False
			self.fw.Position = position
			return True

		self.logger.error("Must specify either position or filter_name")
		return False

	def move_and_wait(self,position=None,filter_name=None, timeout=10.0):

		if not self.move(position=position, filter_name=filter_name):
			self.logger.error("Move failed")
			return False

		t0 = datetime.datetime.utcnow()
		time.sleep(0.1)
		elapsed_time = (datetime.datetime.utcnow() - t0).total_seconds()
		while elapsed_time < timeout and self.fw.position == -1:
			time.sleep(0.1)
			elapsed_time = (datetime.datetime.utcnow() - t0).total_seconds()

		return in_position(position=position, filter_name=filter_name)


	def in_position(self,position=None,filter_name=None):
		if filter_name != None:
			if filter_name not in self.fw.Names:
				self.logger.error("Requested filter does not exist")
				return False
			return self.fw.Position == (fw.Names.index(filter_name)+1)

		if position != None:
			if position < 1 or position > self.npositions:
				self.logger.error("Requested position out of range")
				return False
			return self.fw.Position == position

		self.logger.error("Must specify either position or filter_name")
		return False


if __name__ == '__main__':

        config_file = ''
        base_directory = ''
        fw = ascomcam(config_file, base_directory, driver="ASCOM.Apogee.FilterWheel")
        ipdb.set_trace()

