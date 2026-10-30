
# wrapper code to test DT scheduler
# NM
# 2020 Sept 20

import datetime
from DT_target_selection import choose_dt_target
from astropy.time import Time
import ipdb
import utils
base_directory = '/home/minerva/minerva-control/'
night = 'n20201020'
logger_name = 'dtscheduler.log'


today = datetime.datetime.utcnow()
night = 'n' + today.strftime('%Y%m%d')
logger = utils.setup_logger(base_directory,night,logger_name)


# choose the day to match timeof parameter in mainNew.py
timeof = datetime.datetime(2020,9,25)  # use in simulation
timeof = datetime.datetime.utcnow()   # matches call from mainNew.py

# call the function, store disctionary
remaining_time = 3600
target = choose_dt_target(timeof=timeof, remaining_time=remaining_time, logger=logger)

ipdb.set_trace()

#target = choose_dt_target(timeof)   # <-- how it will be called by mainNew.py


#----------------------------------------------------------------------------
# Some dates to use in testing:

# Sept 29 has 5 candidates, mix of full and partials
# Oct 7 has 4 candidates, all partials
# Nov 8: no candidates with fraction observable > 50 percent



