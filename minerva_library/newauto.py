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
    count = len(open(recordfile).readlines(  ))
    if count <= 5:
        print 'Nothing good in that record, try something better!'
        return None


    raw_data = np.genfromtxt(recordfile,skip_header=5)
    imnlist = raw_data[::step,0].astype(int)
    poslist = raw_data[::step,1].astype(float)
    hfrlist = raw_data[::step,2].astype(float)
    stdlist = raw_data[::step,3].astype(float)
    numlist = raw_data[::step,4].astype(float)

    # bad values used to be -999, make backward compatible
    badind = np.where(hfrlist == -999)[0]
    hfrlist[badind] = np.nan

    #S identify the good points, those were an hfr was found
    goodind = np.where(np.logical_not(np.isnan(hfrlist)))[0]

    #S if there were no good points
    if len(goodind) == 0:
        print 'Nothing good in that record, try something better!'
        return None

    #S try and fit the point, else return the found coefficients
    try:
        focus,coeffs = fitquadfindmin(poslist[goodind],hfrlist[goodind],
                                      stdlist[goodind]*np.sqrt(numlist[goodind]))
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

    else:
        #S just show it if we aren't saving
        plt.show()
        plt.close(fig)
    print 'leaving recordplot()'

def quad(x,c):
    return c[0]*x**2+c[1]*x+c[2]

## FWHM = 2*HFR
# HFR in Pixels
#S want to look at multiple images of one focus for FAU focusing potentially

def get_star(cata):
    # CD Returns the source we want the autofocus to use.
    r = cata['FLUX_RADIUS']
    b = cata['FLUX_ISO'] / np.max(cata['FLUX_ISO'])
    # CD This function seems to work well for choosing the right source
    # CD Might need to change later
    starind = np.argmax(b + 1/r)
    return starind

def new_get_hfr(catfile,fau=False,telescope=None,min_stars=10,ellip_lim=0.66):
    #S get a dictionary containg the columns of a sextracted image
    cata = utils.readsexcat(catfile)

    if not ('FLUX_RADIUS' in cata.keys()):
        if telescope != None: telescope.logger.exception('No hfr in '+catfile)
        return np.nan, np.inf, 0

    if len(cata['FLUX_RADIUS']) == 0:
        if telescope != None: telescope.logger.warning('No stars in image')
        return np.nan, np.inf, 0

    if not ('A_IMAGE' in cata.keys() and 'B_IMAGE' in cata.keys()):
        if telescope != None: telescope.logger.error('No major/minor axes in '+catfile)
        circ_ind = []
        return np.nan, np.inf, 0
    else:
        ellip = cata['A_IMAGE']/cata['B_IMAGE']
        circ_ind = np.where( (ellip >= ellip_lim) & (ellip <= 1.0/ellip_lim) )[0]

    # Check if the stars are too elliptical => windy or not stars; don't use for autofocus
    if len(circ_ind) == 0:
        if telescope != None: telescope.logger.error("Stars are too elliptical, can't use "+catfile)
        return np.nan, np.inf, 0

    # We only expect one or two stars from the FAU guide camera
    if fau:
        # But ghosts are more likely than a second star; just use the brightest
       # hfr_med = cata['FLUX_RADIUS'][cata['FLUX_ISO'].argmax()]
       
        # CD New SExtractor parameters will return many false sources
        # CD This function seems to work for finding the real star
        true_star = get_star(cata)
        hfr_med = cata['FLUX_RADIUS'][true_star]
        hfr_std = 1.0
        numstars = 1.0

    # We expect more than MIN_STAR (ten) stars in a normal image
    elif len(circ_ind>min_stars):
        try:
            hfr_med = np.median(cata['FLUX_RADIUS'][circ_ind])
        except:
            if telescope != None: telescope.logger.error("Could not get median value in "+catfile)
            return np.nan, np.inf, 0

        try:
            numstars = len(circ_ind)
            # Get the Median Absolute Deviation, and we'll convert to stddev then stddev of the mean
            hfr_mad = np.median(np.absolute(cata['FLUX_RADIUS'][circ_ind]-np.median(cata['FLUX_RADIUS'][circ_ind])))

            # We assume that our distribution is normal, and convert to stddev.
            # May need to think more about this, as it isn't probably normal.
            #S Recall stddev of the mean = stddev/sqrt(N)
            hfr_std = (hfr_mad*1.4862)/np.sqrt(numstars)
        except:
            if telescope != None: telescope.logger.error("Could not get HFR_STD in "+catfile)
            return np.nan, np.inf, 0

    return hfr_med, hfr_std, numstars

def fitquadfindmin(poslist, fwhmlist, weight_list=None,logger=None):
    #S if given a list of stadard deviations, we need to do the inverse of 
    #S that for the weight in np.polyfit per the documentation it minimizes 
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
        logger.debug('Starting sigma clipping for autofocus fit.')
    #S see if the old coefficients are the same and if iters is below the max
    #S we enter this loop at least once, but probably don't need to refit.
    #TODO think of better ways to do this? not that important right now.

    # flag failure by returning no best_measured_focus
    best_measured_focus = None

    while not (oldcoeffs == coeffs).all() and iters<10:
        if len(inds) < 3:
            if type(logger)!=type(None): logger.error("Not enough points (" + str(len(inds)) + ") to fit")
            return best_measured_focus, coeffs

        if type(logger)!=type(None): logger.info('fitting '+ str(len(inds)) + ' points')

        #S set the old to the new
        oldcoeffs = coeffs.copy()
        #S get the new
       # if weight_list != None:
       # coeffs = np.polyfit(poslist[inds],fwhmnp[inds],2,w=weight_list[inds])
        coeffs = np.polyfit(poslist[inds],fwhmnp[inds],2)
        #S evaluate quad with new coeffs
        quad = coeffs[0]*poslist**2 + coeffs[1]*poslist + coeffs[2]
        #S find the std of the residuals
        std = np.std(fwhmnp[inds]-quadnp[inds])
        #S redefine the indices where the residuals are greater than 3 sigma.
        #S this should catch all points that were previously excluded.
        fwhmnp = np.asarray(fwhmlist)
        quadnp = np.asarray (quad)
        inds = np.where(np.absolute(fwhmnp-quadnp) < 3.*std)[0]

        #S increase the iterations
        iters += 1

    if iters > 9:
        if type(logger)!=type(None): logger.error("Exceeded max iterations")
        return best_measured_focus, coeffs

    # Check if our fit was upside down (and so clearly wrong)
    if coeffs[0] <= 0.0:
        if type(logger)!=type(None): logger.error('Fit upside down quadratic')
        return best_measured_focus, coeffs

    # solve for minimum (derivative = 0), and convert to an integer
    best_focus = int(-coeffs[1]/(2.0*coeffs[0]))

    # don't allow it to go beyond the limits
    if best_focus < min(poslist) or best_focus > max(poslist):
        #S log that we were out of range
        if type(logger)!=type(None):
            logger.error('Fitted focus (' + str(best_focus) + ') was outside of limits (' + str(min(poslist)) + ',' + str(max(poslist)) + ')')
            return best_measured_focus, coeffs

    #S Return coeffs for extra output to any other function besides control
    return best_focus, coeffs

def autofocus_step(control,telescope,newfocus,af_target, simulate=False):

    status = telescope.getStatus()
    m3port = status.m3.port

    # default (bad) values
    # will be overwritten by good values or serve as flags later
    median = np.nan
    stddev = np.inf
    numstar = 0
    imnum = '9999'

    if newfocus < float(telescope.minfocus[m3port]) or newfocus > float(telescope.maxfocus[m3port]):
        telescope.logger.warning("Focus position (" + str(newfocus) + ") out of range (" + str(telescope.minfocus[m3port]) + "," + str(telescope.maxfocus[m3port]) + ")")
        return median,stddev,numstar,imnum

    telescope.logger.info("moving focuser and waiting")
    if not telescope.focuserMoveAndWait(newfocus,m3port):
        telescope.recoverFocuser(newfocus,m3port)
        telescope.acquireTarget(af_target)

    if af_target['spectroscopy']:
        telescope.logger.info("taking FAU image")
        imagename = control.takeFauImage(af_target,telescope.id)
        telescope.logger.info("done taking FAU image")
    else:
        telescope.logger.info("taking image")
        imagename = control.takeImage(af_target,telescope.id)

    try:
        imnum = imagename.split('.')[4]
    except:
        telescope.logger.exception('Failed to save image: "' + imagename + '"')
        return median,stddev,numstar,imnum

    datapath = '/Data/' + telescope.id.lower() + '/' + control.site.night + '/'
    catalog = '.'.join(imagename.split('.')[0:-2]) + '.cat'

    #S Sextract this guy, put in a try just in case. Defaults should
    #S be fine, which are set in newauto. NOT sextrator defaults
    try:
        catalog = utils.sextract(datapath,imagename)
        telescope.logger.debug('Sextractor success on '+catalog)
    except:
        telescope.logger.exception('Sextractor failed on '+catalog)
        return median,stddev,numstar,imnum

    median,stddev,numstar=new_get_hfr(catalog,telescope=telescope,fau=af_target['spectroscopy'])
    return median,stddev,numstar,imnum

# the high-level auto-focus routine
def autofocus(control,telid,num_steps=10,defocus_step=0.3,\
                  target=None,dome_override=False,simulate=False,slew=True, exptime=5.0):

    control.logger.info("Beginning autofocus")
    telescope = utils.getTelescope(control,telid)
    camera = utils.getCamera(control,telid)
    dome = utils.getDome(control,telid)
    control.logger.info("identified objects")

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
                af_target['exptime'] = exptime
                af_target['fauexptime'] = exptime
                af_target['filter'] = "V"
        else:
            m3port = telescope.port['IMAGER']
            af_target['spectroscopy'] = False
            af_target['exptime'] = exptime
            af_target['fauexptime'] = exptime
            af_target['filter'] = "V"

        control.logger.info("defined af_target")

    else:
        status = telescope.getStatus()
        m3port = status.m3.port
        if m3port == telescope.port['FAU']:
            spectroscopy = True
        else:
            spectroscopy = False
        status = telescope.getStatus()
        # use the current position
        ra = utils.ten(status.mount.ra_2000)
        dec = utils.ten(status.mount.dec_2000)
        slew=False
        af_target = {'name':'autofocus',
                     'exptime':exptime,
                     'fauexptime':exptime,
                     'filter':"V",
                     'spectroscopy':spectroscopy,
                     'ra' : ra,
                     'dec' : dec
                     }

    # best guess at focus
    telescope.guessFocus(m3port)

#    try: m1temp = float(status.temperature.primary)
#    except: m1temp = float(telescope.T0[m3port])
#    try: ambtemp = float(status.temperature.ambient)
#    except: ambtemp = m1temp - float(telescope.dT0[m3port])
#    try: gravity = math.sin(float(status.mount.alt_radian))
#    except: gravity = float(telescope.G0[m3port])
#    dt = m1temp-ambtemp
#    telescope.focus[m3port] = float(telescope.F0[m3port]) + \
#        float(telescope.C0[m3port])*(m1temp-float(telescope.T0[m3port])) + \
#        float(telescope.C1[m3port])*(dt-float(telescope.dT0[m3port])) + \
#        float(telescope.C2[m3port])*(gravity-float(telescope.G0[m3port]))
#    telescope.logger.info('Starting focus for port ' + m3port + ' at ' + str(telescope.focus[m3port]) + ' when T=' + str(m1temp) + ', dT=' + str(dt) + ', gravity=' + str(gravity))

    control.logger.info("setting platescale")
    #S set the platescale for the image
    if af_target['spectroscopy']:
        platescale = float(camera.fau.platescale)
    else:
        platescale = float(camera.platescale)

    #S Initialize telescope, we want tracking ON
    if 'tracking' in af_target.keys(): tracking = af_target['tracking']
    else: tracking = True

    control.logger.info("initializing scope")
    # make sure the telescope is tracking
    if not telescope.isInitialized(tracking=tracking,derotate=(not af_target['spectroscopy'])):
        if not telescope.initialize(tracking=tracking,derotate=(not af_target['spectroscopy'])):
            telescope.recover(tracking=tracking,derotate=(not af_target['spectroscopy']))

    control.logger.info("checking keys")
    if 'ra' in af_target.keys() and 'dec' in af_target.keys() and slew:
        telescope.acquireTarget(af_target,derotate=(not af_target['spectroscopy']))
        # TODO: Need to think about incorporating guiding for FAU
    else:
        telescope.logger.info('No ra and dec, using current position')

    # S our data path
    control.logger.info("setting data path")
    datapath = telescope.datadir + control.site.night + '/'

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

    control.logger.info("defining autofocus steps")
    #S make array of af_defocus_steps
    defsteps = np.linspace(-defocus_step*(num_steps/2),defocus_step*(num_steps/2),num_steps)

    #S Just need an empty list for the fwhm/hfr and std to append to. made
    #S FOCUSMEASure_LIST because we don't necessarily know which value we want
    imagenum_list = np.array([])
    focusmeas_list = np.array([])
    stddev_list = np.array([])
    numstar_list = np.array([])
    poslist = np.array([])

    for step in defsteps:

        if telescope.abort:
            telescope.logger.info("Autofocus aborted")
            return

        #S set the new focus, and move there if necessary
        newfocus = telescope.focus[m3port] + step*1000.0
        telescope.logger.info("New step is " + str(newfocus))

        # if new focus out of mechanical range, skip this step
        if newfocus < float(telescope.minfocus[m3port]) or newfocus > float(telescope.maxfocus[m3port]):
            telescope.logger.info("Autofocus step (" + str(newfocus) + ") out of range; skipping")
            continue

        status = telescope.getStatus()

        #S ensure we have the correct port
        telescope.logger.info("switching to port " + str(m3port))
        telescope.m3port_switch(m3port)
        #S move and wait for focuser
        telescope.logger.info("Defocusing port " + str(m3port) + " by " + str(step) + " mm, to " + str(newfocus))

        median,stddev,numstars,imnum = autofocus_step(control,telescope,newfocus,af_target, simulate=simulate)
        imagenum_list = np.append(imagenum_list,str(imnum))
        focusmeas_list = np.append(focusmeas_list,median*platescale)
        stddev_list = np.append(stddev_list,stddev)
        numstar_list = np.append(numstar_list,numstars)
        poslist = np.append(poslist,newfocus)

#        imagenum_list.append(str(imnum))
#        focusmeas_list.append(median*platescale)
#        stddev_list.append(stddev)
#        numstar_list.append(numstars)
#        poslist.append(newfocus)

    #S find the indices where we didnt hit an error getting a measure
    goodind = np.where(np.logical_not(np.isnan(focusmeas_list)))[0]

    #S This try is here to catch any errors/exceptions raised out of
    #S fitquad. I think we should include exceptions if we are too far
    #S out of focus, etc to make this catch whenever we didn't find a
    #S best focus.

    if len(goodind) == 0:
        telescope.logger.error('No stars; autofocus failed')
        return

    # find the best focus
    telescope.logger.debug('fitting to '+str(len(goodind))+' points.')

    new_best_focus,fitcoeffs = fitquadfindmin(poslist[goodind],focusmeas_list[goodind],\
                                              weight_list=stddev_list[goodind],\
                                              logger=telescope.logger)

    # want to record old best focus
    old_best_focus = telescope.focus[m3port]

    # values that may correlate with focus
    try: alt = str(float(status.mount.alt_radian)*180.0/math.pi)
    except: alt = '-1'
    rotatorStatus = telescope.getRotatorStatus(m3port)
    try: rotang = str(float(rotatorStatus.position))
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

    #S Record all the data to its own run unique file for potential use
    #S later. Just don't want to be scraping through logs for it when we can
    #S just record it now.
    try:
        #S Check to make sure all the arrays are the same length and not zero.
        if len(imagenum_list)==len(poslist)==len(focusmeas_list)==\
                len(stddev_list)==len(numstar_list):
            #S Stack them all together, then transpose so we can write
            #S them in columns
            autodata = np.vstack([imagenum_list,poslist,focusmeas_list,\
                                      stddev_list,numstar_list]).transpose()
            #S Name the data file as:
            #S 'nYYYYMMDD.T#.autorecord.port#.filter.AAAA.BBBB.txt',
            #S where AAAA is the image number on the first image of the
            #S autofocus sequence, and BBBB the last image number.
            datafile = control.site.night+telid+'.autorecord.port'+str(m3port)+'.'+af_target['filter'][0]+'.'+imagenum_list[0]+'.'+imagenum_list[-1]+'.txt'
            with open(datapath+datafile,'a') as fd:
                #S Write all the environment temps, etc. also record old
                #S and new best focii
                focusstr = str(new_best_focus)
                fd.write('Old\tNew\tTM1\tTM2\tTM3\tTamb\tTback\talt\trotang\n')
                fd.write('%0.0f\t%s\t%s\t%s\t%s\t%s\t%s\t%0.2f\t%s\n'\
                             %(old_best_focus,focusstr,tm1,tm2,tm3,tamb,\
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
                np.savetxt(fd,autodata, fmt='%s', header=header)
        else:
            control.logger.error('mismatch length in autofocus arrays')
    except:
        control.logger.exception('unhandled error in autofocus results.')

    # update the best focus
    if new_best_focus == None:
        best_measured_foc = np.nanmin(focusmeas_list)
        best_measured_pos = poslist[np.nanargmin(focusmeas_list)]
        if best_measured_foc > 3.0:
            # fit failed, no good values; don't update focus
            telescope.logger.warning('Autofocus failed, and best focus is bad (' + str(best_measured_foc) + '"); using old focus')
        else:
            # fit failed; good values; use best measured focus
            telescope.logger.warning('Autofocus failed, using best measured focus (' + str(best_measured_pos) + ',' + str(best_measured_foc) + ')')
            telescope.focus[m3port] = best_measured_pos
    else:
        # fit succeeded; use best fitted focus
        telescope.focus[m3port] = new_best_focus

    # write the best focus in a file for future use
    focname = 'focus.' + telescope.logger_name + '.port' + m3port+'.txt'
    with open(focname,'w') as fname:
        fname.write(str(telescope.focus[m3port]))

    # move to the best focus
    if not telescope.focuserMoveAndWait(telescope.focus[m3port],m3port):
        telescope.recoverFocuser(telescope.focus[m3port],m3port)
        telescope.acquireTarget(af_target)

    if new_best_focus == None: return

    # if the fit succeeded, log the values for future analysis
    telescope.logger.info('Updating best focus for port '+str(m3port)+\
                            ' to '+str(telescope.focus[m3port])+' (TM1='+tm1 +\
                            ', TM2=' + tm2 + ', TM3=' + tm3 + ', Tamb=' + \
                            tamb + ', Tback=' + tback + ', alt=' + alt + ')' )

    telescope.logger.info('Finished autofocus')
    return

    if new_best_focus == old_best_focus:
        body = "Hey humans,\n\nI'm having trouble with autofocus, and "+\
            "need your assitance.\n"\
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
            try:
                afplot = recordplot(datapath+datafile,saveplot=True)
                subject = "Autofocus failed on %s; plot attached"\
                    %(telid)
            except:
                afplot = None
                subject = "Autofocus failed on %s; exception raised"\
                    %(telid)
        else:
            afplot=None
            subject = "Autofocus failed on %s; no stars in image"\
                %(telid)

        mail.send(subject,body,level='serious',attachments=[afplot])


if __name__ == '__main__':

#    recordplot('/Data/t1/n20160405/n20160405.T1.autorecord.port2.V.1753.1767.txt')
#    ipdb.set_trace()

    filenames = glob.glob('/Data/t?/n20161220/*autorecord*.txt')
#    filenames = glob.glob('/Data/t4/n20161214/*autorecord*0005.0014.txt')
    for filename in filenames:
        if not '9999.9999' in filename:
            print filename
            recordplot(filename)
    ipdb.set_trace()
    print new_get_hfr('/Data/t1/n20160128/n20160128.T1.autofocus.V.0472.cat')
    print get_hfr_med('/Data/t1/n20160128/n20160128.T1.autofocus.V.0472.cat')
    ipdb.set_trace()
