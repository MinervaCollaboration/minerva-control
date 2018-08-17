# This module contains ports of useful IDL math and data processing utilities.


# This is a port of my IDL weighted least-squares fit program lstsqr.pro
#; This routine does a weighted linear least-squares fit of the nfun functions
#; in array funs[nfun,npt] to the data in array dat.  The weights are given
#; in array wt.  If argument type is given (default=0)
#; then on return outp contains:
#;  type = 0 => the fitted function
#;  type = 1 => residuals around fit,in the sense (data - fit)
#;  type = 2 => ratio (data/fit)
#  Python version returns tuple (fit coeffs,rms,chisq,outp)
#; chisq contains the average of err^2*wt^2, so that wt is implicitly
#; taken to be the reciprocal of the expected sigma at each data point.
#; The technique used is to construct and solve the normal equations.
#; Note that this technique will give garbage for ill-conditioned systems.

import numpy as np
import numpy.linalg as la

def lstsqr(dat,funs,wt,nfun,type=0):

#  dat(nx), wt(nx), funs(nfun,nx) are all numpy arrays.
#  construct funs with, eg, funs=np.zeros(nx,nfun); funs[i,:]=array([f1,f2...])

#; get dimensions of things, make extended arrays for generating normal eqn
#; matrix
   sz=np.shape(dat)
   if len(sz) != 1:
      print 'bad dimension in lstsqr data'
      return [0.],0.,0.,[0.]
   else:
      nx=sz[0]
      wte=np.resize(wt,(nfun,nx))
      datw=np.resize(dat,(nfun,nx))*wte
      funw=funs*wte

#; make normal eqn matrix, rhs
      a=np.zeros([nfun,nfun])
      rhs=np.reshape(np.sum(funw*datw,axis=1),nfun)
      for i in range(nfun):
         for j in range(nfun):
            if i >= j:
               prod=np.sum(funw[i,:]*funw[j,:])
               a[i,j]=a[j,i]=prod

# solve equations
      aa=la.solve(a,rhs)

#; Make fit function, rms
      outpt=np.transpose(np.resize(aa,[nx,nfun]))*funs
      outpt=np.reshape(sum(outpt,0),nx)
      dif=dat-outpt
      s=np.where(wt > 0.)
      ns=len(s)

      if ns > 0:
         wt2=pow(wt,2)
         dif2=pow(dif,2)
         rms=np.sqrt(sum(dif2[s]*wt[s])/ns)
         ndegfree=max([ns-nfun,1])
         chisq=np.sum(dif2[s]*wt[s])/ndegfree
      else:
         rms=0.
         chisq=0.

#; make final outp, depending on type
      if type == 0: outp=outpt
      if type == 1: outp=dif
      if type == 2: outp=dat/outpt

# return the goods
      return aa,rms,chisq,outp

#; This routine returns the median med, the two quartile points q(2),
#; and the full separation between quartile points dq for the input data
#; vector f.
#; For gaussian-distributed data, dq = rms*1.349

def quartile(f):
   med=np.median(f,axis=None)
   nn=f.size
   if nn < 3:
      print 'Need at least 3 data points to compute quartiles'
      q=np.array((med,med))
      dq=0.
   else:
      q=np.zeros(2)
      shi=f[f >= med]
      slo=f[f < med]
      if slo.size > 0: q[0]=np.median(slo) 
      else: q[0]=f[0]
      if shi.size > 0: q[1]=np.median(shi) 
      else: q[1]=f[-1]
      dq=q[1]-q[0]

   return med,q,dq
