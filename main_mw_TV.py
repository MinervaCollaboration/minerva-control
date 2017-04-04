#Minerva system main routine
#create master control object and run one of the observing scripts
import matplotlib
matplotlib.use('Agg')
import sys, os
sys.dont_write_bytecode = True
from minerva_library import control  # An error occurs. # "threading" and "os" are now imported
from minerva_library import rv_control
from minerva_library import utils
import datetime

#-------------------
#from minerva_library import phony_control
import threading
import time, json, copy, ipdb
import numpy as np
#================#

#  At 4:00 let's run main.py.


def SetupTech(minerva, telescope, camera, telescope_num=0):
    #------------place outside---
    #--------Setup function-----------

    if not telescope.initialize(tracking=False, derotate=False):
        telescope.recover(tracking=False, derotate=False)
        
    #S Finally (re)park the telescope.
    telescope.park()     

    # wait for the camera to cool down
    camera.cool()

    #----------------Phot function---------------
    #---------Run outside-------        
    #-------------Skyflats function-----------
   
    return


def PhotCalib(minerva, CalibInfo, telescope_num=0, checkiftime=True):
    #  Photometric Calibrations

    # Take biases and darks
    # wait until it's darker to take biases/darks
    readtime = 10.0
        
    bias_seconds = CalibInfo['nbias']*readtime+CalibInfo['ndark']*sum(CalibInfo['darkexptime']) + CalibInfo['ndark']*readtime*len(CalibInfo['darkexptime']) + 600.0  # why the 600 seconds?
    biastime = minerva.site.sunset() - datetime.timedelta(seconds=bias_seconds)
    waittime = (biastime - datetime.datetime.utcnow()).total_seconds()
    if waittime > 0 and checkiftime:
        # Take biases and darks (skip if we don't have time before twilight)
        minerva.logger.info(telescope_name + 'Waiting until darker before biases/darks (' + str(waittime) + ' seconds)')
        time.sleep(waittime)
        #S Re-initialize, and turn tracking on.
        minerva.doBias(CalibInfo['nbias'],telescope_num)
        minerva.doDark(CalibInfo['ndark'], CalibInfo['darkexptime'],telescope_num)

    return



def startSkyFlats(minerva, telescope, dome, CalibInfo, telescope_num=0):
    # Take Evening Sky flats
    #S Initialize again, but with tracking on.
    if not telescope.initialize(tracking=True, derotate=True):
        telescope.recover(tracking=True, derotate=True) # This recovers tele if

    
    flatFilters = CalibInfo['flatFilters'] 
    minerva.doSkyFlat(flatFilters, False, CalibInfo['nflat'],telescope_num)
        
    # Wait until nautical twilight ends
    timeUntilTwilEnd = (minerva.site.NautTwilEnd() - datetime.datetime.utcnow()).total_seconds()
    if timeUntilTwilEnd > 0:
        minerva.logger.info(telescope_name + 'Waiting for nautical twilight to end (' + str(timeUntilTwilEnd) + 'seconds)')
        time.sleep(timeUntilTwilEnd)
        
    while not dome.isOpen() and datetime.datetime.utcnow() < minerva.site.NautTwilBegin() and datetime.datetime.utcnow() < minerva.site.NautTwilEnd():
        minerva.logger.info(telescope_name + 'Enclosure closed; waiting for conditions to improve')
        time.sleep(60)
    
    
    return


def dynamicSched(free_teles, time_interval):

     '''
     free_teles: array or list of the telescope numbers that are free for RV observations

     Return
     -------
     target_dictionary:
     '''
     
     # create an xterm window

     return




# acquisition == 2 min , readtime_phot = 7 sec, readtime_spec = 21.6 sec  # acquisition ~ slewing, focusing, fine pointing
# duration ==  acquisition + np.sum( num*(exptime + readtime)  )
# save duration in its list or dictionary
def Acq_Exp_RdO(acquisition, target_dict, readtime):
     '''
     Calculate the total amount of time (in seconds) being used by CCD activity and telescope movements
     '''
     filters = target_dict['filter']
     num_exposures = target_dict['num'][0]
     exptime = np.float(target_dict['exptime'][0])

     return datetime.timedelta( seconds = acquisition + np.sum( num_exposures*(exptime + readtime) ) )
     
     
          
          
          
          


def get_States(minerva, tel_phot_targets):
    '''
    For a given expected starttime, record all of the telescopes that want to observe at that time. Also, arrange the exp_starttimes in order (with their corresponding telescope(s) attached to that ordering)

    What if two different targets wanted to start being observed at the exact same expected starttime????
    -- Then I'd have to account for the 'name' of the target as well as its exp_starttime.


    Parameters
    ----------
    minerva: list

    tel_phot_targets: dictionary
                      The target schedule based on the telescope and then the index of observations (probably in chrono order, but I will not assume that)

    Return
    ------
    states_dict: dictionary

    '''

    '''
    Teles_starts = []
    Teles_used = []
    Teles_target_info = []
    
    for t_num in range(1,5):
        if 'T'+str(t_num) is tel_phot_targets.keys():
            good_tele = t_num
            break 
    '''
    
    Teles_starts = {}
    Teles_used = {}
    Teles_target_info = {}

    onePhot_tele = None
    for telescope in minerva.telescopes:
        if tel_phot_targets['T'+telescope.num] != None:
            onePhot_tele = int(telescope.num) #t_num += 1
            break
            #if good_tele > 4: print('No Photometry Scheduled for Tonight.')


    if onePhot_tele != None:
        #ipdb.set_trace()
        my_field_names = copy.copy(tel_phot_targets['T'+minerva.telescopes[onePhot_tele-1].num][0].keys()) # Any telescopes[index] (except the 'None' ones) and any ind_target should work
        my_field_names.pop( my_field_names.index('exp_starttime')  )

        all_starttimes = []
        phot_teles = []
        for telescope in minerva.telescopes:
            '''
            Teles_starts.append( [] )
            Teles_used.append( [] )
            Teles_target_info.append( [] )
            '''
            if tel_phot_targets['T'+telescope.num] == None: # no photometric targets at all for this telescope
                #Teles_starts['T'+telescope.num] = [None]
                #Teles_used['T'+telescope.num] = [None]
                #Teles_target_info['T'+telescope.num] = [None]
                pass
            
            else:

                Teles_target_info['T'+telescope.num] = {}
            
                Teles_starts['T'+telescope.num] = []
                for ind_target in xrange(len(tel_phot_targets['T'+telescope.num])):
                
                    Teles_starts['T'+telescope.num].append( tel_phot_targets['T'+telescope.num][ind_target]['exp_starttime'] )
                
                    # record all other original info
                    for title in my_field_names:
                        if ind_target == 0:  #if title not in Teles_target_info['T'+telescope.num].keys():  # this entire script currently depends on every telescope dictionary and each of their targets having the same titles/fields and number of titles/fields
                            Teles_target_info['T'+telescope.num][title] = []
                        
                        Teles_target_info['T'+telescope.num][title].append( tel_phot_targets['T'+telescope.num][ind_target][title] )

                        
                Teles_used['T'+telescope.num] = list(np.ones(len( Teles_starts['T'+telescope.num] ), dtype='int')*int(telescope.num)) # now that I use telescope.num, this might be unnecessarily redundant
                phot_teles += Teles_used['T'+telescope.num]
                all_starttimes += Teles_starts['T'+telescope.num]
                # Both all_starttimes and phot_teles are now lists that correspond to ALL (no matter the telescope) exp_starttimes                
            
            
        #all_starttimes = []
        #phot_teles = []
        #for tele_title in Teles_starts.keys():
              #all_starttimes += Teles_starts[tele_title] #all_starttimes = np.sum(Teles_starts)
              #phot_teles += Teles_used[tele_title] #np.sum(Teles_used)
              # Both all_starttimes and phot_teles are lists that correspond to ALL exp_starttimes
    
        # see if the summing trick works with a list of dictionaries (that contain the same fields/titles)
        fields = []
        for title in my_field_names:
            #ipdb.set_trace()
            if type(Teles_target_info['T'+minerva.telescopes[onePhot_tele-1].num][title][0])==list:
                fields.append([])
                for telescope in minerva.telescopes:
                    f= Teles_target_info['T'+minerva.telescopes[onePhot_tele-1].num][title]                    
                    fields[-1] +=f
            else:
                fields.append( list(np.concatenate( [ Teles_target_info['T'+telescope.num][title] for telescope in minerva.telescopes if tel_phot_targets['T'+telescope.num] != None ] )) )
            #fields.append([])
            #fields[-1] = np.concatenate([ Teles_target_info['T'+telescope.num][title] for telescope in minerva.telescopes if tel_phot_targets['T'+telescope.num] != None ])
            # Now every field has its own list that corresponds to ALL (no matter the telescope) exp_starttimes

        #single_starttimes = []
        #start_t_teles = []

        #single_fields = []
        all_tuples =[]

        # The different telescope dictionaries will def have the same exp_starttime for observing the same object.  Such duplicates should be accounted for.
        phot_teles = np.array(phot_teles)
        for s_time_ind in xrange(len(all_starttimes)):
            dup_inds = np.where( np.array(all_starttimes) == all_starttimes[s_time_ind] )[0]

            #phot_teles = np.array(phot_teles)
            if s_time_ind == dup_inds[0]: # if an exp_starttime has a multiplicity of 1, then go. if an exp_starttime has a multiplicity > 1 but this is the first time is has occurred in the FOR loop, then go.
                # record telescope(s) with corresponding time
                #single_starttimes.append( all_starttimes[s_time_ind] )
                #start_t_teles.append( list( phot_teles[dup_inds] ) ) # keep it in list format because the dynamic scheduler wants it that way
                single_fields = []
                for field_ind in xrange(len(fields)):
                    #single_fields.append([])
                    #single_fields[field_ind].append( fields[field_ind][dup_inds] )
                    fields[field_ind] = np.array(fields[field_ind])
                    single_fields.append( list( fields[field_ind][dup_inds] ) ) # shouldn't the same field from different telescopes (for the same exp_starttime) be the exact same value?  --- One exp_starttime could have overlapped with another telescope's exp_starttime for a different target.  Or two telescopes can be told to observe differenct phot objects simultaneously
                
                all_tuples.append( tuple( [ all_starttimes[s_time_ind], list(phot_teles[dup_inds]) ]+single_fields ) )
            else:
                pass

        # Arrange in chronological order
    
        prep_formats = []
        for field_ind in xrange(len(all_tuples[0])):
            dat_type = str(np.dtype(type( all_tuples[0][field_ind] )))
            if dat_type == '|S0': dat_type = '|S10'  # for some reason, numpy does not recognize the |S0 string format
            prep_formats.append( dat_type )
    
        #prep_array = np.array( all_tuples, dtype= { 'names': ['exp_starttimes','Telescope_lists']+my_field_names,'formats': [datetime.datetime,'object'] } )
        prep_array = np.array( all_tuples, dtype= { 'names': ['exp_starttime','Teles']+my_field_names,'formats': prep_formats } )
        sorted_array = np.sort( prep_array, order='exp_starttime' )

        states_dict = {}
    
        # IF the very first 'exp_starttime' is after minerva.site.NautTwilEnd() then make the first state at that time.
        # IF the very last 'exp_endtime' is after minerva.site.NautTwilBegin() then make the last state at that time.
        if sorted_array['exp_starttime'][0] > minerva.site.NautTwilEnd():  # Won't it always find the very next sunset and not the one that I truly want ???? -- NO.  Because of the minerva object, it will always get the closest, most relevant twilight ending or beginning
            states_dict['exp_starttime'] = [ minerva.site.NautTwilEnd() ]
            for title in ['Teles']+my_field_names:
                states_dict[title] = [None] # if this [None] were a variable, you would want to use copy.copy
        
        for title in ['exp_starttime','Teles']+my_field_names: #sorted_array.dtype.names:
        
            try: # possibly because of the NautTwilEnd condition
                states_dict[title] += list( sorted_array[title] )
            except KeyError:
                states_dict[title] = list( sorted_array[title] ) # command what may be a list to be a list does not change anything. 
            
            
        '''
        if sorted_array['exp_endtime'][-1] < minerva.site.NautTwilBegin():
            states_dict['exp_endtime'].append( minerva.site.NautTwilBegin() )
            for title in ['exp_starttime','Teles']+my_field_names:
                if title == 'exp_endtime':
                    pass
                else:
                    states_dict[title].append( None )
        '''

    else: # No telescopes have a phot schedule for tonight

        states_dict = {}
        #states_dict['exp_starttime'] = [ Night_boundary for Night_boundary in [minerva.site.NautTwilEnd(), minerva.site.NautTwilBegin()] ]
        #states_dict['Teles'] = [None, None]
        states_dict['exp_starttime'] = [minerva.site.NautTwilEnd()]
        states_dict['Teles'] = [None]
        
    # Caveats:
    # 1) Every phot target must have the same fields filled out in their dictionaries.

                
    return states_dict 




def omniObserve(minerva, states):
    '''
    Start all observations.
    
    Parameters
    ----------


    Return
    ------

    '''

    for state_ind in xrange(len(states['exp_starttime'])):

        threads = []

        phot_teles_num = copy.copy( states['Teles'][state_ind] ) #list(np.where( states['Teles'][state_ind] == 1 )[0] + 1 )
        rv_teles_num = []
        for telescope in minerva.telescopes: rv_teles_num.append(int(telescope.num))
        
        if phot_teles_num == None: 
            pass
        
        else:
            #   call the " self.doScience(target,telescope_num) "
            phot_target_teles = {}
            for title in states.keys():  
                phot_target_teles[title] = states[title][state_ind] #dict_names[ states['name'][target_ind] ] 
                
                    
            phot_target={}
            counter = 0
            for tele in phot_teles_num:
                for title in states.keys(): 
                    if title !="exp_starttime": 
                        phot_target[title] = phot_target_teles[title][counter]
                    else:
                        phot_target[title] = phot_target_teles[title]

                counter+=1 # index for the telescopes
                threads.append( threading.Thread( target = minerva.doScience, args = (phot_target, tele) ))
                threads[-1].name = 'Phot_Obs_'+str(tele)
                threads[-1].start()

            for tel in phot_teles_num: rv_teles_num.pop( rv_teles_num.index(tel) )
            '''
                try:
                    rv_teles_num.pop( rv_teles_num.index(tel) ) #list( np.where( states['Teles'][target_ind] == 0 )[0] + 1 )
                except ValueError:
                    pass
            '''
            
        if state_ind < len(states['exp_starttime'])-1:
            #reacher = datetime.datetime.utcnow
            #state_index = state_ind + 1
            time_thresh = states['exp_starttime'][state_ind + 1]
            
        elif state_ind == len(states['exp_starttime'])-1:
            #reacher = datetime.datetime.utcnow
            time_thresh = minerva.site.NautTwilBegin()
            #state_index = state_ind
            
        minerva.logger.info('Beginning nightly loop')
        remaining_time = (time_thresh - datetime.datetime.utcnow()).seconds
#        while  time_thresh > datetime.datetime.utcnow():
        while remaining_time > 0.0:
            
            # check the time remaining before the next state change and know which telescope(s) will operate then
            minerva.logger.info('Time left in the night ' + str(remaining_time) + ' seconds')            

            t_names = [threads[p].name for p in xrange(len(threads))]

            if len(minerva.telescopes) != len(rv_teles_num) and 'RV_Obs' in t_names:
                minerva.logger.info("All telescopes (" + str(len(minerva.telescopes)) + ") are requested for RV; skipping photometry")
            else:
                # tell the dynamic scheduler the remaining time gap and free telescopes
                RV_target =  minerva.scheduler.choose_target(remaining_time=remaining_time,logger=minerva.logger)#dynamicSched(rv_teles_num, remaining_time)

                # Figure out the error result for the dynamicSched function
                if len(RV_target) > 0:
                    minerva.logger.info('Taking spectrum of ' + RV_target['name'])

                    #break
        
                    # CALL RV observation
                    # The remaining telescopes will always collect RVs on the same target
                    threads.append( threading.Thread( target = rv_control.doSpectra, args = (minerva,RV_target,rv_teles_num) ))
                    threads[-1].name = 'RV_Obs'
                    threads[-1].start()
                    minerva.logger.info('RV thread is activated.')
                else:
                    minerva.logger.info("The scheduler did not return any viable RV targets")


            # If the phot thread is dead then break this while loop; but do it gently and wait until the current dynamic RV!!
            for telescope in minerva.telescopes:
                if 'Phot_Obs_'+telescope.num in t_names:

                    #while #threads[1].isAlive(): 
            
                    if threads[np.where(np.array(t_names)=='Phot_Obs_'+telescope.num)[0][0]].isAlive() == True:
                        #status = 'alive' 
                        pass
                    else:
                        #status = 'dead'    
                        minerva.logger.info('Photometry T'+telescope.num+' thread is now dead.')
                        #while threads[0].isAlive():
                        threads.pop( np.where(np.array(t_names)=='Phot_Obs_'+telescope.num)[0][0] )
                            
            time.sleep(1)
                        
            minerva.logger.info('Waiting for telescope threads to finish')
            for p in xrange(len(threads)):
                threads[p].join()

        
            remaining_time = (time_thresh - datetime.datetime.utcnow()).seconds

    
    return






if __name__ == '__main__':  # do a bunch of threading stuff


    base_directory = '/home/minerva/minerva-control'
    minerva = control.control('control.ini',base_directory)

    threads = []

    for tele in minerva.telescopes:
        # Prep for Night
        telescope_num = int(tele.num)  

        telescope_name = 'T' + str(telescope_num) +': '
    
        if telescope_num < 1 or telescope_num > 4:
            minerva.logger.error(telescope_name + 'invalid telescope index')
            sys.exit()  
    
        #set up night's directory
        minerva.prepNight(telescope_num)
        minerva.scheduleIsValid(telescope_num, email=True)
    
        telescope = utils.getTelescope(minerva,telescope_num)
        camera = utils.getCamera(minerva,telescope_num)

        # Setup tech thread
        threads.append(  threading.Thread( target = SetupTech, args=(minerva, telescope, camera, telescope_num) ) )
        threads[-1].name = 'SetupTech_'+str(telescope_num)
        threads[-1].start()
        
        # End FOR loop

    # Wait until all threads are done because if this telescope's homing is not complete, 
    # then the skyflats thread (which checks to see if the homing is complete)
    # will try to home the telescope if it sees that it is not done homing.  
    # This makes 2 functions trying to home the telescope at the same time. 
    for p in np.arange(len(threads)):
        threads[p].join()

    threads=[]

    # Spectroscopic Calibration

    # if before the end of twilight, do calibrations
    if datetime.datetime.utcnow() < minerva.site.NautTwilEnd():
        rv_control.backlight(minerva)
         
        # by default, checkiftime = True. This is just here as a reminder
        kwargs ={'checkiftime': True}
        threads.append( threading.Thread( target = minerva.specCalib, args=(),kwargs=kwargs ) )
        threads[-1].name = 'SpecCalib'
        threads[-1].start()


    for tele in minerva.telescopes:

        telescope_num = int(tele.num)
        telescope = utils.getTelescope(minerva,telescope_num)  
        CalibInfo,CalibEndInfo = minerva.loadCalibInfo(telescope_num)

        if CalibInfo != None and CalibEndInfo !=None:

            # Photometry Calibration thread
            if datetime.datetime.utcnow() < minerva.site.NautTwilEnd():

                # by default, checkiftime = True. This is just here as a reminder
                kwargs = {'checkiftime':True}
                threads.append(  threading.Thread( target = PhotCalib, args=(minerva, CalibInfo, telescope_num), kwargs=kwargs ) )
                threads[-1].name = 'PhotCalib_'+str(telescope_num)
                threads[-1].start()                  
        

    for p in np.arange(len(threads)):
        threads[p].join()

    # Now do Domes and Skyflats
    threads=[]
    for tele in minerva.telescopes:

        telescope_num = int(tele.num)

        telescope = utils.getTelescope(minerva,telescope_num)  # the variable telescope changes

        CalibInfo,CalibEndInfo = minerva.loadCalibInfo(telescope_num)

        # Prepare Domes before taking Sky flats
        if telescope_num > 2: dome = minerva.domes[1]
        else: dome = minerva.domes[0]
 
        sunfile = minerva.base_directory + '/minerva_library/sunOverride.txt'
        if os.path.exists(sunfile): os.remove(sunfile)

        with open(minerva.base_directory + '/minerva_library/aqawan1.request.txt','w') as fh:
            fh.write(str(datetime.datetime.utcnow()))

        with open(minerva.base_directory + '/minerva_library/aqawan2.request.txt','w') as fh:
            fh.write(str(datetime.datetime.utcnow()))

        if CalibInfo != None and CalibEndInfo != None:
            if datetime.datetime.utcnow() < minerva.site.NautTwilEnd():
                # Skyflats thread
                threads.append(  threading.Thread( target = startSkyFlats, args=(minerva, telescope, dome, CalibInfo, telescope_num) ) )
                threads[-1].name = 'SkyFlats_'+str(telescope_num)
                threads[-1].start()                  
     
        # End FOR loop
        

    
    '''
 
    threads = [None] * len(minerva.telescopes) # 4 setup-procedures and phot calibs for telescopes 
    #  minerva.telescopes is a list of objects. Each object corresponds to one telescope.
    for telescope in minerva.telescopes:
        #print(type(telescope.num))
        p = int(telescope.num) - 1 # threads/processes
        threads[p] = threading.Thread( target = Setup_n_PCalib, args=(minerva, telescope.num) )  
        threads[p].name = 'T'+telescope.num+' Calib'
        threads[p].start()
    
          
    # Spectroscopic Calibrations
     
    # if before the end of twilight, do calibrations
    
    if datetime.datetime.utcnow() < minerva.site.NautTwilEnd():
        rv_control.backlight(minerva)
         
        threads.append( threading.Thread( target = minerva.specCalib, args=() ) )
        threads[-1].name = 'Spec Calib'
        threads[-1].start()
    '''
     # While calibrations (or waiting) is occurring, check the photometry target file for targets of current night.

       
     # The RV scheduler simply finds a target for a certain time period (or returns nothing)
       # the spontaneous schedule must end before the endtime of the photometric target
    
       
    tel_p_targets = {}
    for tele in minerva.telescopes:
        #tel_p_targets['T'+tele.num] = []
        try:
            with open(minerva.base_directory + '/schedule/' + minerva.site.night + '.T' + tele.num + '.txt', 'r') as targetfile:
                next(targetfile) # skip both calibration headers
                next(targetfile)

                p_targets = []
                for line in targetfile: # assume that the observations' starttimes are (kinda) already in chronological order
                    target = minerva.parseTarget(line) 
                    
                    if target <> -1:  # only works for Python 2
                        # truncate the start and end times so it's observable
                        target = utils.truncate_observable_window(minerva.site, target)
                             
                        # I am pretty sure that the target dictionary's start and end times are in datetime.datetime format now
                        
                        if target['starttime'] < target['endtime']:
                            p_targets.append( target )
                            # starttime and endtime only represent when the object is observable
                                  
                             
                #tel_p_targets['T'+tele.num].append( p_targets )
                tel_p_targets['T'+tele.num] = p_targets
              
        except IOError: # there is no photometry target file
               
            # record the telescope so that when the night begins, the dynamic scheduler will know which telescope(s) are free
            tel_p_targets['T'+tele.num] =  None
               
# Even if there is a photometry schedule for a telescope, we may not want (or be able) to use that telescope so I don't include such a telescope in the dictionary

            
    # Calculate the duration times between photometry targets
    # Calculate the expected start and end times of the photometric observations
    #all_night = [None]*4
    for tele in minerva.telescopes: #for telescope_num in range(1,5)
        # check for photometry targets in the telescope target [list]
        if tel_p_targets['T'+tele.num] == None:
            # IF there is no photometry target, then record the time duration of the night for this specific telescope ... maybe
            #all_night[telescope_num-1] = True #[minerva.site.NautTwilEnd() - Morning]
            pass
        else:
            #all_night[telescope_num-1] = False
               
            for ind_target in xrange(len(tel_p_targets['T'+tele.num])):
                p_target = tel_p_targets['T'+tele.num][ind_target]  # without copy.copy, this ind_target dictionary will change whenever the p_target variable changes.  This only happens with one variable coupling at a time
                    
                if ind_target == 0:
                    
                    if p_target['starttime'] < minerva.site.NautTwilEnd(): # staying safe, but should not be necessary
                        p_target['exp_starttime'] = minerva.site.NautTwilEnd()
                        #p_target['prior_interval'] = datetime.timedelta(seconds = 0.0)  
                              
                    else:
                        p_target['exp_starttime'] = p_target['starttime']
                        #p_target['prior_interval'] = p_target['exp_starttime'] - minerva.site.NautTwilEnd() # only for the very 1st one do we not need the rdo_acq_sl, because no image has been taken yet

                        # Add expected endtime by accounting for the number of exposures, exposure time, filters, and acquisition
                        p_target['exp_endtime'] = p_target['exp_starttime'] + Acq_Exp_RdO(120.0, p_target, 7.0)

                        if p_target['exp_endtime'] > p_target['endtime']:
                            p_target['exp_endtime'] = p_target['endtime']

                        if p_target['exp_endtime'] > minerva.site.NautTwilBegin(): # if the exp_endtime is later than sunrise
                            p_target['exp_endtime'] = minerva.site.NautTwilBegin()
                         
                else:

                    # check previous expected endtime, if that overlaps with the current starttime then create expected starttime in target's dictionary
                    if p_target['starttime'] <= tel_p_targets['T'+tele.num][ind_target-1]['exp_endtime']:

                        p_target['exp_starttime'] = tel_p_targets['T'+tele.num][ind_target-1]['exp_endtime'] # It is okay to overlap because of the specified acquisition time, and the computer won't start acquiring the next target until the first one is finished--even if I tell it to do so.
                        #p_target['prior_interval'] = datetime.timedelta(seconds = 0.0)
                              
                    else:
                        p_target['exp_starttime'] = p_target['starttime']
                        
                        #p_target['prior_interval'] = p_target['exp_starttime'] - tel_p_targets['T'+tele.num][ind_target-1]['exp_endtime']
                         
                    #tel_p_targets['T'+tele.num][ind_target-1]['post_interval'] = p_target['prior_interval']
                    
                    # After ascertaining expected starttime of this target, then determine expected endtime of this target---by accounting for duration ==  acquisition + np.sum( num*(exptime + readtime)  )
                    p_target['exp_endtime'] = p_target['exp_starttime'] + Acq_Exp_RdO(120.0, p_target, 7.0)

                    if p_target['exp_endtime'] > p_target['endtime']:
                        p_target['exp_endtime'] = p_target['endtime']

                    if p_target['exp_endtime'] > minerva.site.NautTwilBegin(): # if the exp_endtime is later than sunrise
                        p_target['exp_endtime'] = minerva.site.NautTwilBegin()

                            
                    #if ind_target == len(tel_p_targets['T'+tele.num][ind_target] ) -1: # we're at the last element
                        #p_target['post_interval'] = minerva.site.NautTwilBegin() - p_target['exp_endtime'] 

                              
                #tel_p_targets['T'+tele.num][ind_target] = p_target  # the updated dictionary is placed back in the list  # This should be unnecessary because I did not use copy.copy

                    
    # Get the states of change
    chrono_states = get_States(minerva, tel_p_targets)

    
    # Wait for the sky flats to finish
    for p in np.arange(len(threads)):
        threads[p].join()
         
    omniObserve(minerva, chrono_states)
    
    for tele in minerva.telescopes: minerva.endNight(num=int(tele.num),kiwispec=True)
