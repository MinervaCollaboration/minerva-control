#Minerva system main routine
#create master control object and run one of the observing scripts
import sys
sys.dont_write_bytecode = True
from minerva_library import control

import ipdb

if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
	minerva = control.control('control.ini',base_directory)

	if len(sys.argv) == 2:
		night = sys.argv[1]
	else: night=None

	for i in range(len(minerva.telescopes)):
		minerva.scheduleIsValid(i+1, night=night, email=False)

