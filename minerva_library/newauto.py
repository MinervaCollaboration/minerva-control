import numpy as np
import matplotlib.pyplot as plt
import subprocess
import scipy
import scipy.optimize
import ipdb
import warnings
import utils
import datetime
import time
import mail
import math
import copy
import glob

#S A custom exception class, so we can catch the results of fits on a case by 
#S case basis.
class afException(Exception):
    def __init__(self,message='Autofocus Exception',focus=0.0,coeffs=None):
        self.message = message
        self.focus = focus
        self.coeffs = coeffs


#S Simple function for plotting results in a record file
#S also does a fit, etc..
#S Now used in making plots for emails
def recordplot(recordfile,step=1,saveplot=False):
    #S get the data from the autorecord
    raw_data = np.genfromtxt(recordfile,skip_header=5)
    imnlist = raw_data[::step,0].astype(int)
    poslist = raw_data[::step,1].astype(float)
    hfrlist = raw_data[::step,2].astype(float)
    stdlist = raw_data[::step,3].astype(float)
    numlist = raw_data[::step,4].astype(float)

    #S identify the good points, those were an hfr was found
    goodind = np.where(hfrlist<>-999)[0]

    #S if there were no good points
    if len(goodind) == 0:
        print 'Nothing good in that record, try something better!'
        return None

    #S try and fit the point, else return the found coefficients
    try:
        focus,coeffs = fitquadfindmin(poslist[goodind],hfrlist[goodind],
                                      stdlist[goodind]*\
                                          np.sqrt(numlist[goodind]))
    except afException as e:
        coeffs = e.coeffs

    #S make the x-values to evaluate the fit at for plotting. 
    xplot = np.linspace(poslist.min(),poslist.max(),100)
    #S some printing, not necessary at all but makes info easier
    print 'Only plotting points with found hfradii'
    print 'Coeffs:' 
    print coeffs
    print 'Focus:'
    print focus

    #S init the figure
    fig = plt.figure()
    ax = fig.add_subplot(1,1,1)
    ax.plot(poslist[goodind],hfrlist[goodind],'b.')

    #S If using a port2 autorecord, the errors are fake. We don't want to 
    #S plot bars for those errors, and this will also allow us to avoid 
    #S hitting anything in the 
    if recordfile.split('/')[4].split('.')[3] != 'port2':
        ax.errorbar(poslist[goodind],hfrlist[goodind],stdlist[goodind],\
                         linestyle='None')
    ax.plot(xplot,quad(xplot,coeffs),'g')
    ax.set_xlabel('Focuser Position [$\mu$m]')
    ax.set_ylabel('Half Flux Radius [arcsec]')

    if saveplot:
        #S make the path and file name from the autorecord name and path
        rfilesp = recordfile.split('/')
        fnamesp = rfilesp[4].split('.')
        path = '/%s/%s/%s/'%(rfilesp[1],rfilesp[2],rfilesp[3])
        fname = '%s.%s.%s.%s.%s.%s.png'%(fnamesp[0],fnamesp[1],'afplot',\
                                             fnamesp[3],fnamesp[5],fnamesp[6])
        #S save the actual plot
        plt.savefig(path+fname)
        #S return path for email attachment, whatever else you need
        return path+fname
    
    #S just show it if we aren't saving
    plt.show()
    plt.close(fig)
    print 'leaving recordplot()'


def quad(x,c):
    return c[0]*x**2+c[1]*x+c[2]
    
#S Want to use new utils.readsexcat()
#S want to look at multiple images of one focus for FAU focusing potentially
def new_get_hfr(catfile,fau=False,telescope=None,min_stars=10,ellip_lim=.8):
    #S get a dictionary containg the columns of a sextracted image
    cata = utils.readsexcat(catfile)

    if not ('FLUX_RADIUS' in cata.keys()):
        telescope.logger.exception('No hfr in '+catfile)
        raise Exception()

    if len(cata['FLUX_RADIUS']) == 0:
        telescope.logger.error('No stars in image')
        raise Exception()

    if not ('A_IMAGE' in cata.keys() and 'B_IMAGE' in cata.keys()):
        telescope.logger.error('No major/minor axes in '+catfile)
        circ_ind = []
        raise Exception()
    else:
        circ_ind = np.where((cata['A_IMAGE']/cata['B_IMAGE'])>ellip_lim)[0]
    
    #S Want to catch if the stars are too elliptical
    if len(circ_ind) == 0:
        telescope.logger.error("Stars are too elliptical, can't use "+catfile)
        raise Exception
    #S If we expect only one or two stars from the FAU guide camera
    if fau:
        #S seems stupid... and probably is considering we'll be detecting 
        #S ghosts. might want to just get brightest object radius
#        hfr_med = np.median(cata['FLUX_RADIUS'][circ_ind])

        #S Lots of brackets to put these in a list, sorry about that.
        hfr_med = cata['FLUX_RADIUS'][cata['FLUX_ISO'].argmax()]
        hfr_std = 1.
        numstars = 1.
        
    #S if we expect an imager image with more than ten stars
    elif len(circ_ind>min_stars):
        try:
            hfr_med = np.median(cata['FLUX_RADIUS'][circ_ind])
        except:
            raise Exception()
#            raise afException(message='Could not get median value in '\
#                                  +catfile)


        try:
            numstars = len(circ_ind)
            #S Get the Median Absolute Deviation, and we'll convert to 
            #S stddev then stddev of the mean
            hfr_mad = np.median(np.absolute(\
                    cata['FLUX_RADIUS'][circ_ind]\
                        -np.median(cata['FLUX_RADIUS'][circ_ind])))
            #S We assume that our distribution is normal, and convert to 
            #S stddev. May need to think more 
            #S about this, as it isn't probably normal. 
            #S Recall stddev of the mean = stddev/sqrt(N)
            hfr_std = (hfr_mad*1.4862)/np.sqrt(numstars)
        except: 
            raise Exception()
#            raise afException(message='Could not get HFR_STD')

    return hfr_med, hfr_std, numstars

def fitquadfindmin(poslist, fwhmlist, weight_list=None,logger=None,
	telescope_num=99):
    
    #S if given a list of stadard deviations, we need to do the inverse of 
    #S that for the wieght in np.polyfit per the documentation it minimizes 
    #S sum(w**2(y-y_mod)**2), where w is the weight provided.
    if len(np.where(weight_list==0.)[0])>0:
        weight_list = None
    if type(weight_list) != type(None):
        stdlist = weight_list.copy()
        weight_list = np.sqrt(np.sqrt(1/np.array(weight_list)))
    # analytically fit a quadratic
    #S this is fine if w=None, as that is the default for the kwarg
    #S here is just an initializiation of an array for the old coeffs
    oldcoeffs = np.array([0.,0.,0.])
    #S actually fit a quadratic, using the entire set of data
    coeffs = np.polyfit(poslist,fwhmlist,2,w=weight_list)
    #S evaulate the fit at the given focuser positions
    quad = coeffs[0]*poslist**2 + coeffs[1]*poslist + coeffs[2]
    #S find the standard deviation of the residuals

    std = np.std(fwhmlist-quad)
    #S create a set of indices where the residuals are greater than 3sigma
    fwhmnp = np.array(fwhmlist)
    quadnp = np.array(quad)
    inds = np.where(np.absolute(fwhmnp-quadnp) < 3.*std)[0]
    #S initialize the iteration couter
    iters = 0
    if type(logger)!=type(None):
        logger.debug('T'+str(telescope_num)+': Starting sigma clipping for'\
                         +' autofocus fit.')
    #S see if the old coefficients are the same and if iters is below the max
    #S we enter this loop at least once, but probably don't need to refit.
    #TODO think of better ways to do this? not that important right now.

    while not (oldcoeffs == coeffs).all() and iters<10:
        print 'fitting '+ str(len(inds))
        #S set the old to the new
        oldcoeffs = coeffs.copy()
        #S get the new
       # if weight_list != None:
        coeffs = np.polyfit(poslist[inds],fwhmnp[inds],2,w=weight_list[inds])
       # else:
       #   coeffs = np.polyfit(poslist[inds],fwhmnp[inds],2)
        #S evaluate quad with new coeffs
        quad = coeffs[0]*poslist**2 + coeffs[1]*poslist + coeffs[2]
        #S find the std of the residuals
        std = np.std(fwhmnp[inds]-quadnp[inds])
        #S redefine the indices where the residuals are greater than 3sigma. 
        #S this should catch all points that were previously excluded. 
        fwhmnp = np.asarray(fwhmlist)
        quadnp = np.asarray (quad)
        inds = np.where(np.absolute(fwhmnp-quadnp) < 3.*std)[0]
#        inds = np.where(np.absolute(fwhmnp-quadnp) < 20.*stdlist)[0]
        #S increase the iterations
        iters += 1

    if iters > 9:
        print "couldn't fit"
        return None, coeffs

    # if the best fit was a downward facing parabola, it was bad
    #S For most of these I return None, None if there was no input logger, 
    #S which is a way of saying exceptions need to handled by any other call
    #S except for those from control.autofocus
    if coeffs[0] <= 0.0: 
        #S Check if our fit was upside down
        if type(logger)!=type(None):
            #S going to return where the maximum is, so that we can decide to 
            #S add more points on the opposite side. 
            logger.error('T'+str(telescope_num)+': Autofocus fit upside down'\
                             +'quadratic (or a line), something funky.')
#            maximum = int(-coeffs[1]/(2.0*coeffs[0]))
            raise afException('NoMinimum_Exception',None,coeffs)
        else:
            return None, coeffs

    # solve for minimum (derivative = 0), and convert to an integer
    best_focus = int(-coeffs[1]/(2.0*coeffs[0]))
 
    # don't allow it to go beyond the limits
    if best_focus <= min(poslist):
        #S log that we were out of range
        if type(logger)!=type(None):
            logger.error('T'+str(telescope_num)+': New best focus was below '\
                         +'lower limit.')
            #S we return exceptions now so it can be caught in calling routine
            raise afException('LowerLimit_Exception',None,coeffs)
        else:
            return best_focus, coeffs
        #return None
        best_focus = min(poslist)
    if best_focus >= max(poslist):
        #S log that we were out of range
        if type(logger)!=type(None):
            logger.error('T'+str(telescope_num)+': New best focus was above'\
                             +' upper limit.')
            #S Same as above
            raise afException('UpperLimit_Exception',None,coeffs)
        else:
            return best_focus, coeffs
    #S Return coeffs for extra output to any other function besides control
    return best_focus, coeffs

def autofocus_step(control,telescope,newfocus,af_target):
    
    status = telescope.getStatus()
    m3port = status.m3.port

    if not telescope.focuserMoveAndWait(newfocus,port=m3port):
        telescope.recoverFocuser(newfocus,m3port)

    if af_target['spectroscopy']:
        imagename = control.takeFauImage(af_target,telescope_num=\
                                             int(telescope.num))
    else:
        imagename = control.takeImage(af_target,telescope_num=\
                                          int(telescope.num))
    
    # default (bad) values
    # will be overwritten by good values or serve as flags later
    median = -999
    stddev = 999
    numstar = 0

    try: 
        imnum = imagename.split('.')[4]
    except: 
        telescope.logger.exception('Failed to save image')
        imnum = '9999'
        return median,stddev,numstar,imnum

    
    datapath = '/Data/t' + telescope.num + '/' + control.site.night + '/'
    catalog = '.'.join(imagename.split('.')[0:-2]) + '.cat'
    
    #S Sextract this guy, put in a try just in case. Defaults should
    #S be fine, which are set in newauto. NOt sextrator defaults
    try:
        catalog = utils.sextract(datapath,imagename)
        telescope.logger.debug('Sextractor success on '+catalog)
    except:
        telescope.logger.exception('Sextractor failed on '+catalog)  
        return median,stddev,numstar,imnum
    
    try:
        median,stddev,numstar=new_get_hfr(
            catalog,telescope=telescope,fau=af_target['spectroscopy'])
        telescope.logger.info('Got hfr value from '+ catalog)
    except:
        telescope.logger.exception('Failed to get hfr value from '+catalog)

    return median,stddev,numstar,imnum


#S the new autofocus with variable steps. borrowing heavily from standard 
#S autofocus
def new_autofocus(control,telescope_number,num_steps=10,defocus_step=300.,\
                  target=None,dome_override=False):

    #S get the telescope we plan on working with, now redundant
    telescope = control.telescopes[telescope_number-1]

    #S Define/make sure we have a target
    if target != None:
        af_target = copy.deepcopy(target)
        af_target['name'] = 'autofocus'
        # select the appropriate port (default to imager)
        if 'spectroscopy' in af_target.keys():
            if af_target['spectroscopy']:
                m3port = telescope.port['FAU']
            else:
                m3port = telescope.port['IMAGER']
        else:
            m3port = telescope.port['IMAGER']                
            af_target['spectroscopy'] = False

    else:
        af_target = {'name':'autofocus',
                     'exptime':[5],
                     'fauexptime':10,
                     'filter':["V"],
                     'spectroscopy':False}
        m3port = telescope.port['IMAGER']

    #S Initialize telescope, we want tracking ON
    if not telescope.isInitialized(tracking=True,derotate=\
                                       (not af_target['spectroscopy'])):
        if not telescope.initialize(tracking=True,derotate=\
                                        (not af_target['spectroscopy'])):
            telescope.recover(tracking=True,derotate=\
                                  (not af_target['spectroscopy']))
        
    if 'ra' in af_target.keys() and 'dec' in af_target.keys():
        telescope.acquireTarget(af_target)
        #TODO Need to think about incorporating guiding for FAU

    else:
        telescope.logger.info('No ra and dec, using current position')

    #S our data path
    datapath = '/Data/t' + str(telescope_number) + '/' + \
        control.site.night + '/'

    #wait for dome to be open
    if telescope_number > 2:
        dome = control.domes[1]
    else:
        dome = control.domes[0]
    #S Get current time for measuring timeout
    t0 = datetime.datetime.utcnow()

    #S Loop to wait for dome to open, cancels after ten minutes
    while (not dome.isOpen()) and (not dome_override):
        telescope.logger.info('Enclosure closed; waiting for dome to open')
        timeelapsed = (datetime.datetime.utcnow()-t0).total_seconds()
        if timeelapsed > 600:
            telescope.logger.info('Enclosure still closed after '+\
                                    '10 minutes; skipping autofocus')
            return
        time.sleep(30)

    #S make array of af_defocus_steps
    initsteps = np.linspace(-defocus_step*(num_steps/2),\
                                defocus_step*(num_steps/2),num_steps)
    #S Array of new positions for the focuser, using this rahter than step.
    poslist = initsteps + telescope.focus[m3port]

    #S Just need an empty list for the fwhm/hfr and std to append to. made
    #S FOCUSMEASure_LIST because we don't necessarily know which value we want
    imagenum_list = []
    focusmeas_list = []
    stddev_list = []
    numstar_list = []

    #S while we don't have a good fit, probably want a condition on 
    #S number of steps and a timeout. 
#    while fit == False:
    
    #S do the intial num_steps to sample where we are in the focus range.
    #XXX what if there is no good initial fit? not enough succesful points?
    #S should we just try these same points again? that seems dumb.
    for step in initsteps:
        #S set the new focus, and move there if necessary
        newfocus = telescope.focus[m3port] + step

        #S take the image, get the values, do everything really.
        median,stddev,numstars,imnum = \
            autofocus_step(control,telescope_num,newfocus,af_target)
                                                          
        focusmeas_list.append(median)
        stddev_list.append(stddev)
        numstar_list.append(numstar)
        imagenum_list.append(imnum)

    DELTA_FOCUS = 101.
    MAXSTEPS = 15
    #S init old focus at zero, will be updated to newest value and should be
    #S fine from there
    old_best_focus = 0.

    #S while we have a sufficient shift in focus and are under the maxsteps
    while delta_focus < threshold:
        #try and fit quad, see where it finds the focus
        try:
            new_best_focus, focus_coeffs = fitquadfindmin()
            #S if we get a focus from fitquad, then we can calculate the 
            #S change of the focus
            delta_focus = np.abs(old_best_focus - new_best_focus)
            
        #S if we hit an afException, then use that information to add a new 
        #S afstep, in the direction that we are insuffcient
        except afEcxeption as e:
            #S Action if focus is below lower bound of step positions
            if e.message == 'LowerLimit_Exception':
                newfocus = poslit.min() - defocus_step
                np.append(poslist,newfocus)
                pass
            #S Action if focus is below upper bound of step positions
            if e.message == 'UpperLimit_Exception':
                pass
            #S Action if no minimum is found
            if e.message == 'NoMinimum_Exception':
                #idea: if we don't find a deep enough minimum or there isnt
                #S one, we might want to try again? we could find a very 
                #S shallow minimum even if there is no noticable change, or
                #S if the hfrs are flat. there could also be an issue if 
                #S we capture a wing where the focus levels off far from the 
                #S the actual focus, e.g. the shape of graph is something like:
                #        
                #           x x x   x x
                #         x       x
                # x     x
                #   x x
                pass
            #S run the autofocus step if we are still hitting the afExceptions, 
            #S probably want to continue and try and fit again after this.
            median,stddev,numstars,imnum = \
                autofocus_step(control,telescope_num,newfocus,af_target)
            
            focusmeas_list.append(median)
            stddev_list.append(stddev)
            numstar_list.append(numstar)
            imagenum_list.append(imnum)
            continue #???????????????????
        
        #S catch all other exceptions
        except:
            pass
        
        #S once we are getting a focus in the range we are testing, we can now 
        #S start refining to get below the threshold. 
        old_best_focus = new_best_focus
        
        #S find where most of our points are found
        points_below = len(np.where(poslist < new_best_focus)[0])
        points_above = len(np.where(poslist > new_best_focus)[0])
        
        #S if number of positions below focus is greater than those above, we 
        #S want to add some above the focus        
        if points_below > points_above:
            newfocus = poslit.max() + defocus_step
            np.append(poslist,newfocus)
            #S afstep for point one step above the current highest position
            pass

        #S same logic, but for below
        if points_below < points_above:
            newfocus = poslit.min() - defocus_step
            np.append(poslist,newfocus)
            pass

            pass
        median,stddev,numstars,imnum = \
            autofocus_step(control,telescope_num,newfocus,af_target)
        
        focusmeas_list.append(median)
        stddev_list.append(stddev)
        numstar_list.append(numstar)
        imagenum_list.append(imnum)
        continue #???????????????????????????


    print('Found a focus')
    #S declare victory, and do all the updates from current autofocus

            

def autofocus(control,telescope_number,num_steps=10,defocus_step=0.3,\
                  target=None,dome_override=False,simulate=False):

    telescope = utils.getTelescope(control,telescope_number)
    camera = utils.getCamera(control,telescope_number)
    dome = utils.getDome(control,telescope_number)
    
    
    #S Define/make sure we have a target
    if target != None:
        af_target = copy.deepcopy(target)
        af_target['name'] = 'autofocus'
        # select the appropriate port (default to imager)
        if 'spectroscopy' in af_target.keys():
            if af_target['spectroscopy']:
                m3port = telescope.port['FAU']
            else:
                m3port = telescope.port['IMAGER']
                af_target['exptime'] = 5
                af_target['filter'] = "V"
        else:
            m3port = telescope.port['IMAGER']                
            af_target['spectroscopy'] = False
            af_target['exptime'] = 5
            af_target['filter'] = "V"
            
    else:
        status = telescope.getStatus()
        m3port = status.m3.port
        if m3port == telescope.port['FAU']:
            spectroscopy = True
        else:
            spectroscopy = False
        af_target = {'name':'autofocus',
                     'exptime':5,
                     'fauexptime':10,
                     'filter':"V",
                     'spectroscopy':spectroscopy}
        
    #S set the platescale for the image
    if af_target['spectroscopy']:
        platescale = float(camera.fau.platescale)
    else:
        platescale = float(camera.platescale)
    #S Initialize telescope, we want tracking ON
    if 'tracking' in af_target.keys():
        tracking = af_target['tracking']
    else:
        tracking = True

    if not telescope.isInitialized(tracking=tracking,derotate=
                                   (not af_target['spectroscopy'])):
        if not telescope.initialize(tracking=tracking,derotate=\
                                        (not af_target['spectroscopy'])):
            telescope.recover(tracking=tracking,derotate=\
                                  (not af_target['spectroscopy']))
            
    if 'ra' in af_target.keys() and 'dec' in af_target.keys():
        telescope.acquireTarget(af_target,\
                                    derotate=(not af_target['spectroscopy']))
        #TODO Need to think about incorporating guiding for FAU
    else:
        telescope.logger.info('No ra and dec, using current position')

    # S our data path
    datapath = '/Data/t' + str(telescope_number) + '/' + \
        control.site.night + '/'


    # wait for dome to be open
    # S Get current time for measuring timeout
    t0 = datetime.datetime.utcnow()

    # we don't normally want to do an autofocus when the dome is closed, 
    # but we want to be able to test it during the day
    if not simulate:
        # S Loop to wait for dome to open, cancels after ten minutes
        while (not dome.isOpen()) and (not dome_override):
            telescope.logger.info('Enclosure closed; waiting for dome to open')
            timeelapsed = (datetime.datetime.utcnow()-t0).total_seconds()
            if timeelapsed > 600:
                telescope.logger.info('Enclosure still closed after '+\
                                    '10 minutes; skipping autofocus')
                return
            time.sleep(30)

    #S make array of af_defocus_steps
    defsteps = np.linspace(-defocus_step*(num_steps/2),\
                                defocus_step*(num_steps/2),num_steps)
    #S Array of new positions for the focuser, using this rahter than step.
    poslist = defsteps*1000 + telescope.focus[m3port]

    #S Just need an empty list for the fwhm/hfr and std to append to. made
    #S FOCUSMEASure_LIST because we don't necessarily know which value we want
    imagenum_list = []
    focusmeas_list = []
    stddev_list = []
    numstar_list = []

    for step in defsteps:
        #S set the new focus, and move there if necessary
        newfocus = telescope.focus[m3port] + step*1000.0
        status = telescope.getStatus()

        #S ensure we have the correct port
        telescope.m3port_switch(m3port)
        #S move and wait for focuser
        telescope.logger.info("Defocusing by " + str(step) + \
                                  " mm, to " + str(newfocus))

        median,stddev,numstars,imnum = autofocus_step(control,telescope,\
                                                          newfocus,af_target)
        imagenum_list.append(str(imnum))
        if median != -999:
            focusmeas_list.append(median*platescale)
            stddev_list.append(stddev)
        else:
            focusmeas_list.append(median)
            stddev_list.append(0)
#            focusmeas_list.append(median)

        numstar_list.append(numstars)
            
    #S define poslist from steps and the old best focus. this is an
    #S nparray
    poslist = defsteps*1000 + telescope.focus[m3port]
    #S Convert to array for ease of mind
    focusmeas_list = np.array(focusmeas_list)
    stddev_list = np.array(stddev_list)
    #S find the indices where we didnt hit an error getting a measure
    goodind = np.where(focusmeas_list <> -999)[0]


    #S This try is here to catch any errors/exceptions raised out of
    #S fitquad. I think we should include exceptions if we are too far
    #S out of focus, etc to make this catch whenever we didn't find a
    #S best focus.
    try:
        #S this is in place to catch us if all the images fail to get
        #S sextracted or something else goes on.
        #S probably a better way to do this, but we'll figure that out
        #S later.
        if len(goodind) == 0:
            telescope.logger.exception('Failed autofocus due to no medians')
            raise afException()
        #S find the best focus
        telescope.logger.debug('T'+str(telescope_number) +': fitting '+\
                                 'to '+str(len(goodind))+' points.')

        new_best_focus,fitcoeffs = fitquadfindmin(\
            poslist[goodind],focusmeas_list[goodind],\
                weight_list=stddev_list[goodind],\
                logger=telescope.logger,telescope_num=telescope_number)
        #S Log the best focus.
        telescope.logger.info('Found new best focus: ' + str(new_best_focus))

    except afException as e:
        #S if something went wrong, log and send email.
        new_best_focus = None
        coeffs=e.coeffs
        telescope.logger.exception('Failed in finding new focus')



    # want to record old best focus
    old_best_focus = telescope.focus[m3port]

    # if no sensible focus value measured, use the old value
    if new_best_focus == None: new_best_focus = old_best_focus
    
    # update the telescope focus
    telescope.focus[m3port] = new_best_focus
    # move to the best focus
    status = telescope.getStatus()
    if telescope.focus[m3port] <> status.focuser.position:
        control.logger.info('T'+str(telescope_number) + ": Moving focus to " +\
                                str(telescope.focus[m3port] + \
                                        telescope.focus_offset[m3port]))
        telescope.focuserMove(telescope.focus[m3port]+\
                                  telescope.focus_offset[m3port],port=m3port)
        # wait for focuser to finish moving
        time.sleep(0.5)
        status = telescope.getStatus()
        while status.focuser.moving == 'True':
            telescope.logger.info('Focuser moving'+\
                                      ' ('+str(status.focuser.position)+')')
            time.sleep(0.3)
            status = telescope.getStatus()

    # record values in the header
    try: alt = str(float(status.mount.alt_radian)*180.0/math.pi)
    except: alt = '-1'
    try: rotang = str(float(status.rotator.position))
    except: rotang = '720'
    try:    tm1 = str(status.temperature.primary)
    except: tm1 = 'UNKNOWN'
    try:    tm2 = str(status.temperature.secondary)
    except: tm2 = 'UNKNOWN'
    try:    tm3 = str(status.temperature.m3)
    except: tm3 = 'UNKNOWN'
    try:    tamb = str(status.temperature.ambient)
    except: tamb = 'UNKNOWN'
    try:    tback = str(status.temperature.backplate)
    except: tback = 'UNKNOWN'

    telescope.logger.info('Updating best focus for port '+str(m3port)+\
                            ' to '+str(telescope.focus[m3port])+' (TM1='+tm1 +\
                            ', TM2=' + tm2 + ', TM3=' + tm3 + ', Tamb=' + \
                            tamb + ', Tback=' + tback + ', alt=' + alt + ')' )

    with open('focus.' + telescope.logger_name + '.port'+\
                 m3port+'.txt','w') as fname:
        fname.write(str(telescope.focus[m3port]))

    telescope.logger.info('Finished autofocus')


    #S Record all the data to it's own run unique file for potential use
    #S later. Just don't want to be scraping through logs for it when we can
    #S just record it now.
    try:
        #S Check to make sure all the arrays are the same length and not zero.
        if len(imagenum_list)==len(poslist)==len(focusmeas_list)==\
                len(stddev_list)==len(numstar_list):
            #S Stack them all together, then transpose so we can write
            #S them in columns
#           ipdb.set_trace()
#           print imagenum_list,poslist,focusmeas_list,stddev_list,numstar_list
            autodata = np.vstack([imagenum_list,poslist,focusmeas_list,\
                                      stddev_list,numstar_list]).transpose()
            #S Name the data file as:
            #S 'nYYYYMMDD.T#.autorecord.port#.filter.AAAA.BBBB.txt',
            #S where AAAA is the image number on the first image of the
            #S autofocus sequence, and BBBB the last image number.
            datafile = control.site.night+'.T'+str(telescope_number)+\
                '.autorecord.port'+str(m3port)+'.'+af_target['filter'][0]+\
                '.'+imagenum_list[0]+'.'+imagenum_list[-1]+'.txt'
            with open(datapath+datafile,'a') as fd:
                #S Write all the environment temps, etc. also record old
                #S and new best focii
                fd.write('Old\tNew\tTM1\tTM2\tTM3\tTamb\tTback\talt\trotang\n')
                fd.write('%0.0f\t%0.0f\t%s\t%s\t%s\t%s\t%s\t%0.2f\t%s\n'\
                             %(old_best_focus,new_best_focus,tm1,tm2,tm3,tamb,\
                                   tback,float(alt),rotang))
                fd.write(datetime.datetime.utcnow().strftime(\
                        '%Y-%m-%d %H:%M:%S')+'\n')

                #S Write a header with info on following columns
                header = 'Column 1\tImage number\n'+\
                    'Column 2\tFocuser position\n'+\
                    'Column 3\tMedian focus measure\n'+\
                    'Column 4\tSDOM\n'+\
                    'Column 5\tNumber of stars'
                #S save the array of good stuff
                np.savetxt(fd,autodata,fmt='%s',header=header)
        else:
            control.logger.error('T'+str(telescope_number)+': Could not '+
                                 'record autodata due to mismatch length in'+\
                                     ' arrays')
    except:
        control.logger.exception('T'+str(telescope_number)+':unhandled error'+\
                                  ' stopped record of autofocus results.')
        
    if new_best_focus == old_best_focus:
        body = "Hey humans,\n\nI'm having trouble with autofocus, and "+\
            "need your assitance. You have a few options:\n"\
            +"-Try and figure what is going on with the newautofocus\n"\
            +"-Revert to PWI autofocus\n"\
            +"This may be tricky because a lot of this is worked into "+\
            "the observingScript, "\
            +"and you may be fighting with that for control of the "+\
            "telescope."\
            +" I would recommend stopping main.py, but it could be "+\
            "situational.\n\n"\
            +"I AM CONTINUING WITH NORMAL OPERATIONS USING OLD ''BEST'' "+\
            "FOCUS.\n\n"\
            +"Love,\nMINERVA\n\n"\
            +"P.S. Tips and tricks (please add to this list):\n"\
            +"-You could be too far off the nominal best focus, and the"+\
            " routine can't find a clean fit.\n"\
            +"-The aqawan could somehow be closed, and you're taking "+\
            "pictures that it can't find stars in.\n"\
            +"-You can now plot the results of any autofocus run, look "+\
            "into newauto.recordplot(). Just "\
            +"'python newauto.py' and enter the recordplot(path+"+\
            "record_name).\n"
 
 
        if len(goodind)!=0:
            #                ipdb.set_trace()
            try:
                afplot = recordplot(datapath+datafile,saveplot=True)
                subject = "Autofocus failed on T%s; plot attached"\
                    %(str(telescope_number))
            except:
                afplot = None
                subject = "Autofocus failed on T%s; exception raised"\
                    %(str(telescope_number))
        else:
            afplot=None
            subject = "Autofocus failed on T%s; no stars in image"\
                %(str(telescope_number))
 
        mail.send(subject,body,level='serious',attachments=[afplot])


if __name__ == '__main__':

    recordplot('/Data/t1/n20160405/n20160405.T1.autorecord.port2.V.1753.1767.txt')
    ipdb.set_trace()
    
    filenames = glob.glob('/Data/t?/n20160323/*autorecord*.txt')
    for filename in filenames:
        print filename
        recordplot(filename)
    ipdb.set_trace()
    print new_get_hfr('/Data/t1/n20160128/n20160128.T1.autofocus.V.0472.cat')
    print get_hfr_med('/Data/t1/n20160128/n20160128.T1.autofocus.V.0472.cat')
    ipdb.set_trace()
