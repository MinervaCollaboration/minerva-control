class expmeter:

    def __init__(self, night, configfile='minerva_class_files/com.ini'):

        self.night = night

        #set appropriate parameter based on aqawan_num
        #create configuration file object 
        configObj = ConfigObj(configfile)
        
        try:
            config = configObj['expmeter']
        except:
            print('ERROR: expmeter was not found in the configuration file", configfile)
            return 
        
        logger_name = imagerconfig['Setup']['LOGNAME']
        log_file = 'logs/' + night + '/' + imagerconfig['Setup']['LOGFILE']
			
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

    def read(self):
