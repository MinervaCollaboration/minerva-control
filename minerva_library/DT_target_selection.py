#Brianna Beller & Nate McCrady
#MINERVA - Doppler Tomography Target Scheduler
#Scrapes list from George Zhou at Harvard, selects best target for scheduling
#Last edit: 29-Sept-2020

##########################################################################
#NOTE FOR USER

# if run as main code, the observation night is determined by 
# THESE VARIABLES:


# otherwise, can be used by calling the function choose_dt_target() with parameter
# being a datetime object for 4:00pm local time on observing date, which
# returns a dictionary object with chosen target info

##########################################################################

##########################################################################
#IMPORTS

import urllib
import numpy as np
from astropy.coordinates import Angle as ang
from astropy import units as u
#from astropy.time import Time
from collections import OrderedDict
import ephem
import ipdb
#from datetime import timezone
import datetime
import utils
import socket

##########################################################################
#CONVERSIONS AND SETTINGS

secPerDay = 3600*24.
djd2jd= 2415020.0   # add to DJD to get regular JD

horizon = 21.    # degrees
minFraction = 0.5

##########################################################################
#FUNCTIONS

#read in data from url as dict obj
def rdlist():
    
    url='https://www.cfa.harvard.edu/~yjzhou/misc/minerva_sim_data/candidates.csv'

    #import and decode data
#    data = urllib.request.urlopen(url).read()         # use in Python 3
    data = urllib.urlopen(url).read()                  # use in Python 2
    data = data.decode('utf-8')
    
    #split data by rows & separate into lists
    data=data.splitlines()
    for i in np.arange(len(data)):
        data[i]=data[i].split(',')
    
    #create dictionary
    dt_list={}
    
    #add data to dictionary
    for x in np.arange(len(data[0])):
        key=data[0][x]
        value=[]
        for i in np.arange(1, len(data)):
            value.append(data[i][x])
        dt_list[key]=value
   
    return dt_list

def mkdict(name=None,ra=999.,dec=999.,vmag=999.):
# modified from targetlist.py
    
    fauexptime = 5.0*(10**(-0.4*(7-vmag)))
    if fauexptime < 0.01: fauexptime = 0.01
    if fauexptime > 15: fauexptime = 15
    target = OrderedDict()
    target['name'] = name
    target['ra'] = ra
    target['dec'] = dec
    target['starttime'] = datetime.datetime(2015,1,1,00,00,00) #XXX BB: these 2 lines are where I removed leading zeros in month/day arg positions
    target['endtime'] = datetime.datetime(2115,1,1,00,00,00)
    target['spectroscopy'] = True
    target['DT'] = True
    target['filter'] = ['rp']   # not used
    target['num'] = [99]
    target['exptime'] = [1200]  # seconds
    target['priority'] = 1
    target['seplimit'] = 0.0 # no minimum separation
    target['fauexptime'] = fauexptime   # seconds
    target['defocus'] = 0.0
    target['selfguide'] = True
    target['guide'] = False
    target['cycleFilter'] = True   # not used
    target['positionAngle'] = 0.0
    target['acquisition_offset_north'] = 0.    # could need for faint targets?
    target['acquisition_offset_east'] = 0. 
    target['pmra'] = 0.     # could need for high PM targets?
    target['pmdec'] = 0. 
    target['parallax'] = 0.
    target['rv'] = 0.
    target['i2'] = False
    target['vmag'] = vmag
    target['comment'] = ''
    target['observed'] = 0
    target['bstar'] = False
    target['maxobs'] = 99   #not used here
    #target['last_observed'] = 0
        
    if len(target) == 0: return -1   # error trap
    return target


def choose_dt_target(timeof=None, remaining_time=86400.0, logger=None):     #takes datetime obj as parameter 

    if timeof == None: timeof = datetime.datetime.utcnow()
    
    #function returns a target dictionary

    ##########################################################################
    #DATA IMPORT AND FORMATTING

    #read in possible targets from url into dictionary
    dt_list=rdlist()
    
    try:
        #unpack dictionary into lists by spreadsheet column
        toi_list = ((dt_list["TOI"]))
        ra_list = (dt_list["RA"])
        dec_list = (dt_list["DEC"])
        vmag_list = (dt_list["Vmag"])
        tc_list = (dt_list["Tc"])
        period_list = (dt_list["P"])
        q_list = (dt_list["q"])
        snr_list = (dt_list["snr"])
        sg1_list = (dt_list["SG1 Disposition"])
        vsini_list = (dt_list["vsini"])
    except:
        top_candidate='NONE'
        DT_target={}
        return DT_target

    #rename targets from 'xxx.x' to 'TOI xxx.x'
    for i in range(len(toi_list)):
        x = str(toi_list[i]).replace(".","_")
        toi_list[i]=('TOI%s' % x)

    #convert RA & Dec values to angle objects then to floats of degree values
    for i in range(len(dec_list)):
        dec_list[i]=ang('%s degrees' % dec_list[i])
        dec_list[i]=dec_list[i].degree
    
    for i in range(len(ra_list)):
        j=ra_list[i].split(':')
        new_str='{}h{}m{}s'.format(int(j[0]),int(j[1]),float(j[2]))
        ra_list[i]=ang(new_str,unit='degree')
        ra_list[i]=ra_list[i].degree

    #convert numerical data from str to float
    for i in np.arange(len(vmag_list)):
        vmag_list[i]=float(vmag_list[i])

    for i in np.arange(len(tc_list)):
        tc_list[i]=(float(tc_list[i])+2457000)  # using TESS standard for dates, convert to JD

    for i in np.arange(len(period_list)):
        period_list[i]=float(period_list[i])

    for i in np.arange(len(period_list)):
        q_list[i]=float(q_list[i])

    for i in np.arange(len(snr_list)):
        snr_list[i]=float(snr_list[i])

    #convert numerical lists to arrays for calculations
    ra_list=np.array(ra_list)
    dec_list=np.array(dec_list)
    vmag_list=np.array(vmag_list)
    tc_list=np.array(tc_list)
    period_list=np.array(period_list)
    q_list=np.array(q_list)
    snr_list=np.array(snr_list)
    vsini_list = np.array(vsini_list).astype(np.float64)

    ##########################################################################
    #CALCULATIONS

    #extract transit duration from q value
    t_dur = q_list*period_list*secPerDay  # in seconds
    
    ##########################################################################
    #ESTABLISH OBSERVING CONDITIONS

    #establish current time (for performing calculations for night ahead)
    daybefore = timeof-datetime.timedelta(days=1)
    yr=daybefore.year
    mo=daybefore.month
    day=daybefore.day    

    # in utc, starts 4pm local (AZ) time offset for 23:00 start
    currenttime = datetime.datetime(yr,mo,day,23)
    if logger <> None: logger.info('** For Observing Night of {}-{}-{} (UT) **\n'.format(yr,mo,day))

    # create observer with MINERVA location
    # call truncate_observable_window from utils.py to do this
    obs=ephem.Observer()
    obs.lat = ephem.degrees(str(31.680407))             #deg N
    obs.lon = ephem.degrees(str(-110.878977))           #deg E
    obs.horizon = ephem.degrees(str(-12.0))
    obs.elevation = 2316.0                              #meters
    obs.date=currenttime

    #create sun & moon objects
    sun=ephem.Sun()
    sun.compute(obs)

    moon=ephem.Moon()
    moon.compute(obs)

    #when is sunset? (sun alt < -12deg)
    next_sunset=obs.next_setting(sun, currenttime, use_center=True)     

    #when is sunrise? (sun alt > -12deg)
    next_sunrise=obs.next_rising(sun, currenttime, use_center=True)

    if logger <> None: logger.info('Sunset (UT):  {}    Sunrise (UT): {}'.format(next_sunset,next_sunrise))

    #convert DJD to JD for subsequent calculations
    next_sunset = next_sunset + djd2jd
    next_sunrise = next_sunrise + djd2jd

    # truncate by remaining_time
    end_time = utils.datetime2jd(timeof) + remaining_time/86400.0
    if end_time < next_sunrise:
        next_sunrise = end_time

    #establish 1-min interval time check points for target (needed later for altitude & moon separation)
    ttime=[next_sunset]
    while max(ttime) <= next_sunrise:
        ttime.append(max(ttime)+60/secPerDay)

    ##########################################################################
    #TARGET FILTERING: keep only observable transits (partial & full)
    
    #create blank lists for storing data for viable candidates outside loop
    obs_candidates=[]
    obs_start=[]
    obs_end=[]
    frac_obs=[]
    max_alt=[]
    
    #iterate through targets to find viable candidates for the night
    if logger <> None: logger.info('** There are {} stars in the target list. **'.format(len(toi_list)))  # N

    for i in np.arange(len(toi_list)):
        target={}
        target['name']=toi_list[i]
        target['ra']=ra_list[i]
        target['dec']=dec_list[i]
        target['vmag']=vmag_list[i]
        target['tc']=tc_list[i]
        target['period']=period_list[i]
        target['q']=q_list[i]
        target['snr']=snr_list[i]
        target['sg1']=sg1_list[i]
        target['vsini']=vsini_list[i]
        target['t_dur']=t_dur[i]   # keep this as exactly (egress - ingress) in seconds

        if snr_list[i] < 7.5: continue # skip low SNR objects
        
        if vsini_list[i] > 50: continue # skip rapid rotators

        #create fixed body for ephem calculations
        target['fixedbody'] = ephem.FixedBody(obs)
        target['fixedbody']._ra = ephem.degrees(str(target['ra']))
        target['fixedbody']._dec = ephem.degrees(str(target['dec']))
        target['fixedbody'].compute(obs)

        #increment target's transit midpoint ('tc' value) until next transit occurs after the next sunset
        #use the midpoint here so we can find partial events for later use
        while target['tc'] <= next_sunset:
            target['tc']=target['tc']+target['period']

        #establish next ingress and egress times for target
        target['next_transit_start']= target['tc'] - target['t_dur']/2./secPerDay
        target['next_transit_end']= target['tc'] + target['t_dur']/2./secPerDay

        # JDE: doesn't this skip any partials where only egress is visible?
        # JDE: don't we want target['next_transit_start'] here?
        #if target's next midpoint doesn't end before the next sunrise, continue loop with next candidate
#        if target['tc'] > next_sunrise:
        if target['next_transit_start'] > next_sunrise:
            #if logger <> None: logger.info('{} eliminated. Next transit: {}'.format(target['name'],str(utils.jd2datetime(target['tc']))))
            continue    # go to next target in list
        if logger <> None:
            logger.info('Transit found for {}, RA: {:.4f}, Dec: {:.4f}'.format(target['name'],target['ra'],target['dec']))
            logger.info('Transit center at {}, duration {:.2f} hrs'.format(str(utils.jd2datetime(target['tc'])),target['t_dur']/3600.))
            logger.info('Ingress: {}, egress: {}'.format(str(utils.jd2datetime(target['next_transit_start'])),
                                                         str(utils.jd2datetime(target['next_transit_end']))))

        #if transit ingress is before sunset, flag as a partial event
        if target['next_transit_start'] < next_sunset:
            if logger <> None: logger.info('Partial event: {} has ingress before sunset.'.format(target['name']))

        #if transit egress is after sunrise, flag as a partial event
        if target['next_transit_end'] > next_sunrise:
            if logger <> None: logger.info('Partial event: {} has egress after sunrise.'.format(target['name']))

        # ALTITUDE CALCULATIONS

        #find earlier of rise-through-20-deg time or sunset
        #and later of set-through-20-deg time or sunrise

        target_alt=[]
        event_inProgress=[]   # a minute-by-minute Boolean array
        for j in ttime:
            obs.date=j-djd2jd   # ephem calculates in DJD!!
            target['fixedbody'].compute(obs)
            target_alt.append(target['fixedbody'].alt)  # in radians
            event_inProgress.append((j>target['next_transit_start'] and j<target['next_transit_end'])and(target['fixedbody'].alt*180/np.pi > horizon))
        target_alt=np.array(target_alt)*180/np.pi         #convert alt to deg
    
        fractionObservable = np.array(event_inProgress).sum()/(target['t_dur']/60.)
        # fix the rounding error for coarse time steps
        if np.abs(1-fractionObservable) < (60./t_dur[i]): fractionObservable = 1.0
        if fractionObservable == 0:
            if logger <> None: logger.info('Entire transit for {} occurs below observable altitude.'.format(target['name']))
            continue    # go to next target in list

        if np.max(target_alt) < horizon:
            if logger <> None: logger.info('Object never rises above minimum altitude.')
            continue    # go to next target in list
    
        #NOTE: DOESN'T CURRENTLY HAVE MAX ALTITUDE CAP
        max_alt.append(np.max(target_alt))
        if logger <> None: logger.info('Max altitude is: {:.1f}'.format(np.max(target_alt)))
        
        #definition of ttime above ensures these are between sunset and sunrise
        entersHorizon = np.min(np.array(ttime)[target_alt >= horizon])
        leavesHorizon = np.max(np.array(ttime)[target_alt >= horizon])

        '''
        #calculate start and end of observations based on (duration of baseline) = t_dur
        #currently unused, as for now any good target we will observe as long as it is above our horizon
        #start t_dur before midpoint
        baselineBegin = target['next_transit_start'] - target['t_dur']/2./secPerDay
        #end t_dur after midpoint
        baselineEnd = target['next_transit_end'] + target['t_dur']/2./secPerDay

        print('{} Sunset\n{} StarRises\n{} BaselineBegin\n'.format(next_sunset,entersHorizon,baselineBegin))
        print('{} BaselineEnd\n{} StarSets\n{} Sunrise\n'.format(baselineEnd,leavesHorizon,next_sunrise))
        '''

        #save observation start and end times outside of loop
        obs_start.append(entersHorizon)
        obs_end.append(leavesHorizon)
        frac_obs.append(fractionObservable)
    
        '''
        #will target's separation from moon be > 10deg during entire transit?
        moon_sep=[]
        for j in ttime:
            obs.date=j
            moon.compute(j)
            target['fixedbody'].compute(obs)
            moon_sep.append(ephem.separation(moon,target['fixedbody']))
        moon_sep=np.array(moon_sep)
        moon_sep=moon_sep*180/np.pi           #convert angle of separation to deg
    
        #check here to see if minimumn moon_sep is less than limit
        # currently not implemented
        '''
    
        #NOT CURRENTLY ELIMINATING TARGETS BASED ON SG1 DISPOSITION
        #reserved for possible future use
        
        #if all above conditions are met, add to new list of viable candidates (by index #)
        obs_candidates.append(i)
    
    #readable printout of night's viable candidates  if desired
    if logger <> None:
        logger.info('CANDIDATE EVENTS ({}):'.format(len(obs_candidates)))
        if len(obs_candidates) > 0:
            for i in np.arange(len(obs_candidates)):
                logger.info('Candidate: {}'.format(toi_list[obs_candidates[i]]))
                logger.info('RA: {:6.3f}  Dec: {:6.3f}'.format(ang(ra_list[obs_candidates[i]],u.deg),ang(dec_list[obs_candidates[i]],u.deg)))
                logger.info('Obs Start (UT): {}'.format(str(utils.jd2datetime(obs_start[i]))))
                logger.info('Obs End (UT): {}'.format(str(utils.jd2datetime(obs_end[i]))))
                logger.info('Fraction of transit duration observable: {:.2f}'.format(frac_obs[i]))
                logger.info('SNR: {:5.1f}'.format(snr_list[obs_candidates[i]]))
                logger.info('Period: {:5.1f}'.format(period_list[obs_candidates[i]]))
                if max_alt[i] > 85:
                    logger.info('--> WARNING: Max altitude for {} exceeds 85 degrees <--'.format(toi_list[obs_candidates[i]]))
                    logger.info('Max altitude: {:.1f} deg'.format(max_alt[i]))
#                logger.info('(Index #: {})'.format(i))
            
    ##########################################################################
    #TARGET SELECTION: return the single top candidate for the night
    
    #pick best candidate of obs_candidates
    if len(obs_candidates) >= 1:
        
        #loop to remove candidates with less than minimum allowed fraction of transit observable        
        i=len(obs_candidates)-1
        while i >=0:
            if frac_obs[i] < minFraction:
                obs_candidates.pop(i)
                obs_start.pop(i)
                obs_end.pop(i)
                frac_obs.pop(i)
                max_alt.pop(i)
            i-=1

        #check if more than one candidate remaining
        if len(obs_candidates)>1:
        
            #more than one transit
            #check if any targets with 100% transit observable
            if max(frac_obs) == 1:
                #at least one full transit
                #if so, eliminate targets that aren't 100% obs
                i=len(obs_candidates)-1
                while i>=0:
                    if frac_obs[i]!=1:
                        obs_candidates.pop(i)
                        obs_start.pop(i)
                        obs_end.pop(i)
                        frac_obs.pop(i)
                        max_alt.pop(i)
                    i-=1

                #check if more than one candidate remaining
                if len(obs_candidates)>1:    
                    
                    #multiple full transits: select target with highest SNR
                    cand_snr=[]
                    for i in obs_candidates:
                        cand_snr.append(snr_list[i])
                    
                    #eliminate targets that don't have highest SNR of remaining
                    i=len(obs_candidates)-1
                    while i>=0:
                        if cand_snr[i]!=max(cand_snr):
                            obs_candidates.pop(i)
                            obs_start.pop(i)
                            obs_end.pop(i)
                            frac_obs.pop(i)
                            max_alt.pop(i)
                            cand_snr.pop(i)
                        i-=1                    

                    #check if more than one candidate remaining (i.e., multiple targets with same SNR)
                    if len(obs_candidates)>1: 

                        #if so, select target with higher period
                        cand_p=[]
                        for i in obs_candidates:
                            cand_p.append(period_list[i])
                        
                        #top candidate name
                        top_candidate=toi_list[obs_candidates[cand_p.index(max(cand_p))]]
                        
                        #top candidate index number in dictionary with all scraped data
                        chosenIndex=obs_candidates[cand_p.index(max(cand_p))]
                        
                        #create dictionary
                        DT_target=mkdict(name=top_candidate,ra=ra_list[chosenIndex]/15.,dec=dec_list[chosenIndex],vmag=vmag_list[chosenIndex])
                    
                    else:
                            
                        #top candidate name
                        top_candidate=toi_list[obs_candidates[0]]
                        
                        #index number in dictionary with all scraped data
                        chosenIndex=obs_candidates[0] 
            
                        # build target dictionary
                        DT_target=mkdict(name=top_candidate,ra=ra_list[chosenIndex]/15.,dec=dec_list[chosenIndex],vmag=vmag_list[chosenIndex])
                
                else:
                    #only one full transit in the list
                    #top candidate name
                    top_candidate=toi_list[obs_candidates[0]]
                    
                    #index number in dictionary with all scraped data
                    chosenIndex=obs_candidates[0] 
        
                    # build target dictionary
                    DT_target=mkdict(name=top_candidate,ra=ra_list[chosenIndex]/15.,dec=dec_list[chosenIndex],vmag=vmag_list[chosenIndex])   

            else:
                #no full transits observable, only patrial transits
                #select target with highest SNR, regardless of fraction observable (all are more than 50 percent)

                cand_snr=[]
                for i in obs_candidates:
                    cand_snr.append(snr_list[i])
                
                #eliminate targets that don't have highest SNR of remaining
                i=len(obs_candidates)-1
                while i>=0:
                    if cand_snr[i]!=max(cand_snr):
                        obs_candidates.pop(i)
                        obs_start.pop(i)
                        obs_end.pop(i)
                        frac_obs.pop(i)
                        max_alt.pop(i)
                        cand_snr.pop(i)
                    i-=1                    

                #check if more than one candidate remaining
                if len(obs_candidates)>1: 
                
                    #if so, select target with higher period
                    
                    cand_p=[]
                    for i in obs_candidates:
                        cand_p.append(period_list[i])
                    
                    #top candidate name
                    top_candidate=toi_list[obs_candidates[cand_p.index(max(cand_p))]]

                    #top candidate index number in dictionary with all scraped data
                    chosenIndex=obs_candidates[cand_p.index(max(cand_p))]
                    
                    #create dictionary
                    DT_target=mkdict(name=top_candidate,ra=ra_list[chosenIndex]/15.,dec=dec_list[chosenIndex],vmag=vmag_list[chosenIndex])
                
                else:
                        
                    #top candidate name
                    top_candidate=toi_list[obs_candidates[0]]
                    
                    #index number in dictionary with all scraped data
                    chosenIndex=obs_candidates[0] 
        
                    # build target dictionary
                    DT_target=mkdict(name=top_candidate,ra=ra_list[chosenIndex]/15.,dec=dec_list[chosenIndex],vmag=vmag_list[chosenIndex])   
                
        #if only one candidate remaining after eliminating <50% observable transit    
        elif len(obs_candidates)==1:
                    
            #top candidate name
            top_candidate=toi_list[obs_candidates[0]]

            #index number in dictionary with all scraped data
            chosenIndex=obs_candidates[0] 

            # build target dictionary
            DT_target=mkdict(name=top_candidate,ra=ra_list[chosenIndex]/15.,dec=dec_list[chosenIndex],vmag=vmag_list[chosenIndex])            
        
        elif len(obs_candidates)==0:
            #no candidate remaining after eliminating < minimum fraction observable transit  
            top_candidate='NONE'
            DT_target={}
            
    else:
        #no candidate transits were found, no DT target, return minimal dictionary         
        top_candidate='NONE'
        DT_target={}


    
    #readable printout of night's top candidate if desired
    if logger <> None:
        if top_candidate!='NONE':
            logger.info('TOP DT CANDIDATE: {}'.format(top_candidate))
        else:
            logger.info('No viable DT candidates on chosen night')
        
    return DT_target


##########################################################################
# for testing
if __name__=='__main__':

    hostname = socket.gethostname()
    if hostname == 'Main':
        base_directory = '/home/minerva/minerva-control/'
    else:
        print 'hostname not recognized'
        sys.exit()

    logger_name = 'dtscheduler.log'

    today = datetime.datetime.utcnow()
    night = 'n' + today.strftime('%Y%m%d')
    logger = utils.setup_logger(base_directory,night,logger_name)

    # choose the day to match timeof parameter in mainNew.py
    timeof = datetime.datetime(2020,9,25)  # use to simulate night
    timeof = datetime.datetime.utcnow()   # matches call from mainNew.py

    # call the function, store disctionary
    remaining_time = 3600
    target = choose_dt_target(timeof=timeof, remaining_time=remaining_time, logger=logger)

    ipdb.set_trace()
