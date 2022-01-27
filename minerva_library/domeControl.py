from filelock import FileLock
import control
import socket
import threading
import mail
import datetime, time
import sys, os
import utils
import argparse


# check weather condition; close if bad, open and send heartbeat if good; update dome status
def domeControl(minerva,dome,day=False):

    minerva.logger.info("Starting domeControl")
    lastnight = ''
    while True:
        t0 = datetime.datetime.utcnow()

        # roll over the logs to a new day
        thisnight = datetime.datetime.strftime(t0,'n%Y%m%d')
        if thisnight != lastnight:
            minerva.logger.info("Updating log path")
            minerva.update_logpaths(minerva.base_directory + '/log/' + thisnight)
            lastnight = thisnight

        openRequested = os.path.isfile(minerva.base_directory + '/minerva_library/' + dome.id + '.request.txt')
        day = os.path.isfile(minerva.base_directory + '/minerva_library/sunOverride.' + dome.id + '.txt')

        # if the weather says it's not ok to open
        timeoutOverride = os.path.exists(minerva.base_directory + '/minerva_library/timeoutOverride.' + dome.id + '.txt')

        minerva.logger.debug('Checking if ok to open for ' + dome.id)

        # this double call to oktoopen creates two identical messages in the log when it's not ok to open
        if not minerva.site.oktoopen(dome.id, domeopen=dome.isOpen()):
            if not minerva.site.oktoopen(dome.id, domeopen=dome.isOpen(),ignoreSun=True):
                # if it wouldn't be ok to open if we ignored the sun, reset the timeout
                minerva.logger.info('Weather not ok to open; resetting 30 minute timeout')
                minerva.site.lastClose = datetime.datetime.utcnow()
            # otherwise, just log it
            else: minerva.logger.info('Weather not ok to open')
            # regardless, make sure the dome is closed
            dome.close_both()
        elif (datetime.datetime.utcnow() - minerva.site.lastClose).total_seconds() < (30.0*60.0) and not timeoutOverride:
            minerva.logger.info('Conditions must be favorable for 30 minutes before opening; last bad weather at ' + str(minerva.site.lastClose))
            dome.close_both() # should already be closed, but for good measure...
        elif not openRequested:
            minerva.logger.info("Weather is ok, but domes are not requested to be open")
            dome.close_both()
        else:
            minerva.logger.debug('Weather is good; opening dome')

            reverse = (dome.id == 'aqawan1')

            if day and dome.id != 'astrohaven1':
                openthread = threading.Thread(target=dome.open_shutter,args=(1,))
            else:
                openthread = threading.Thread(target=dome.open_both,args=(reverse,))
            openthread.name = dome.id + '_OPEN'
            minerva.logger.debug('Starting thread to open ' + dome.id)
            openthread.start()
            
            # only send heartbeats when we want it open
            dome.heartbeat()

        if dome.id == 'aqawan1' or dome.id == 'aqawan2':
            status = dome.status()
        else:
            status = dome.status

        isOpen = (status['Shutter1'] == 'OPEN') and (status['Shutter2'] == 'OPEN')
        
        filename = minerva.base_directory + '/minerva_library/' + dome.id + '.stat'
        with FileLock(filename):
            with open(filename,'w') as fh:
                fh.write(str(datetime.datetime.utcnow()) + ' ' + str(isOpen))

        # check for E-stops (aqawans only)
        if dome.id == 'aqawan1' or dome.id == 'aqawan2':
            response = dome.send('CLEAR_FAULTS')
            if 'Estop' in response:
                if not dome.estopmailsent:
                    mail.send("Aqawan " + str(dome.id) + " Estop has been pressed!",dome.estopmail,level='serious')
                    dome.estopmailsent = True
            else:
                if dome.estopmailsent:
                    mail.send("Aqawan " + str(dome.id) + " Estop has been cleared.","",level='serious')
                dome.estopmailsent = False

        # ensure 4 hearbeats before timeout 
        sleeptime = max(14.0-(datetime.datetime.utcnow() - t0).total_seconds(),0)
        time.sleep(sleeptime)

    dome.close_both()

def domeControl_catch(minerva, dome, day=False):
    try:
        domeControl(minerva, dome, day=day)
    except Exception as e:
        dome.logger.exception('DomeControl thread died: ' + str(e.message) )
        body = "Dear benevolent humans,\n\n" + \
            "I have encountered an unhandled exception which has killed the "+\
            "dome control thread. The error message is:\n\n" + \
            str(e.message) + "\n\n" + \
            "Check " + minerva.logger_name + " for additional information. Please "+\
            "investigate, consider adding additional error handling, and "+\
            "restart 'domeControl.py'. The heartbeat *should* close the domes, "+\
            "but this is an unhandled problem and it may not close." +\
            "Please investigate immediately.\n\n" + \
            "Love,\n" + \
            "MINERVA"
        mail.send("DomeControl thread died",body,level='critical', directory=minerva.directory)
        sys.exit()


def domeControlThread(minerva,day=False):
    threads = []
    for dome in minerva.domes:
        minerva.logger.info("Starting dome control thread for " + str(dome.id))
        thread = threading.Thread(target = domeControl_catch,args=(minerva,dome,)) 
        thread.name = dome.id
        threads.append(thread)

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()        

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Observe with MINERVA')
    parser.add_argument('--red'  , dest='red'  , action='store_true', default=False, help='run with MINERVA red configuration')
    parser.add_argument('--south', dest='south', action='store_true', default=False, help='run with MINERVA Australis configuration')
    opt = parser.parse_args()

    # python bug work around -- strptime not thread safe. Must call this once before starting threads                              
    junk = datetime.datetime.strptime('2000-01-01 00:00:00','%Y-%m-%d %H:%M:%S')

    base_directory = '/home/minerva/minerva-control'
    if socket.gethostname() == 'Kiwispec-PC': base_directory = 'C:/minerva-control'
    minerva = control.control('control.ini',base_directory,red=opt.red,south=opt.south)
    domeControlThread(minerva)
