#S was going to make targets their own classes, but might as well preserve 
#S dicts. we can just have the scheduler perform functions on them and update
#S values. 
"""
The scheduler class, which performs all checks on observability of targets,
calculates weights, and some ephem on sun, moon. Will contain some other 
utility functions.
"""

import numpy as np
import math
import os
import ephem
import sys
#import simbad_reader
#import targetlist
import ephem
import ipdb
#import env
import datetime
import time
import subprocess
import targetlist
from configobj import ConfigObj
import utils, env

###
# SCHEDULER
###

class scheduler:
    def __init__(self,config_file,base_directory='.'):
        #S want to get the site from the control class, makes easy computing
        #S LST and such
        self.base_directory = base_directory
        self.config_file = config_file
        self.dt_fmt = '%Y%m%dT%H:%M:%S'
        # load the config file
        self.load_config()
        # make the observer which will be used in calculations and what not
        self.obs = ephem.Observer()
        self.obs.lat = ephem.degrees(str(self.latitude)) # N
        self.obs.lon = ephem.degrees(str(self.longitude)) # E
        self.obs.horizon = ephem.degrees(str(self.sun_horizon))
        self.obs.elevation = self.elevation # meters    
        # an ephem sun and moon object for tracking the sun
        self.sun = ephem.Sun()
        self.sun.compute(self.obs)
        self.moon = ephem.Moon()
        self.moon.compute(self.obs)
        self.obspath = self.base_directory + 'schedule/rvobshistory/'

        # TODO: incorporate this into the observing script and initialize to False
        self.bstarobserved = True
        
        # get the target list
        self.update_list()

        self.make_fixedBodies()

        self.site = env.site('site_mtHopkins.ini',self.base_directory)

    def load_config(self):
        try:
#            ipdb.set_trace()
            config = ConfigObj(self.base_directory+'/config/'+self.config_file)
            self.latitude = config['Setup']['LATITUDE']
            self.longitude = config['Setup']['LONGITUDE']
            self.elevation = float(config['Setup']['ELEVATION'])
            self.sitename = config['Setup']['SITENAME']
            self.sun_horizon = float(config['Setup']['HORIZON'])
            self.target_min_horizon = float(config['Setup']['MINALT'])
            self.target_max_horizon = float(config['Setup']['MAXALT'])
            self.targets_file = config['Setup']['TARGETSFILE']
            self.min_moon_sep = float(config['Setup']['MINMOONSEP'])
            # used for minerva logging
#            self.logger_name = config['Setup']['LOGNAME']

        except:
            print('ERROR accessing configuration file: ' + self.config_file)
            sys.exit()

    def sort_target_list(self,key='weight'):
        #S sort the target_list list of target dictionaries by the given key
        try:
            self.target_list = sorted(self.target_list, key=lambda x:-x[key])
            return True
        except:
            print 'Something went wrong when sorting with ' + key
            return False

    def choose_target(self,key='weight',remaining_time=86400.0, logger=None, timeof=None, cadence=True):
        #S we assume you need to update the weights of targets
        #S this calculates weghts for those targets which are currently 
        #S observable, using datetime.datetime.utcnow()
        self.calculate_weights(remaining_time=remaining_time, logger=logger, timeof=timeof, cadence=cadence)
        #S next we sort the target list based on the weight key
        self.sort_target_list(key=key)
        #S now the highest weighted target is the first position of this list,
        #S so we will just return the first entries dictionary

        # if no targets are observable, return an empty dictionary
        if self.target_list[0]['weight'] == -999.0: return {}
 
        # this is done within calculate_weights (right?)
#        target = utils.truncate_observable_window(self.site, self.target_list[0])

        return self.target_list[0]


    def update_list(self,bstar=False,includeInactive=False):
        #S need to update list potentially
        try:
            self.target_list = targetlist.mkdict(includeInactive=includeInactive) + targetlist.mkdict(bstar=True,includeInactive=includeInactive)
        except:
            #S Placeholder for logger
            pass
        
    def calculate_weights(self, tels=None, remaining_time=86400.0, logger=None, timeof=None, cadence=True):
        #S need to update weights for all the targets in the list.
        #S going to use simple HA weighting for now.
        if timeof == None: timeof = datetime.datetime.utcnow()

        for target in self.target_list:

            target = utils.truncate_observable_window(self.site, target,timeof=timeof)

            # if the target is observable
            if (target['starttime'] <= timeof) and (target['endtime'] >= (timeof + datetime.timedelta(seconds=target['exptime'][0]))):
                #S this is where you want to insert whatever weight function
                if cadence:
                    target['weight'] = self.calc_weight_multi(target,timeof=timeof)*target['priority']
                else:
                    target['weight'] = self.calc_weight_ha(target,timeof=timeof)*target['priority']

                # weight for 1 Bstar per night
                if target['bstar'] and (self.bstarobserved):
                    # Only observe one B star per night (unless we have nothing better to do)
                    target['weight'] /= 1000000.0
                else:
                    # exponentially increase the priority of B stars as the night progresses
                    # multiply by 1 for 10 hours left in the night and 100 for 0.5 hours left in the night
                    timeleft = (self.nextsunrise(datetime.datetime.utcnow()) - datetime.datetime.utcnow()).total_seconds()
                    target['weight'] *= 0.784*math.exp(8725.59/timeleft) 
            else:
                # not observable
                target['weight'] = -999.0

            if logger != None:     
                pass
            else:
                print target['name'], target['starttime'], target['endtime'], timeof,  target['exptime'], target['weight']


        #pass

    def make_fixedBodies(self):
        for target in self.target_list:
            target['fixedbody'] = ephem.FixedBody()
            target['fixedbody']._ra = ephem.hours(target['ra'])
            target['fixedbody']._dec = ephem.degrees(target['dec'])
#            target['fixedbody']._epoch = 2000.0
            target['fixedbody'].compute(self.obs)
        
    def calc_weight_ha(self,target,logger=None,timeof=None):
        """
        simple, just going to weight for current ha sort of
        weight = 1 - abs(HA/RA)
        """
        if 'observed' in target.keys():
            if target['observed']>2:
                return -1

        # temp set the horizon for targets
        if timeof == None: timeof = datetime.datetime.utcnow()
        if logger != None: logger.info("Scheduler time is " + str(timeof))

        self.obs.date = timeof
        lst = math.degrees(self.obs.sidereal_time())/15.
        target['fixedbody'].compute(self.obs)
        return 1.0 - np.abs((lst-target['ra'])/12.0)

    def calc_weight_multi(self,target,timeof=None, obspath=None):

        # need some sort of default for the obs path
        if obspath == None:
            obspath = self.obspath

        # if timeof not provided, use current utc
        if timeof == None:
            timeof = datetime.datetime.utcnow()

        self.obs.date = timeof

        #TODO update target['last_obs'] correctly
        target['last_obs'] = [[datetime.datetime(2000,1,1,0,0,0),datetime.datetime(2000,1,1,0,0,59),59,80,0,1]]

        #S if the target was observed less than the separation time limit
        #S between observations, then we give it an 'unobservable' weight.
        # just comment out if you want a random start time
#        self.start_ha = -target['seplimit']/3600.
        self.start_ha = 0.0#-target['seplimit']/3600.


        if (timeof-target['last_obs'][-1][0]).total_seconds() < target['seplimit']:
            return -1.0

        if target['observed']>target['maxobs']:
            return -1.0

        cad_weight = 0.0
        try:
            
            if os.path.exists(obspath+target['name']+'.txt'):
                obs_hist = self.get_obs_history(target,obspath=obspath)
                cad_weight = 0.0

                # if hasn't been observed in the past day, boost its priority
                #target['last_obs'][-1][0] is the start time of the most recent observation
                if (timeof-target['last_obs'][-1][0]).total_seconds() > 86400.0:
#                    print('cad boost to ' +target['name'])
                    cad_weight = 1.0
        except:
            print('boop\n')
            cad_weight = 1.0
        
        #S weight for the first observation of a three obs run.
        if target['observed']%3==0:
            #S the standard deviation of this is actually important as we 
            #S start to think about cadence. if we want to make cadence
            #S and the three obs weight complimetnary or something, a steeper
            #S drop off of the gaussian WILL matter when mixed with a cad term.
            target_ha=(math.degrees(self.obs.sidereal_time())/15.0-target['ra'])
            threeobs_weight= \
                np.exp(-((target_ha-self.start_ha)**2./(2.*.5**2.)))

        #S weight for the second observation of a three obs run.
        elif target['observed']%3 == 1:
            #S there is a cap of 2. on this weight, which means a third 
            #S observation will always be prioritized.
            threeobs_weight=np.min(\
                [2.,1.+((timeof-target['last_obs'][-1][0]).total_seconds()-\
                            -target['seplimit'])/target['seplimit']])

        #S weight for the third observation of a three obs run, but note that
        #S there is no cap on this one.
        elif target['observed']%3 == 2:
            threeobs_weight=2.+\
                ((timeof-target['last_obs'][-1][0]).total_seconds()-\
                     target['seplimit'])/target['seplimit']

        return threeobs_weight+cad_weight
            
    def prep_night(self,timeof=None,init_run=False):
        """
        A function to go through some processes that only need to be done at 
        the beginning of the night.
        """
        if timeof == None:
            timeof = datetime.datetime.utcnow()
        # temp set the horizon for targets
        self.obs.date = timeof
        self.obs.horizon = str(self.target_min_horizon)
        # get a random starting hour angle normally distrubted around an hour
        # angle of -2. this is for the three observations per night of MINERVA,
        # and might be useless to you.
        self.start_ha = np.random.normal(loc=-2.,scale=.5)

        for target in self.target_list:
            # reset targets observation counter for the night to zero
            target['observed']=0
            # compute the target for the obs at time and horizon
            target['fixedbody'].compute(self.obs)
            # if it's neverup, flag it
            if target['fixedbody'].neverup:
                target['neverup']=True
            else:
                target['neverup']=False
                """
                try:
                    target['last_obs']=self.get_obs_history(target,prev_obs=1)
                except:
                    target['last_obs']=[]
                """
            if init_run == True:
                try:
                    target['last_obs']=self.get_obs_history(target,prev_obs=1)
                except:
                    target['last_obs']=[[datetime.datetime(2000,1,1,0,0,0),datetime.datetime(2000,1,1,0,0,59),59,80,0,1]]
        # reset to sun horizon
        self.obs.horizon = str(self.sun_horizon)
                
    def get_obs_history(self,target,prev_obs=1,obspath=None):
        if obspath == None:
            obspath = self.obspath
        # a function that 'tail's a target file to get the last prev_obs and
        # places the details in a list?
        # add a line for the empty one at the end of a file?

        # TODO: update from spectrograph.take_image
        target_file = obspath+target['name']+'.txt'
        if os.path.exists(target_file):
            raw_obs=\
                subprocess.check_output(['tail','-n',str(prev_obs),target_file])
            obs_lines = raw_obs.split('\n')[:-1]
            obs_list = []
            for line in obs_lines:
                try:
                    line = line.split('\t')
                    line[0] = datetime.datetime.strptime(line[0],self.dt_fmt) # start time of exposure
                    line[1] = datetime.datetime.strptime(line[1],self.dt_fmt) # end time of exposure
                    line[2] = float(line[2]) # duration in seconds of exposure
                    line[3] = float(line[3]) # altitude (degrees)
                    line[4] = float(line[4]) # azimuth (degrees)
                #                line[5] = float(line[5]) # quality flag
                    obs_list.append(line)
                except:
                    # so it doesn't try and parse the header
                    pass
            if obs_list is []:
                ipdb.set_trace()
        else:
            # default to observed a long time ago
            obs_list = [[datetime.datetime(2000,1,1,0,0,0),datetime.datetime(2000,1,1,0,0,59),59,80,0,1]]

        return obs_list

    # TODO: call by spectrograph.take_image
    def record_observation(self,target,telescopes=None, timeof=None):
        if timeof == None: timeof = datetime.datetime.utcnow()
        obs_start = timeof
        exptime = self.calc_exptime(target)
        obs_end = timeof + datetime.timedelta(minutes=exptime)
        duration = (obs_end-obs_start).total_seconds()
        try: os.stat(self.sim_path+target['name']+'.txt')
        except: self.write_target_file(target)
        self.scheduler.obs.date=timeof
        # the observation 'quality', or whether it was a good observation or 
        # not (1 is good, 0 is unusable)
        obs_quality = 1
        target['fixedbody'].compute(self.scheduler.obs)
        alt = target['fixedbody'].alt
        azm = target['fixedbody'].az
#        if target['fixedbody'].alt < 0:
#            ipdb.set_trace()
        with open(self.sim_path+target['name']+'.txt','a') as target_file:
            obs_string = obs_start.strftime(self.dt_fmt)+'\t'+\
                obs_end.strftime(self.dt_fmt)+'\t'+\
                '%08.2f'%duration+'\t'+\
                '%06.2f'%math.degrees(alt)+'\t'+\
                '%07.2f'%math.degrees(azm)+' \t '+\
                '%i'%obs_quality+\
                '\n'         
            print(target['name']+': '+obs_string)
            target_file.write(obs_string)
        obs_list = [obs_start,obs_end,duration,alt,azm,obs_quality]
        target['last_obs'].append(obs_list)
        pass

    def nextsunrise(self, currenttime, horizon=-12):
        self.obs.horizon=str(horizon)
        sunrise = self.obs.next_rising(ephem.Sun(),start=currenttime,\
                                           use_center=True).datetime()
        return sunrise
    def nextsunset(self, currenttime, horizon=-12):
        self.obs.horizon=str(horizon)
        sunset = self.obs.next_setting(ephem.Sun(), start=currenttime,\
                                           use_center=True).datetime()
        return sunset

    def prevsunrise(self, currenttime, horizon=-12):
        self.obs.horizon=str(horizon)
        sunrise = self.obs.previous_rising(ephem.Sun(), start=currenttime,\
                                           use_center=True).datetime()
        return sunrise
    def prevsunset(self, currenttime, horizon=-12):
        self.obs.horizon=str(horizon)
        sunset = self.obs.previous_setting(ephem.Sun(), start=currenttime,\
                                           use_center=True).datetime()
        return sunset
    def sunalt(self,timeof=None):
        if timeof == None:
            self.obs.date=datetime.datetime.utcnow()
        else:
            self.obs.date=timeof
        sun = ephem.Sun()
        sun.compute(self.obs)
        return float(sun.alt)*180.0/math.pi
    def sunaz(self):
        sun = ephem.Sun()
        sun.compute(self.obs)
        return float(sun.az)*180.0/math.pi

    def dict_to_class(self):
        #S a potential route we can take.
        pass

    def get_photom_scheds(self,night,telescopes):
        #S Holding off till later on this.
        pass
    def read_photom_sched(self,photom_file):
        #S See get_photom_scheds()
        pass

#S Things we need
#S -good way to break one telescope away.
#S -i think we really need to break away from observing scripts for each 
#S  telescope. or at least need to find a new way potentially.
#S -

if __name__ == '__main__':
    ipdb.set_trace()
    e = scheduler('scheduler.ini')
    ipdb.set_trace()
