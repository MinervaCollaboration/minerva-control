import datetime, time
import dynapower
import convectron

class vacuum:

    def __init__(self, night, configfile=''):
        
        #set appropriate parameter based on aqawan_num
        #create configuration file object 
        configObj = ConfigObj(configfile)
        
        try:
            config = configObj[self.num]
        except:
            print('ERROR accessing ', self.num, ".", 
                self.num, " was not found in the configuration file", configfile)
            return 

        logger_name = config['Setup']['LOGNAME']
        log_file = 'logs/' + night + '/' + config['Setup']['LOGFILE']
			
	# setting up imager logger
        fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
        datefmt = "%Y-%m-%dT%H:%M:%S"

        self.logger = logging.getLogger(logger_name)
        formatter = logging.Formatter(fmt,datefmt=datefmt)
        formatter.converter = time.gmtime
        
        fileHandler = logging.FileHandler(log_file, mode='a')
        fileHandler.setFormatter(formatter)

        console = logging.StreamHandler()
        console.setFormatter(formatter)
        console.setLevel(logging.INFO)
        
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(fileHandler)
        self.logger.addHandler(console)

        self.specgauge = convectron('spectrograph')
        self.pumpgauge = convectron('pump')


    # vent the spectrograph to atmosphere (never?)
    def vent(self):
        # close the pump valve
        dynapower.off('pumpvalve')

        # turn off the pump
        dynapower.off('pump')

        if self.specgauge.pressure() < 500:
            mail.send("The spectrograph is pumped and attempting to vent!","Manual login required to continue")
            self.logger.error("The spectrograph is pumped and attempting to vent; manual login required to continue"")
            ipdb.set_trace()            

        # open the vent valve
        dynapower.on('ventvalve')

        t0 = datetime.datetime.utcnow()
        elapsedtime = 0.0
        while self.specgauge.pressure() < 500:
            elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds() 
            self.logger.info('Waiting for spectrograph to vent (Pressure = ' + str(specgauge.pressure()) + '; elapsed time = ' str(elapsedtime) + ' seconds)')
            if elapsedtime < timeout:
                time.sleep(5)
            else:
                self.logger.error("Error venting the spectrograph")
                return

        self.logger.info("Venting complete")

    # pump down the spectrograph (during the day)     
    def pump(self):

        timeout = 300

        # close the pump valve
        dynapower.off('pumpvalve')

        # turn on the pump
        dynapower.on('pump')

        if self.specgauge.pressure() > 500:
            mail.send("The spectrograph is at atmosphere!","Manual login required to continue")
            self.logger.error("The spectrograph is at atmosphere! Manual login required to continue")
            ipdb.set_trace()

        # wait until the guage reads < 100 ubar
        t0 = datetime.datetime.utcnow()
        elapsedtime = 0.0
        while self.pumpgauge.pressure() > 100.0:
            elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds() 
            self.logger.info('Waiting for tube to pump down (Pressure = ' + str(pumpgauge.pressure()) + '; elapsed time = ' str(elapsedtime) + ' seconds)')
            if elapsedtime < timeout:
                time.sleep(5)
            else:
                self.logger.error("Error pumping down the spectrograph")
                return          
                
        # open the pump valve
        dynapower.on('pumpvalve')

        

    # close the valves, hold the pressure (during the night)
    def hold(self):

        # make sure the vent valve is closed
        dynapower.off('ventvalve')

        # close the pump valve
        dynapower.off('pumpvalve')

        # turn off the pump
        dynapower.off('pump')

        
        
        
