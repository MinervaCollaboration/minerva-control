#S was going to make targets their own classes, but might as well preserve 
#S dicts. we can just have the scheduler perform functions on them and update
#S values. 


import numpy as np
import targetlist
import ipdb
import env
import datetime
import time

###
# SCHEDULER
###

class scheduler:
    def __init__(self,site,base_directory='/home/minerva/minerva-control'):
        #S want to get the site from the control class, makes easy computing
        #S LST and such
        self.base_directory = base_directory
        self.site = site
        #S this is to track whether we are currently taking a spectrum, which
        #S we will need to know if we finish a photometry sequence and a 
        #S telescope is freed up.
        self.spec_in_progress = False
        
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
            self.target_list = sorted(self.target_list, key=lambda x:x[key])
            return True
        except:
            print 'Something went wrong when sorting with ' + key
            return False

    def choose_target(self):
        #S need to make a target class for being observered?
        #S will return the selected target dictionary
        #S need way to choose next best target

        #S update the time, probably don't need this here
        self.site.obs.date = datetime.datetime.utcnow()
        #S update the weights for all the targets in our list
        self.calculate_weights()
        #S sort the target list by weight, so that the list of dictionaries
        #S is now in descending order based on weight.
        self.target_list = sorted(targetlist, key=lambda x:x['weight'])
        for target in self.target_list:
            if self.can_observe(target):
                return target
            #S I thnik we should cover all this in can_observe()
            """
            #S Check to see if we already observed this target. Could be 
            #S switched to check if observed less than a certain number
            #S this condition may need to be removed for multiple observations
            #S per night.
            if target['observed'] == 1:
                continue
            #S Check to see if we will try and observe past sunset
            if (datetime.datetime.utcnow()+\
                    datetime.timedelta(seconds=target['exptime']))\
                    >self.obs.NautTwilBegin():
                continue
            #S check to see if the target will go below horizon before 
            #S finishing the observation.
            
            #S if all checks pass, we want to return the chosen target dict

            """


    def update_list(self,bstar=False,includeInactive=False):
        #S need to update list potentially
        try:
            self.target_list=targetlist.mkdict(\
                bstar=bstar,\
                    includeInactive=includeInactive)
        except:
            #S Placeholder for logger
            pass
        

    def calculate_weights(self):
        #S need to update weights for all the targets in the list.
        #S going to use simple HA weighting for now.
        for target in self.target_list:
#            if self.can_observe(target):
            target['weight'] = self.calc_weight(target)
#            else:
#                target['weight'] = -1
        pass


    def calc_weight(self,target):
        for target in self.target_list:
            target['weight'] = target['vmag']
        
    def calc_weight1(self,target):
        #S if the target was observed less than the separation time limit
        #S between observations, then we give it an 'unobservable' weight.
        
        start_ha = - 0.5
        if (datetime.datetime.utcnow()-target['last_obs']).total_seconds<\
                self.sep_limit:
            target['weight'] = -1
        
        #S weight for the first observation of a three obs run.
        elif target['observations']%3==0:
            #S the standard deviation of this is actually important as we 
            #S start to think about cadence. if we want to make cadence
            #S and the three obs weight complimetnary or something, a steeper
            #S drop off of the gaussian WILL matter when mixed with a cad term.
            target['weight'] = np.exp(-((x-start_ha)**2./(2.*.5**2.)))

        #S weight for the second observation of a three obs run.
        elif target['observations']%3 == 1:
            #S there is a cap of 2. on this weight, which means a third 
            #S observation will always be prioritized.
            target['weight'] = np.min(\
                [2.,1.+((now-target['last_obs']).total_seconds()/60.-30.)/30.])

        #S weight for the third observation of a three obs run, but note that
        #S there is no cap on this one.
        elif target['observations']%3 == 2:
            target['weight']=2.+((now-target['last_obs']).total_seconds()/60.\
                                     -30.)/30.
            
            
            
        

    def can_observe(self,target):
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
        if (datetime.datetime.utcnow()+\
                datetime.timedelta(seconds=target['exptime']))\
                >self.site.NautTwilEnd():
            pass
#            continue
        #S check to see if the target will go below horizon before 
        #S finishing the observation.
            
        #S if all checks pass, we want to return the chosen target dict

        return True
        pass

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
    test_site = env.site('site_mtHopkins.ini','/home/minerva/minerva-control')
    target = {'ra':21.}
    e = scheduler(test_site)
    print e.calc_ha(target)
    print test_site.obs.sidereal_time()
    time.sleep(10)
    print test_site.obs.sidereal_time()
    ipdb.set_trace()
