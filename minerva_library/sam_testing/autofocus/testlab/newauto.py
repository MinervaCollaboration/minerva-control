import numpy as np
import subprocess
import scipy
import scipy.optimize
import ipdb

def sextract(datapath,imagefile,sexfile='autofocus.sex',paramfile=None,convfile=None,catfile=None):

    #S Path on MinervaMAIN where all the .sex, .param, etc. files will be 
    #S located
    sexpath = '/usr/share/sextractor/'
    #S This is the base command we be calling with sextractor. It has
    #S the default sexfile of autofocus.sex, which will be given some pretty 
    #S general values for now.
    # We'll add on other parameters and arguements as they are specified
    sexcommand = 'sextractor '+datapath+imagefile+' -c ' + sexpath+sexfile
    #S If a paramfile was specfied, then we will use that instead of the 
    #S default param file in autofocus.sex (which is autofocus.param)
    if paramfile <> None:
        sexcommand+= ' -PARAMETERS_NAME ' + sexpath+paramfile
    #S Similar to above, but will be the vconvolution filter that were using.
    if convfile <> None:
        sexcommand+= ' -FILTER_NAME ' + sexpath+convfile
    #S we're going to name the catalog after the image just by removing the 
    #S fits and  adding cat. if a cat file is specified we'll use that. 
    #S Datpath is the path where the image is (hopefully), but can be anywhere
    #S you want it to go.
    if catfile == None:
        catfile = imagefile.split('.fits')[0] + '.cat'
        sexcommand += ' -CATALOG_NAME ' + datapath+catfile
    #S so we a have sexcommand, which has all of it's components split by 
    #S spaces ideally, which will allow for just a .split to put in a list 
    #S for subprocess.call
    subprocess.call(sexcommand.split())
    #S Just going to return the catalog file name for now, could return fwhm, 
    #S whatever later
    return catfile



def get_hfr_med(catfile):
    #S need to find which column has the hfr, but it'll start as None
    hfr_col = None
    catalog = open(catfile, 'r')
    for line in catalog.readlines():
        #S Find the column that contains the hfr
        if '#' in line and 'FLUX_RADIUS' in line:
            hfr_col = int(line[4])
        #S Checking for a line that would indicate the fwhm
        if '#' in line and 'FWHM_IMAGE' in line:
            fwhm_col = int(line[4])
        #S If we get past the header of the catalog, let's stop reading lines
        if (not ('#' in line)):
            break
    if hfr_col == None:
        print 'we didnt find an hfr column, somthing wrong with catalog'
        return False, False
    #S we could explicitly write out arguemnets, but this will do for now.
    cat_array = np.genfromtxt(catfile)
    #S This is silly, we can do much better with flag checks, sizes, etc.
    #S really simple right now.
    hfr_med = np.median(cat_array[:,hfr_col-1])
    #S Get the Median Absolute Deviation, and we'll convert to stddev then stddev of the mean
    hfr_mad = np.median(np.absolute(cat_array[:,hfr_col-1]-np.median(cat_array[:,hfr_col-1])))
    #S We assume that our distribution is normal, and convert to stddev. May need to think more 
    #S about this, as it isn't probably normal. 
    #S Recall stddev of the mean = stddev/sqrt(N)
    hfr_std = (hfr_mad*1.4862)/np.sqrt(len(cat_array[:,hfr_col-1]))
    return hfr_med, hfr_std


def fitquadfindmin(poslist, fwhmlist, weight_list=None):
    
    #S if given a list of stadard deviations, we need to do the inverse of that for the wieght in np.polyfit
    #S per the documentation it minimizes sum(w**2(y-y_mod)**2), where w is the weight provided.
    if type(weight_list) == list:
        weight_list = 1/np.array(weight_list)
    # analytically fit a quadratic
    #S this is fine if w=None, as that is the default for the kwarg
    #S here is just an initializiation of an array for the old coeffs
    oldcoeffs = np.array([0.,0.,0.])
    #S actually fit a quadratic, using the entire set of data
    coeffs = np.polyfit(poslist,fwhmlist,2)#,w=weight_list)
    #S evaulate the fit at the given focuser positions
    quad = coeffs[0]*poslist**2 + coeffs[1]*poslist + coeffs[2]
    #S find the standard deviation of the residuals
    std = np.std(fwhmlist-quad)
    #S create a set of indices where the residuals are greater than 3sigma
    inds = np.where(np.absolute(fwhmlist-quad) < 3.*std)
    #S initialize the iteration couter
    iters = 0
    #S see if the old coefficients are the same and if iters is below the max
    #S we enter this loop at least once, but probably don't need to refit.
    #TODO think of better ways to do this? not that important right now.
    while not (oldcoeffs == coeffs).all() and iters<10:
        #S set the old to the new
        oldcoeffs = coeffs
        #S get the new
        coeffs = np.polyfit(poslist[inds],fwhmlist[inds],2)#,w=weight_list[inds])
        #S evaluate quad with new coeffs
        quad = coeffs[0]*poslist**2 + coeffs[1]*poslist + coeffs[2]
        #S find the std of the residuals
        std = np.std(fwhmlist[inds]-quad[inds])
        #S redefine the indices where the residuals are greater than 3sigma. this should 
        #S catch all points that were previously excluded. 
        inds = np.where((fwhmlist-quad) < 3.*std)
        #S increase the iterations
        iters += 1

    # if the best fit was a downward facing parabola, it was bad
    if coeffs[0] < 0.0: return None

    # solve for minimum (derivative = 0)
    best_focus = -coeffs[1]/(2.0*coeffs[0])
 
    # don't allow it to go beyond the limits
    if best_focus < min(poslist):
        #S temp putting it to return none, we don't require it to have domes open,
        #S actual picture sbeing taken, so it could be trowing us off 
        return None
        best_focus = min(poslist)

    if best_focus > max(poslist):
        #S Same as above
        return None
        best_focus = max(poslist)

    return best_focus
    

if __name__ == '__main__':
    import ipdb
    ipdb.set_trace()
    print get_hfr_med('./sam_testing/autofocus/testdir/testringtophatbig.cat')
    ipdb.set_trace()
