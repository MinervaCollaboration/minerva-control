#Minerva system main routine
#create master control object and run one of the observing scripts
import matplotlib
matplotlib.use('Agg')
import sys, os
sys.dont_write_bytecode = True
from minerva_library import control
from minerva_library import rv_control
import datetime
import argparse, ipdb
from minerva_library import utils

if __name__ == '__main__':

	parser = argparse.ArgumentParser(description='Observe with MINERVA')
	parser.add_argument('--red'  , dest='red'  , action='store_true', default=False, help='run with MINERVA red configuration')
	parser.add_argument('--south', dest='south', action='store_true', default=False, help='run with MINERVA Australis configuration')
	opt = parser.parse_args()

	base_directory = '/home/minerva/minerva-control'

	utils.killmain(red=opt.red,south=opt.south)
	minerva = control.control('control.ini',base_directory,red=opt.red,south=opt.south)

	for dome in minerva.domes:
		sunfile = 'minerva_library/sunOverride.' + dome.id + '.request.txt'
		if os.path.exists(sunfile): os.remove(sunfile)
		# make sure the domes are closed
	        # but not if it starts in the middle of the night #
		if datetime.datetime.utcnow().hour < 2 or datetime.datetime.utcnow().hour > 20:
			requestfile = 'minerva_library/' + dome.id + '.request.txt'
			if os.path.exists(requestfile): os.remove(requestfile)

	# if a file for kiwispec exists, use that. If not, observe with all four telescopes
	if os.path.exists(minerva.base_directory + '/schedule/' + minerva.site.night + '.kiwispec.txt'):
		rv_control.rv_observing_catch(minerva)
	else:
		#run observing script on all telescopes with their own schedule file
		minerva.observingScript_all()
	sys.exit()
	
	# minerva.telcom_enable()
	# minerva.telescope_mountGotoAltAz(30,90)
	
	
	# minerva.doBias(11,2)
	
	

	while True:
		print 'main test program'
		print ' a. observingScript_all'
		print ' b. observingScript(1)'
		print ' c. observingScript(2)'
		print ' d. observingScript(3)'
		print ' e. observingScript(4)'
		print '----------------------------'
		choice = raw_input('choice:')
		
		if choice == 'a':
			minerva.observingScript_all()
		elif choice == 'b':
			minerva.observingScript(1)
		elif choice == 'c':
			minerva.observingScript(2)
		elif choice == 'd':
			minerva.observingScript(3)
		elif choice == 'e':
			minerva.observingScript(4)
		else:
			print 'invalid choice'
