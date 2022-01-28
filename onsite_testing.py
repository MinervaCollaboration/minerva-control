import ipdb, datetime, time, socket, os

import numpy as np

from minerva_library import control
from minerva_library.autofocus import autofocus
from minerva_library import measure_flexure as flex
from minerva_library import af_utils
from minerva_library import utils


if __name__ == '__main__':
    base_directory = '/home/minerva/minerva-control'
    if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
    minerva = control.control('control.ini', base_directory)

#    print('Check manually that all telescopes are set up correctly.')
#    ipdb.set_trace()

#   for tel in minerva.telescopes:
    for tel in [utils.getTelescope(minerva, 'T2')]:
        tel.logger.info('Guessing at best focus')
        status = tel.getStatus()
        m3port = status.m3.port
        tel.guessFocus(m3port)
        focus_guess = tel.focus[m3port]

        tel.logger.info('Moving to nominal best focus position for flexure testing.')
        if not tel.focuserMoveAndWait(focus_guess, m3port):
            tel.recoverFocuser(focus_guess, m3port)
            ipdb.set_trace()

        tel.logger.info('Testing one step of flexure-measuring routine on ' + tel.id)
        
        flex.flex_step(minerva, tel, 45)

#        print('Check files on the ' + tel.id + 'machine to make sure there are actual stars and source extractor is working correctly.')
#        ipdb.set_trace()

#        threads = []
#	for tel in minerva.telescopes:
#        for tel in [utils.getTelescope(minerva, 'T1')]:
#            thread = PropagatingThread(target = flex.diagnose_flexure,
#		 							args=(minerva, telescope))
 #           thread.name = telid + ' (onsite_testing->diagnose_flexure)'
 #           thread.start()
 #           threads.append(thread)

#	for thread in threads:
#            thread.join()

        alt, foc = flex.diagnose_flexure(minerva, minerva.telescopes[1])

	ipdb.set_trace()
