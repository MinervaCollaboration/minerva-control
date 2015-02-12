class guider:
    
    def __init__(self,guider_name, configfile=''):

    self.name = guider_name

    #set appropriate parameter based on aqawan_num
    #create configuration file object 
    configObj = ConfigObj(configfile)
    
    try:
        guiderconfig = configObj[self.name]
    except:
        print('ERROR accessing ', self.name, ".", 
            self.name, " was not found in the configuration file", configfile)
        return 

    self.platescale = float(guiderconfig['Setup']['PLATESCALE'])
    self.filters = guiderconfig['FILTERS']
    self.setTemp = float(guiderconfig['Setup']['SETTEMP'])
    self.maxcool = float(guiderconfig['Setup']['MAXCOOLING'])
    self.maxdiff = float(guiderconfig['Setup']['MAXTEMPERROR'])
    self.xbin = int(guiderconfig['Setup']['XBIN'])
    self.ybin = int(guiderconfig['Setup']['YBIN'])
    self.x1 = int(guiderconfig['Setup']['X1'])
    self.x2 = int(guiderconfig['Setup']['X2'])
    self.y1 = int(guiderconfig['Setup']['Y1'])
    self.y2 = int(guiderconfig['Setup']['Y2'])
    self.xcenter = int(guiderconfig['Setup']['XCENTER'])
    self.ycenter = int(guiderconfig['Setup']['YCENTER'])
    self.pointingModel = guiderconfig['Setup']['POINTINGMODEL']
    self.port = int(guiderconfig['Setup']['PORT'])
    
    logger_name = guiderconfig['Setup']['LOGNAME']
    log_file = 'logs/' + guiderconfig['Setup']['LOGFILE']
                    
    # setting up logger
    self.logger = logging.getLogger(logger_name)
    formatter = logging.Formatter(fmt="%(asctime)s [%(filename)s:%(lineno)s - %(funcName)20s()] %(levelname)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    fileHandler = logging.FileHandler(log_file, mode='w')
    fileHandler.setFormatter(formatter)
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)

    self.logger.setLevel(logging.DEBUG)
    self.logger.addHandler(fileHandler)
    self.logger.addHandler(streamHandler)

    self.cam = Dispatch("MaxIm.CCDCamera")

    def removebadpix(self, data, mask):
        medianed_image = median_filter(data, size=2)
        data[np.where(mask>0)] = medianed_image[np.where(mask>0)]
        return data
