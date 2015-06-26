#Minerva system main routine
#create master control object and run one of the observing scripts
import sys
sys.dont_write_bytecode = True
from minerva_library import control

import ipdb, datetime, time

if __name__ == '__main__':

	base_directory = '/home/minerva/minerva_control'
	minerva = control.control('control.ini',base_directory)


	tel = 4
	minerva.telescopes[tel-1].home()
	minerva.telescopes[tel-1].home_rotator()
	minerva.telescopes[tel-1].initialize_autofocus()
	sys.exit()

	for telescope in minerva.telescopes:
		telescope.initialize()
	for imager in minerva.cameras:
		imager.cool()


	for i in range(0,4):
		minerva.endNight(i+1,email=False)

#	minerva.telescopes[1].initialize()
#	minerva.telescopes[1].park()
#	filename = '/Data/t2/n20150621/n20150621.T2.EPIC2015.V.0044.fits'
#	reference = minerva.guide(filename, None)
#	reference = minerva.guide(filename, reference)
#	ipdb.set_trace()

#	telescope_num = 3
#	minerva.prepNight(telescope_num,email=False)
#	filename = minerva.takeImage(1,'V','test',camera_num=telescope_num)



	

#	minerva.cameras[2].cool()

#	minerva.getPA('/Data/t' + str(telescope_num) + '/' + minerva.site.night + '/' + filename)
#	minerva.getPA('/Data/t2/n20150618/n20150618.T2.OB150941.ip.0083.fits')
#	minerva.getPA('/Data/t2/n20150618/n20150618.T2.OB150572.ip.0082.fits')
#	minerva.getPA('./n20150618.T2.OB150572.ip.0082.fits')

	sys.exit()

	ipdb.set_trace()
	
	
	#run observing script on all telescopes with their own schedule file
	minerva.observingScript_all()
	
	
	# minerva.telcom_enable()
	# minerva.telescope_mountGotoAltAz(30,90)
	
	
	# minerva.doBias(11,2)
	
	
	
	
