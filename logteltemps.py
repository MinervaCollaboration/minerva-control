import matplotlib
#matplotlib.use('Agg')
import sys
sys.dont_write_bytecode = True
from minerva_library import control
import ipdb, datetime, time, socket
#from si.client import SIClient
#from si.imager import Imager
import threading
import math
import numpy as np
from minerva_library import rv_control
from minerva_library import newauto
from minerva_library import utils
import copy

def cleanUpNight(minerva):
	minerva.endNight(num=1)
	minerva.endNight(num=2)
	minerva.endNight(num=3)
	minerva.endNight(num=4)

if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
	if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
	minerva = control.control('control.ini',base_directory)

	while True:
          t0 = datetime.datetime.utcnow()

	  weather = -1
	  while weather == -1:
            minerva.site.getWeather()
	    weather = copy.deepcopy(minerva.site.weather)

          for tel in minerva.telescopes:

              status = tel.getStatus()
	      try: m1temp = float(status.temperature.primary)
	      except: m1temp = -99.0
	      try: m2temp = float(status.temperature.secondary)
	      except: m2temp = -99.0
	      try: m3temp = float(status.temperature.m3)
	      except: m3temp = -99.0
	      try: tback = float(status.temperature.backplate)
	      except: tback = -99.0
	      try: tamb = float(status.temperature.ambient)
	      except: tamb = -99.0
	      try: fanstat = status.fans.on
	      except: fanstat = 'UNKNOWN'

	      print m1temp, m2temp, m3temp, tback, tamb, fanstat, float(minerva.site.weather['outsideTemp']), minerva.base_directory + '/log/' + minerva.night + '/' + tel.id + '.temp.log'


	      dome = utils.getDome(minerva,tel.id)
	      domeStatus = dome.status()


	      f = open(minerva.base_directory + '/log/' + minerva.night + '/' + tel.id + '.temp.log',"a+")
	      f.write("%s %.1f %.1f %.1f %.1f %.1f %s %s %.1f %.1f %.1f %.1f %s %s %.1f %.1f %.1f \n" %
		      (datetime.datetime.utcnow(), \
		      m1temp, m2temp, m3temp, tback, tamb, fanstat, \
		      dome.isOpen(), float(domeStatus['EnclTemp']), float(domeStatus['EnclIntakeTemp']), \
		      float(domeStatus['EnclExhaustTemp']), \
		      float(domeStatus['PanelExhaustTemp']),domeStatus['WallFanOpMode'],\
		      domeStatus['OTAblowerOpMode'],float(domeStatus['PanelFanTach']),float(domeStatus['PoleFanExhaustTach']),\
		      float(minerva.site.weather['outsideTemp'])))
	      f.close()

	  timetosleep = max(0.0, 60.0 - (datetime.datetime.utcnow()-t0).total_seconds())
	  time.sleep(timetosleep)
