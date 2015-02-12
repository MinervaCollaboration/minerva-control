from glob import glob
import pyfits
import segments
import source_extraction
import os.path
import numpy as np
from datetime import datetime, timedelta

def findoffset(x, y, mag, xref, yref, magref):
    
    MAXSTARS = 50
    thet=0.0 # thet +/- dthet (deg)
    dthet = 0.1
    scl = 0.0 # 1 + scl +/- dscl
    dscl = 0.01
    naxis1 = 2048
    naxis2 = 2048

    maxstars = min(MAXSTARS,len(xref))
    sortndx = np.argsort(magref)
       
    xreftrunc = xref[sortndx[0:maxstars]]
    yreftrunc = yref[sortndx[0:maxstars]]
    magreftrunc = magref[sortndx[0:maxstars]]
    lindx1,lparm1 = segments.listseg(xreftrunc, yreftrunc, magreftrunc)

    maxstars = min(MAXSTARS,len(x))

    sortndx = np.argsort(magtmp)
    x = x[sortndx[0:maxstars]]
    ytmp = ytmp[sortndx[0:maxstars]]
    magtmp = magtmp[sortndx[0:maxstars]]
    lindx2,lparm2 = segments.listseg(xtmp, ytmp, magtmp)
    
    # magic
    dx,dy,scale,rot,mat,flag,rmsf,nstf = \
        segments.fitlists4(naxis1,naxis2,lindx1,lparm1,lindx2,lparm2,\
                               xref,yref,xtmp,ytmp,scl,dscl,thet,dthet)
    
