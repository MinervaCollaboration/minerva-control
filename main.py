#Minerva system main routine
#create master control object and run one of the observing scripts
import sys
sys.dont_write_bytecode = True
from minerva_library import control
from minerva_library import rv_control


if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'

	minerva = control.control('control.ini',base_directory)

	# if a file for kiwispec exists, use that. If not, observe with all four telescopes
	if os.path.exists(minerva.base_directory + '/schedule/' + minerva.site.night + '.kiwispec.txt'):
		rv_control.rv_observing_catch(minerva.logger)
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
