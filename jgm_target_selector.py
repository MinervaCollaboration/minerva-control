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
import scheduler
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

### Time zone here is UTC - so Arizona is 7 hours

# assume targetlist has the desired ordered dictionary format and only active targets
# for target in targetlist:
#     if target['ra'] >= mthop.sidereal_time() and target['ra'] <= mthop1.sidereal_time():
#         ranked_observables.append(target)
# ranked_observables = sorted(ranked_observables, key = lambda target: target['vmag']) # add the vmag key into sorted and rank accordingly

# print ranked_observables

ranked_observables2 = []
## with MINERVA scheduler code assuming I had all missing pieces of information
targets = targetlist.mkdict(name=None, bstar=False, includeInactive=False)
for target in targets: # automatically for active targets in active target list
    # initialize scheduler
    thesis_sched = scheduler.scheduler('scheduler.ini',base_directory='/home/minerva/minerva-control') 
    # add the times corresponding to Dec, Jan, Feb
    if thesis_sched.is_observable(target, timeof = datetime.datetime(2017,1,20,0,0,),max_exptime=86400):
        ranked_observables2.append(target['name'])

ranked_observables = thesis_sched.sort_target_list(key = 'vmag')

#print ranked_observables
print ranked_observables2

target_names = []
for target in targets:
    target_names.append(target['name'])

print target_names
'''
config directory = scheduler.ini
base directory - config directoryor level above it 

/home/minerva/minerva-control/config

'''










































