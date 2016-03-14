import datetime, time
import pdu
import convectron
import utils

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
        
        self.logger_name = config['Setup']['LOGNAME']
        self.logger = utils.setup_logger(self.base_directory,self.night,self.logger_name)

        self.specgauge = convectron('spectrograph')
        self.pumpgauge = convectron('pump')


    # vent the spectrograph to atmosphere (never?)
    def vent(self):

        timeout = 1200.0

        # close the vent valve
        self.benchpdu.off('ventvalve')
        
        # close the pump valve
        self.benchpdu.off('pumpvalve')

        # turn off the pump
        self.benchpdu.off('pump')

        if self.specgauge.pressure() < 500.0:
            mail.send("The spectrograph is pumped and attempting to vent!","Manual login required to continue",level='Debug')
            self.logger.error("The spectrograph is pumped and attempting to vent; manual login required to continue")

            # TODO: make hold file to restart thread
            ipdb.set_trace()            

        # open the vent valve
        self.benchpdu.on('ventvalve')

        t0 = datetime.datetime.utcnow()
        elapsedtime = 0.0
        while self.specgauge.pressure() < 500:
            elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds() 
            self.logger.info('Waiting for spectrograph to vent (Pressure = ' + str(specgauge.pressure()) + '; elapsed time = ' str(elapsedtime) + ' seconds)')


            # TODO: monitor pressure during venting and create smarter error condition
            if elapsedtime < timeout:
                time.sleep(5)
            else:
                self.logger.error("Error venting the spectrograph")
                return

        self.logger.info("Venting complete")

    # pump down the spectrograph (during the day)     
    def pump(self):

        timeout = 1200

        if self.specgauge.pressure() > 500:
            mail.send("The spectrograph is at atmosphere!","Manual login required to continue")
            self.logger.error("The spectrograph is at atmosphere! Manual login required to continue")

            # TODO: make hold file to restart thread
            ipdb.set_trace()

        # close the vent valve
        self.benchpdu.off('ventvalve')

        # close the pump valve
        self.benchpdu.off('pumpvalve')

        # turn on the pump
        self.benchpdu.on('pump')

        # wait until the pump gauge reads < 100 ubar
        t0 = datetime.datetime.utcnow()
        elapsedtime = 0.0
        while self.pumpgauge.pressure() > 0.1:
            elapsedtime = (datetime.datetime.utcnow() - t0).total_seconds() 
            self.logger.info('Waiting for tube to pump down (Pressure = ' + str(pumpgauge.pressure()) + '; elapsed time = ' str(elapsedtime) + ' seconds)')
            if elapsedtime < timeout:
                time.sleep(5)
            else:
                self.logger.error("Error pumping down the spectrograph")
                return          
                
        # open the pump valve
        self.benchpdu.on('pumpvalve')
        self.logger.info("Pumping down the spectrograph")

        # TODO: wait for pressure to go below some value??


    # close the valves, hold the pressure (during the night)
    def hold(self):

        # make sure the vent valve is closed
        self.benchpdu.off('ventvalve')

        # close the pump valve
        self.benchpdu.off('pumpvalve')

        # turn off the pump
        self.benchpdu.off('pump')

        
        
        
