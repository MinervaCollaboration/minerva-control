#Minerva system main routine
#create master control object and run one of the observing scripts
import sys
sys.dont_write_bytecode = True
from minerva_library import control

if __name__ == '__main__':

	base_directory = '/home/minerva/minerva-control'
	minerva = control.control('control.ini',base_directory)
	
	#run observing script on all telescopes with their own schedule file
#	minerva.observingScript_all()
	
	
	# minerva.telcom_enable()
	# minerva.telescope_mountGotoAltAz(30,90)
	
	
	# minerva.doBias(11,2)
	
	

	while True:
		print 'main test program'
		print ' a. observingScript_all'
		print ' 1. observingScript(1)'
		print ' 2. observingScript(2)'
		print ' 3. observingScript(3)'
		print ' 4. observingScript(4)'
		print ' d. domeControlThread()'
		print ' x. exit'
		print '----------------------------'
		choice = raw_input('choice:')
		
		if choice == 'a':
			minerva.observingScript_all()
		elif choice == '1':
			minerva.observingScript(1)
		elif choice == '2':
			minerva.observingScript(2)
		elif choice == '3':
			minerva.observingScript(3)
		elif choice == '4':
			minerva.observingScript(4)
		elif choice == 'd':
			minerva.domeControlThread()
		elif choice == 'x':
			sys.exit()
		else:
			print 'invalid choice'
		break
