# this module contains routines for the line-segment WCS code, which
# matches starfield images either to each other or to star catalogs.
# These routines are intended to be fast and relatively insensitive to
# the number of stars available for fitting, but they demand that the
# location, plate scale, and orientation of the image to be matched be
# known at least fairly well.

#; This routine takes vectors of the x,y positions and magnitudes of 
#; nst stars.  It generates and returns numpy arrays containing the
#; chracteristics of all of the line segments connecting pairs of stars
#; Segments point from the brighter (lower-mag) star to the fainter.
#; Parameters returned are:
#;  lindx(2,nl) = indices of the component stars in the original star list.
#;               lndx(0,*) contains the brighter stars, lndx(1,*) the fainter
#;  lparm(0:1,nl) = x,y positions of brighter component of each segment
#;  lparm(2,nl) = separation between the 2 components (pixel)
#;  lparm(3,nl) = angle of rotation from x-axis to segment (degrees)
#;  lparm(4,nl) = magnitude difference faint-bright >= 0.

import numpy as np
import numpy.random as ran
import math
import util

def listseg(x,y,mag):

   nst=len(x)
   nl=nst*(nst-1)/2

   lindx=np.zeros([2,nl])
   lparm=np.zeros([5,nl])

   so=np.argsort(mag)
   xs=x[so]
   ys=y[so]
   mags=mag[so]

   ii=0
   for i in range(nst):
      for j in range(i+1,nst):
         lindx[0,ii]=so[i]
         lindx[1,ii]=so[j]
         lparm[0,ii]=xs[i]
         lparm[1,ii]=ys[i]
         dx=xs[j]-xs[i]
         dy=ys[j]-ys[i]
         lparm[2,ii]=np.sqrt(pow(dx,2)+pow(dy,2))
         lparm[3,ii]=math.atan2(dy,dx)*180./math.pi
         lparm[4,ii]=mags[j]-mags[i]
         ii += 1

   return lindx,lparm


#; This routine searches for matches between the line segment lists
#; lndx1,lparm1 drawn from starlist of length n1,n2.
#; It assumes that the segments in list2 are multiplied by
#; (1.+scale), rotated CCW by rot (degrees), and have larger magnitude
#; differences by zp relative to those in list1.
#; Matching box size is factor of (1+/-dl) in length, +/-dt in rotation,
#; and +/-dm in magnitude difference.
#; Matching segments are assigned two votes, one of which is added to the
#; intersection of the indices of each of the two stars involved in the
#; segment.  The array of votes is returned.
#
# calling sequence is
# votes = matchseg(n1,lndx1,lparm1,n2,lndx2,lparm2)

def matchseg(n1,lndx1,lparm1,n2,lndx2,lparm2,scale,rot,zp,dl,dt,dm):

   votes=np.zeros((n1,n2))
   nl1=np.shape(lndx1)[1]
   nl2=np.shape(lndx2)[1]

#; transform segment parameters in list2
   len2=np.reshape(lparm2[2,:],nl2)/(1.+scale)
   thet2=np.reshape(lparm2[3,:],nl2)-rot
   thet2[thet2>180.]=thet2[thet2>180.]-360.
   thet2[thet2< -180.]=thet2[thet2 < -180.]+360.
   dm2=np.reshape(lparm2[4,:],nl2)+zp
   len1=np.reshape(lparm1[2,:],nl1)
   thet1=np.reshape(lparm1[3,:],nl1)
   dm1=np.reshape(lparm1[4,:],nl1)

#loop over segments in the 2nd list (ordinarily the smaller one)
   for i in range(nl2):
      sg=np.where((abs(len1/len2[i]-1.) <= dl) & (abs(thet1-thet2[i]) <= dt)
               & (abs(dm1-dm2[i]) <= dm))
      nsg=len(sg[0])
      if(nsg > 0):
         for j in range(nsg):
            ib=lndx1[0,sg[0][j]]
            jb=lndx2[0,i]
            iff=lndx1[1,sg[0][j]]
            jff=lndx2[1,i]
            votes[ib,jb]+=1
            votes[iff,jff]+=1

   return votes


#; This routine produces two lists of fake star positions
#; and magnitudes, each containing nstar stars within a box
#; of edge length len. 
#; The positions of stars in list2 are first rotated CCW
#; by an amount theta (degrees) relative to those in list1, then
#; multiplied by a factor (1. + scl) then displaced by 
#; dx,dy.  The magnitudes in list1 are randomly perturbed with
#; a gaussian distribution with rms = dmag.
#; On input, seed is the seed of the random number generator.

def mktestlists(nstar,len,sed,dx,dy,dmag,theta,scl):

   radian=180./math.pi
   ran.seed(sed)         # prime the random number generator

#make list1 positions, magnitudes
   x1=len*ran.random(nstar)
   y1=len*ran.random(nstar)
   l1=40.*ran.random(nstar)
   mag1=10.+np.log(l1)

# make list2 ditto
   x1p=x1-len/2.
   y1p=y1-len/2.
   thetr=theta/radian
   y2p=y1p*np.cos(thetr)+x1p*np.sin(thetr)
   x2p=x1p*np.cos(thetr)-y1p*np.sin(thetr)
   x2p=x2p*(1.+scl)
   y2p=y2p*(1.+scl)
   x2=x2p+len/2.+dx
   y2=y2p+len/2.+dy

   mag2=mag1+dmag*ran.randn(nstar)

   return x1,y1,mag1,x2,y2,mag2


#; This routine attempts to match line segments between vectors of star
#; positions and magnitudes described in ldx1,lprm1 and ldx2,lprm2.
#; These lists of line parameters are created by listseg.pro, and may have
#; been subsequently edited.
#; The technique is to use matchseg to match segments having similar length
#; and orientation, and to yield a trial set of corresponding stars.  This
#; set is then robustly fit to a 6-parameter model including x- and y-
#; displacements, and a 2 x 2 matrix transform.  The fit is rejected
#; unless the rotation and the scale change are within bounds thet +/- dthet,
#; scl +/- dscl.  In this case, flag is set to -1, else 0.
#; On input, lenx, leny are the edge lengths of the image that is being fit.
#; On output,
#;  rmsf = rms (pixels) about final fit to coords
#;  nstf = number of stars used in final coord fit

def fitlists4(lenx,leny,ldx1,lprm1,ldx2,lprm2,x1,y1,x2,y2,scl,dscl,thet,dthet):

   # constants
   fracv=0.6         # use votes cells that have at least fracv*max(votes)
   nmv0=4            # but insist on at least nmv0 votes
   mns=4             # need at least this many stars cross-identified to do
                  # a fit
   radian=180./math.pi
   flag=-1            # assumes a bad fit
   bad=1              # ditto


   # match the line segment lists
   nst1=np.size(x1)
   nst2=np.size(x2)
   n1=np.size(ldx1)
   n2=np.size(ldx2)
   zp=0.0                 # assume no systematic zero point shift
   dm=0.5                 # match magnitude differences within +/- 0.5 mag
   votes = matchseg(nst1,ldx1,lprm1,nst2,ldx2,lprm2,scl,thet,zp,dscl,dthet,dm)
      
   # select votes to give corresponding stars
   nmv=max(fracv*np.max(votes),nmv0)
   s=np.where(votes >= nmv)
   ns=np.size(s[0])
   if(ns > mns):

      # do the fit
      # compute star indices from s values, get coordinates
      ix1=s[0]
      ix2=s[1]

      # shift origin to center of image
      # fortran/sextractor/python indexing issue?
      xx1=x1[ix1]-lenx/2.0
      yy1=y1[ix1]-leny/2.0
      xx2=x2[ix2]-lenx/2.0           
      yy2=y2[ix2]-leny/2.0

      # make fitting functions
      funs=np.zeros((3,ns))
      funs[0,:]=1.
      funs[1,:]=xx1
      funs[2,:]=yy1
      wt=np.ones(ns)

      # do the fits
      ccx,rmsx,chisqx,outpx = util.lstsqr(xx2,funs,wt,3,type=1)
      ccy,rmsy,chisqy,outpy = util.lstsqr(yy2,funs,wt,3,type=1)

      # pitch outliers, if any
      err=np.sqrt(outpx**2+outpy**2)
      med,q,dq = util.quartile(err)
      sb=np.where(err > (med+5.*dq/1.349))
      nsb=np.size(sb)
      nsg=min((nst1,nst2))
      if nsb > 0:
         wt[sb]=0.
         sg=np.where(wt > 0.)
         nsg=np.size(sg)
         if(nsg > mns):
            ccx,rmsx,chisqx,outpx = util.lstsqr(xx2,funs,wt,3,type=1)
            ccy,rmsy,chisqy,outpy = util.lstsqr(yy2,funs,wt,3,type=1)

   else:
      bad=2
      outpx=np.ones(ns > 1)
      outpy=np.ones(ns > 1)
      ccx=np.array([0.,1.,0.])
      ccy=np.array([0.,0.,1.])
      rmsx=0.0
      rmsy=0.0

   # test for scale and rotation in correct range, also for unitary matrix
   while(bad):
      dx=ccx[0]
      dy=ccy[0]
      scale=np.sqrt((ccx[1]**2+ccx[2]**2+ccy[1]**2+ccy[2]**2)/2.)
      mat=np.array([ccx[1:3],ccy[1:3]])/scale
      rot=radian*math.atan2((mat[0,1]-mat[1,0])/2.,(mat[0,0]+mat[1,1])/2.)
      if(bad==2): break
      if (np.abs(scale-(1.+scl))/scale > dscl) or (abs(rot-thet) >= dthet):
         bad=1
      else:
         bad=0

      if(bad):
         err=np.sqrt(outpx**2+outpy**2)*wt
         merr=np.max(err)
         wt[err == merr] = 0.
         sg=np.where(wt > 0.)
         nsg=np.size(sg)
         if(nsg > mns): 
            ccx,rmsx,chisqx,outpx = util.lstsqr(xx2,funs,wt,3,type=1)
            ccy,rmsy,chisqy,outpy = util.lstsqr(yy2,funs,wt,3,type=1)

         else: break

   if(bad):
      flag=-1
      rmsf=0.
      nstf=0.
   else:
      flag=0
      rmsf=np.sqrt(rmsx**2+rmsy**2)
      nstf=nsg

   return dx,dy,scale,rot,mat,flag,rmsf,nstf

