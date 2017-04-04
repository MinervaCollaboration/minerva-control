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
        self.time = datetime.datetime(2000,1,1,12,00,00)
        self.obs.date = self.time
        # an ephem sun and moon object for tracking the sun
        self.sun = ephem.Sun()
        self.sun.compute(self.obs)
        self.moon = ephem.Moon()
        self.moon.compute(self.obs)
        
        # seconds between three obs
        self.sep_limit = 120.*60.
        # get the target list
        self.target_list = targetlist.mkdict()
        self.make_fixedBodies()

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


    def calc_ha(self,target):
        self.site.obs.date = datetime.datetime.utcnow()
        lst = (self.site.obs.sidereal_time()*180./np.pi)/15.
        ha = lst - target['ra']
        if ha<0.:
            ha+=24.
        if ha>24.:
            ha-=24.
        if ha>12.:
            ha = ha-24

        return ha

    def sort_target_list(self,key='weight'):
        #S sort the target_list list of target dictionaries by the given key
        try:
            self.target_list = sorted(self.target_list, key=lambda x:-x[key])
            return True
        except:
            print 'Something went wrong when sorting with ' + key
            return False

    def choose_target(self,key='weight',remaining_time=86400.0, logger=None):
        #S we assume you need to update the weights of targets
        #S this calculates weghts for those targets which are currently 
        #S observable, using datetime.datetime.utcnow()
        self.calculate_weights(remaining_time=remaining_time, logger=logger)
        #S next we sort the target list based on the weight key
        self.sort_target_list(key=key)
        #S now the highest weighted target is the first position of this list,
        #S so we will just return the first entries dictionary

        # if no targets are observable, return an empty dictionary
        if self.target_list[0]['weight'] == -999: return {}
        
        return self.target_list[0]


    def update_list(self,bstar=False,includeInactive=False):
        #S need to update list potentially
        try:
            self.target_list=targetlist.mkdict(\
                bstar=bstar,\
                    includeInactive=includeInactive)
        except:
            #S Placeholder for logger
            pass
        

    def calculate_weights(self, tels=None, remaining_time=86400.0, logger=None):
        #S need to update weights for all the targets in the list.
        #S going to use simple HA weighting for now.
        for target in self.target_list:
#            print target
            
            if self.is_observable(target,max_exptime=remaining_time):
                #S this is where you want to insert whatever weight function
                target['weight'] = self.calc_weight(target)#,timeof=self.time)
                if logger != None: logger.debug(target['name'] + ' is has a weight of ' + str(target['weight']))
            else:
                if logger != None: logger.debug(target['name'] + ' is not observable')
                target['weight'] = -999
        #pass

    

    def calc_weight(self,target,logger=None):
        """
        simple, just going to weight for current ha sort of
        weight = 1 - abs(HA/RA)
        """
#        if target['observed']>0:
#            return -1
        # temp set the horizon for targets
        self.obs.date = self.time
        lst = math.degrees(self.obs.sidereal_time())/15.
        target['fixedbody'].compute(self.obs)
        return 1.-np.abs((lst-target['ra'])/12.)

    def make_fixedBodies(self):
        for target in self.target_list:
            target['fixedbody'] = ephem.FixedBody()
#            ipdb.set_trace()
            target['fixedbody']._ra = str(target['ra'])
            target['fixedbody']._dec = str(target['dec'])
#            target['fixedbody']._epoch = 2000.0
            target['fixedbody'].compute(self.obs)

        
    def calc_weight1(self,target,timeof=None,obspath=None):

        # need some sort of default for the obs path
        if obspath == None:
            obspath = self.sim_path

        # if now timeof provided, use current utc
        if timeof == None:
            timeof = datetime.datetime.utcnow()

        #S if the target was observed less than the separation time limit
        #S between observations, then we give it an 'unobservable' weight.
        # just comment out if you want a random start time
#        self.start_ha = -self.sep_limit/3600.
        try:
            if (timeof-target['last_obs'][-1][0]).total_seconds()<\
                    self.sep_limit:
                return -1.
        except:
            ipdb.set_trace()
                

        if target['observed']>3:
            return -1.

        cad_weight = 0.
        try:
            
 #           if os.stat(obspath+target['name']+'.txt'):
#                obs_hist = self.get_obs_history(target,simpath=obspath)
            
                cad_weight = 0.
                # if the last obs time was great than four hours ago, add a bit
#                ipdb.set_trace()
#                print (timeof-obs_hist[-1][1]).total_seconds()>4.*3600.
                if (timeof-target['last_obs'][-1][0]).total_seconds()>24.*3600.:
#                    print('cad boost to ' +target['name'])
                    cad_weight = 1.
        except:
            print('boop\n')
            cad_weight = 1.
        
        #S weight for the first observation of a three obs run.
        if target['observed']%3==0:
            #S the standard deviation of this is actually important as we 
            #S start to think about cadence. if we want to make cadence
            #S and the three obs weight complimetnary or something, a steeper
            #S drop off of the gaussian WILL matter when mixed with a cad term.
            target_ha=(math.degrees(self.obs.sidereal_time())-target['ra'])
            threeobs_weight= \
                np.exp(-((target_ha-self.start_ha)**2./(2.*.5**2.)))

        #S weight for the second observation of a three obs run.
        elif target['observed']%3 == 1:
            #S there is a cap of 2. on this weight, which means a third 
            #S observation will always be prioritized.
            threeobs_weight=np.min(\
                [2.,1.+((timeof-target['last_obs'][-1][0]).total_seconds()-\
                            -self.sep_limit)/self.sep_limit])

        #S weight for the third observation of a three obs run, but note that
        #S there is no cap on this one.
        elif target['observed']%3 == 2:
            threeobs_weight=2.+\
                ((timeof-target['last_obs'][-1][0]).total_seconds()-\
                     self.sep_limit)/self.sep_limit

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
                    target['last_obs']=[]
        # reset to sun horizon
        self.obs.horizon = str(self.sun_horizon)
                
        
    def get_obs_history(self,target,prev_obs=1,simpath=None):
        if simpath == None:
            simpath = self.sim_path
        # a function that 'tail's a target file to get the last prev_obs and
        # places the details in a list?
        # add a line for the empty one at the end of a file?
        target_file = simpath+target['name']+'.txt'
        raw_obs=\
            subprocess.check_output(['tail','-n',str(prev_obs),target_file])
        obs_lines = raw_obs.split('\n')[:-1]
        obs_list = []
        for line in obs_lines:
            try:
                line = line.split('\t')
                line[0] = datetime.datetime.strptime(line[0],self.dt_fmt)
                line[1] = datetime.datetime.strptime(line[1],self.dt_fmt)
                line[2] = float(line[2])
                line[3] = float(line[3])
                line[4] = float(line[4])
                obs_list.append(line)
            except:
                # so it doesn't try and parse the header
                pass
        if obs_list is []:
            ipdb.set_trace()
        return obs_list

    def is_observable(self,target,timeof=None,max_exptime=86400.0, logger=None):
        if logger != None: self.logger.info("Checking observability of " + target['name'])
#        print("Checking observability of " + target['name'])

        # if the timeof obs is not provided, use the schedulers clock for the 
        # time. this could cause issues, need to keep an eye on it
        if timeof == None:
            timeof=datetime.datetime.utcnow()
        #S want to make sure taget is a legal candidate. this includes avoiding
        #S targets who:
        #S   - have not risen
        #S   - will set before exposure will be finished
        #S   - have a suitable moon separation
        #S and other criteia decided later
        
        #S Check to see if we already observed this target. Could be 
        #S switched to check if observed less than a certain number
        #S this condition may need to be removed for multiple observations
        #S per night.
#        if target['observed'] == 1:
#            continue
        #S Check to see if we will try and observe past sunset
        
        target['observable'] = False
        if target['exptime'][0]>max_exptime:
            if logger != None: logger.info(target['name'] + ": exptime (" + str(target['exptime'][0]) + " longer than max_exptime (" + str(max_exptime) + ")")
            return False

        self.obs.horizon = str(self.target_min_horizon)
        target['fixedbody'].compute(self.obs)

        # check if the star will be rising sometime tonight
        #TODO:
        # i think this checks for just a 24 hour period, but needs more 
        # investigation
#        if target['neverup']:
#            #print(target['name']+" is never up")
#            print(target['name'] + ": never up")
#            return False

        #TODO need coordinate propagation before this point, does pyephem do 
        #TODO this?
        # temporarily set the self.obs horizon to the minalt, will be 
        # switched back after check
        self.obs.date = timeof

        # check if the target is separated enough from the moon
        #TODO test
        moon = ephem.Moon()
        moon.compute(self.obs)
        if math.degrees(ephem.separation(moon,target['fixedbody']))<self.min_moon_sep:
            if logger != None: logger.info(target['name'] + ": too close to the moon")
            return False

        # next is some nested if-statements for checking observability
        # still need to check if target will set before end of obs
        # check if the star is already in the sky
        if target['fixedbody'].alt > math.radians(float(self.target_min_horizon)):
            # see if we have enough time to observe
            if timeof+datetime.timedelta(seconds=target['exptime'][0])<\
                    self.nextsunrise(timeof,horizon=self.sun_horizon):
                # check if it will be below horizon at the end of the obs
                finish_time = timeof+\
                    datetime.timedelta(seconds=target['exptime'][0])
                self.obs.date=finish_time
                target['fixedbody'].compute(self.obs)
                if target['fixedbody'].alt>math.radians(self.target_min_horizon):
                    # there is time to observe
                    if logger != None: logger.info(target['name'] + ": is observable")
                    target['observable']=True
                    return True
                else:
                    # the target will set before fully observable
                    if logger != None: logger.info(target['name'] + " not observable; target sets before finish")
                    return False
            else:
                # there is not enought time to observe this target before the 
                # sun rises
                #print("can't observe"+target['name'])

                if logger != None: logger.info(target['name'] + " not observable; sunrise before finish")
                return False
        else:
            if logger != None: logger.info(target['name'] + ": too low (" + str(math.degrees(target['fixedbody'].alt)) + ")")
            return False       
        
        # reset the horizon for the sun
        self.obs.horizon = str(self.sun_horizon)

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
