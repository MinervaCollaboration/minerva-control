import threading
import control
import mail
import ipdb
import datetime
import sys
import ephem

def rv_observing(minerva):

    # python bug work around -- strptime not thread safe. Must call this once before starting threads    
    junk = datetime.datetime.strptime('2000-01-01 00:00:00','%Y-%m-%d %H:%M:%S')

    minerva.domeControlThread()
    minerva.telescope_initialize(tracking=False,derotate=False)
    minerva.telescope_park()


    with open(minerva.base_directory + '/schedule/' + minerva.site.night + '.kiwispec.txt', 'r') as targetfile:
        for line in targetfile:
            target = minerva.parseTarget(line)
            if target <> -1:
                # check if the end is after morning twilight begins                                                                                                        
                if target['endtime'] > minerva.site.NautTwilBegin():
                    target['endtime'] = minerva.site.NautTwilBegin()
                    # check if the start is after evening twilight ends                                                                                                        
                    if target['starttime'] < minerva.site.NautTwilEnd():
                        target['starttime'] = minerva.site.NautTwilEnd()

                        # compute the rise/set times of the target
                        #S I think something with coordinates is screwing us up here                                                                                               
                        #S We are still going below 20 degrees.                                                                                                                    
                        minerva.site.obs.horizon = '21.0'
                        body = ephem.FixedBody()
                        body._ra = str(target['ra'])
                        body._dec = str(target['dec'])
                        #S using UTC now for the epoch, shouldn't make a siginificant                                                                                              
                        #S difference from using local time                                                                                                                        
                        body._epoch = datetime.datetime.utcnow()
                        body.compute()
                        
                        try:
                            risetime = minerva.site.obs.next_rising(body,start=minerva.site.NautTwilEnd()).datetime()
                        except ephem.AlwaysUpError:
                            # if it's always up, don't modify the start time                                                                                                   
                            risetime = target['starttime']
                        except ephem.NeverUpError:
                            # if it's never up, skip the target                                                                                                                
                            risetime = target['endtime']
                        try:
                            settime = minerva.site.obs.next_setting(body,start=minerva.site.NautTwilEnd()).datetime()
                        except ephem.AlwaysUpError:
                            # if it's always up, don't modify the end time                                                                                                     
                            settime = target['endtime']
                        except ephem.NeverUpError:
                            # if it's never up, skip the target                                                                                                                
                            settime = target['starttime']

                        if risetime > settime:
                            try:
                                risetime = minerva.site.obs.next_rising(body,start=minerva.site.NautTwilEnd()-datetime.timedelta(days=1)).datetime()
                            except ephem.AlwaysUpError:
                                # if it's always up, don't modify the start time
                                risetime = target['starttime']
                            except ephem.NeverUpError:
                                # if it's never up, skip the target
                                risetime = target['endtime']

                        # make sure the target is always above the horizon
                        if target['starttime'] < risetime:
                            target['starttime'] = risetime
                        if target['endtime'] > settime:
                            target['endtime'] = settime

                        if target['starttime'] < target['endtime']:
                            minerva.doSpectra(target,[1,2,3,4])
                            minerva.logger.info(target['name']+ ' not observable; skipping')

def backlight(minerva, tele_list=0, fauexptime=150.0, stagepos=None, name='backlight'):

    #S check if tele_list is only an int                                                                                                
    if type(tele_list) is int:
        #S Catch to default a zero arguement or outside array range tele_list                                                       
        #S and if so make it default to controling all telescopes.                                                       
        if (tele_list < 1) or (tele_list > len(minerva.telescopes)):
            #S This is a list of numbers fron 1 to the number scopes                                                            
            tele_list = [x+1 for x in range(len(minerva.telescopes))]
        #S If it is in the range of telescopes, we'll put in a list to                                                              
        #S avoid accessing issues later on.                                                                                         
        else:
            tele_list = [tele_list]

    #S Zero index the tele_list                                                                                                         
    tele_list = [x-1 for x in tele_list]

    # move the iodine stage to the best position for backlighting
    if stagepos == None:
        kwargs = {'locationstr' : 'backlight'}
        threads = [threading.Thread(target=minerva.ctrl_i2stage_move,kwargs=kwargs)]
    else:
        kwargs = {'position':stagepos}
        threads = [threading.Thread(target=minerva.ctrl_i2stage_move,kwargs=kwargs)]
        

    # turn on the slit flat LED
    minerva.spectrograph.led_turn_on()

    # swap to the imaging port to block light from the telescope
    for i in range(len(tele_list)):
        threads.append(threading.Thread(target=minerva.telescopes[tele_list[i]].m3port_switch,
                                        args=[minerva.telescopes[tele_list[i]].port['IMAGER'],]))

    # execute long commands asynchronously
    for thread in threads:
        thread.start()

    # wait for everything to complete
    for thread in threads:
        thread.join()

    # take an exposure with the spectrograph (to trigger the LED)
    kwargs = {'expmeter':None,"exptime":fauexptime+30,"objname":"backlight"}
    spectrum_thread = threading.Thread(target=minerva.spectrograph.take_image, kwargs=kwargs)
    spectrum_thread.start()

    # take images with all FAUs
    fau_threads = []
    for i in range(len(tele_list)):
        kwargs = {'telescope_num':int(minerva.telescopes[tele_list[i]].num)}
        target = {
            'name':name,
            'fauexptime':fauexptime,
            }
        fau_threads.append(threading.Thread(target=minerva.takeFauImage,args=[target,],kwargs=kwargs)) 

    print "starting all FAU images"
    for fau_thread in fau_threads:
        fau_thread.start()
    print "started all FAU images"

    # wait for all fau images to complete
    for fau_thread in fau_threads:
        fau_thread.join()

    # wait for spectrum to complete
    spectrum_thread.join()
    
    # turn off the slit flat LED
    minerva.spectrograph.led_turn_off()

    print "done with backlit images"
    
    #minerva.takeFauImage({'name':'backlight','fauexptime':1},telescope_num=1)
    
def rv_observing_catch(minerva):
    try:
        rv_observing(minerva)
    except Exception as e:
        minerva.logger.exception('rv_observing thread died: ' + str(e.message) )
        body = "Dear benevolent humans,\n\n" + \
            'I have encountered an unhandled exception which has killed the specCalib control thread. The error message is:\n\n' + \
            str(e.message) + "\n\n" + \
            "Check control.log for additional information. Please investigate, consider adding additional error handling, and restart 'main.py\n\n'" + \
            "Love,\n" + \
            "MINERVA"
        mail.send("rv_observing thread died",body,level='serious')
        sys.exit()

def fiber_stability(minerva):
    # evaluate stability as a function of alt/az/rotation
    for rotang in range(0,360,10):

        threads = []
        for telescope in minerva.telescopes():
            threads.append(threading.Thread(target=telescope.rotatorMove,args=[rotang,]))
        for thread in threads:
            thread.start()
            
        # now slew in alt/az
        for alt in range(21,84,15):
            for az in range(0,270,90):
                
                minerva.telescope_mountGotoAltAz(alt,az)

                # wait for telescopes to get in position
                for telescope in minerva.telescopes():
                    while not telescope.inPosition(alt=alt,az=az):
                        time.sleep(1)
                
                backlight(minerva)

if __name__ == "__main__":

    minerva = control.control('control.ini','/home/minerva/minerva-control')
    minerva.telescope_initialize(tracking=False,derotate=False)
    minerva.telescope_park()


    ipdb.set_trace()
    fiber_stability(minerva)

#    # figure out the optimal stage position for i2 stage during backlighting (81 mm)
#    for i in range(20):
#        backlight(minerva,stagepos=73.0 + float(i), name='backlight' + str(int(73.0 + float(i))))



                



