# -*- coding: utf-8 -*-
"""
Created on Fri Sep 16 14:53:03 2016

@author: jgarciamejia

Senior Thesis Code
Uses scheduler.py and targetlist.py to figure out best targets to observe on 
Jan 20, 2017 +/- 1 month. Criteria are: RA, Known planets, Brightness

"""
#import numpy as np
#import math
import targetlist
#import scheduler
import ephem 
import datetime

# targetlist contains active targets from the 
# MINERVA catalog, aka targets currently being observed by MINERVA


## without MINERVA code using simple criteria

ranked_observables = []
# Determine LST for Arizona from December 20 to February 20 using ephem - COULD DO BETTER WITH MORE RELIABLE INFO MAYBE
mthop = ephem.Observer()
mthop.lon = '-110:53:07'
mthop.lat = '31:41:18'
mthop.elevation = 2607
#mthop.date = '2017/1/20' # format of date incorrect 
mthop.date = datetime.datetime(2017,1,20)

mthop1 = ephem.Observer()
mthop1.lon = '-110:53:07'
mthop1.lat = '31:41:18'
mthop1.elevation = 2607
#mthop.date = '2017/1/20' # format of date incorrect 
mthop1.date = datetime.datetime(2017,1,20,4,0,0)

targetlist = targetlist.mkdict(name =None,bstar = False, includeInactive=False)

### Time zone here is UTC - so Arizona is 7 hours

# assume targetlist has the desired ordered dictionary format and only active targets
for target in targetlist: #mask soehow based on the previous
    if target['ra'] >= mthop.sidereal_time() and target['ra'] <= mthop1.sidereal_time():
        ranked_observables.append(target)
ranked_observables = sorted(ranked_observables, key = lambda target: target['vmag']) # add the vmag key into sorted and rank accordingly

print type(targetlist[0]['ra']), type(mthop.sidereal_time())
print ranked_observables
        
'''

ranked_observables2 = []
## with MINERVA scheduler code assuming I had all missing pieces of information

for target in targetlist: # automatically for active targets in active target list
    # initialize scheduler
    thesis_sched = scheduler(config_file,base_directory='.') 
    # add the times corresponding to Dec, Jan, Feb
    if scheduler.is_observable(target, timeof = ) or scheduler.is_observable(target, timeof = ) \
    or scheduler.is_observable(target, timeof = ):
        ranked_observables2.append(target)

ranked_observables = scheduler.sort_target_list(key = 'vmag')

print ranked_observables


//anaconda/lib/python2.7/site-packages/spyderlib/widgets/externalshell/start_ipython_kernel.py:8: DeprecationWarning: the ephem.Body attributes 'rise_time', 'rise_az', 'transit_time', 'transit_alt', 'set_time', 'set_az', 'circumpolar', and 'never_up' are deprecated; please convert your program to use the ephem.Observer functions next_rising(), previous_rising(), next_transit(), and so forth

  (see spyderlib/widgets/externalshell/pythonshell.py)"""


'''   
'''
config directory = scheduler.ini
base directory - config directoryor level above it 

/home/minerva/minerva-control/config

'''










































