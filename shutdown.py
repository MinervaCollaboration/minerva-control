import main
import logging, time

site, aqawan, telescope, imager = main.prepNight()


# setting up main logger
fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
datefmt = "%Y-%m-%dT%H:%M:%S"

#    logging.basicConfig(level=logging.DEBUG, format=fmt, datefmt=datefmt)
logger = logging.getLogger('main')
formatter = logging.Formatter(fmt,datefmt=datefmt)
formatter.converter = time.gmtime
        
fileHandler = logging.FileHandler('logs/' + site.night + '/main.log', mode='a')
fileHandler.setFormatter(formatter)

console = logging.StreamHandler()
console.setFormatter(formatter)
console.setLevel(logging.INFO)
        
logger.setLevel(logging.DEBUG)
logger.addHandler(fileHandler)
logger.addHandler(console)


imager.connect()
main.endNight(site, aqawan, telescope, imager)
