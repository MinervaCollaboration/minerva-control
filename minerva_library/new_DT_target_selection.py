# Rewritten by Cayla Dedrick on 20210626

import numpy as np
import pandas as pd
from astropy.coordinates import SkyCoord
from astropy import units as u 
from collections import OrderedDict
import ephem
import ipdb
import datetime
import utils
import socket

def rd(extra_targets = None, logger=None):
     '''
    Reads in George's DT target list and any extra DT targets.

    Parameters
        extra_targets: str, optional
            name of .csv file containing the DT targets we want to add manua\
lly, must be in same format as the DT target list
    Returns:
        dt_list: dict
            DT targets and their parameters
    '''

    url='https://www.cfa.harvard.edu/~yjzhou/misc/minerva_sim_data/candidate\
s.csv'
    df = pd.read_csv(url)
    df['Name'] = ['TOI'+str(row['TOI']).replace(".","_") for i, row in df.iterrows()]
    if extra_targets != None:
        try: extra_df = pd.read_csv(extra_targets)
        except:
            if logger != None: logger.info("Target file '" + extra_targets +\
 "' does not exist. Continuing with regular DT targets.")
            continue
        df = pd.concat([df, extra_df])
    dt_dict = df.to_dict('list')
    
def mkdict(name=None,ra=999.,dec=999.,vmag=999.):
# modified from DT_target_selection.py (modified from targetlist.py)
    
    fauexptime = 5.0*(10**(-0.4*(7-vmag)))
    if fauexptime < 0.01: fauexptime = 0.01
    if fauexptime > 15: fauexptime = 15
    target = OrderedDict()

    target['name'] = name
    target['ra'] = ra
    target['dec'] = dec
    target['starttime'] = datetime.datetime(2015,1,1,00,00,00)
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

def choose_dt_target(timeof=None, remaining_time=84600.0, logger=None, extra_targets=None):
    if timeof == None: timeof = datetime.datetime.utcnow()
    
    dt_targets = rdlist(extra_targets=extra_targets, logger=logger)
    
    # convert RA, Dec to decimal degrees
    coord = SkyCoord(ra = dt_targets['RA'], dec = dt_targets['DEC'], unit=(u.hourangle, u.deg))
    dt_targets['RA'] = coord.ra.deg
    dt_target['DEC'] = coord.dec.deg

    # calculate transit durations
    q = np.array(dt_targets['q'])
    P = np.array(dt_targets['P'])
    t_dur = q * P * u.day

    # observations start at UT 23:00:00 (4PM MST)
    
    start = timeof.date()
    if timeof.hour < 23:
        start -= datetime.timedelta(days=1)
    
    starttime = datetime.datetime(start.year, start.month, start.day, 23)
    if logger != None: logger.info('** For Observing Night of n{}{:02d}{:02d}**\n'.format(timeof.year, timeof.month, timeof.day))
    
    obs = ephem.Observer()
    obs.lat = ephem.degrees('31.680407')
    obs.lon = ephem.degrees('-110.878977')
    obs.horizon = ephem.degrees('-12.0')
    obs.elevation = 2316.0
    obs.date(starttime)

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

    obs_candidates=[]
    obs_start=[]
    obs_end=[]
    frac_obs=[]
    max_alt=[]
    
    #iterate through targets to find viable candidates for the night
    if logger <> None: logger.info('** There are {} stars in the target list. **'.format(len(toi_list)))
    
    for i in range(len(q)):
        
        if dt_targets['snr'][i]: continue 
        if dt_targets['vsini'][i] < 7.5: continue
        
        fixedbody = ephem.FixedBody(obs)
        fixedbody._ra = ephem.degrees(str(dt_targets['RA'][i]))
        fixedbody._dec = ephem.degrees(str(dt_targets['DEC'][i]))
        fixedbody.compute(obs)
        
        tc = dt_targets['Tc'][i]
        while tc <= next_sunset:
            tc += dt_targets['P'][i]
            
        next_transit_start = tc - t_dur[i].to(u.s)/2
        next_transit_end = tc + t_dur.to(u.s)/2

        if next_transit_start > next_sunrise:
            continue
        
        #TODO: Add logging
        if next_transit_start < next_sunset:
            if logger != None: logger.info('Partial event: {} ingress is before sunset.'.format(dt_targets['Name'][i]))

        if next_transit_end < next_sunrise:
            if logger != None: logger.info('Partial event: {} egress is after sunrise.'.format(dt_targets['Name'][i]))
        
        



        
       



 
