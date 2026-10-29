# -*- coding: utf-8 -*-
"""
Created on Mon Mar 28 09:33:31 2016

@author: johnjohn
"""

import numpy as np
import matplotlib.pyplot as pl
from scipy.interpolate import interp1d
from astropy.io import fits
import numpy.random as rand
from scipy.optimize import curve_fit
from scipy.io.idl import readsav
from scipy.integrate import simps
import mpyfit  # This requires a special installation
import emcee
from timeit import default_timer as timer
from utils import *
from astropy.time import Time
from glob import glob
import socket, ipdb, os
import csv
import math
import random


class Spectrum(object):
    def __init__(self, obsname, bstar=False):
        self.c = 2.99792458e8  # speed of light
        ffile = obsname
        self.fits = ffile
        self.h = fits.open(ffile)

        # is this right?
        self.ntel = self.h[0].data.shape[0]

        t = Time(self.h[0].header['DATE-OBS'], format='isot', scale='utc')
        self.jd = t.jd

        self.wls = np.load('templates/MC_bstar_wls.air.npy')
        self.iodine = np.load('templates/MINERVA_I2_0.1_nm.npy')
        self.template = []
        self.ipdict = np.load('synthetic_IPs/ipdict.npy')

        # don't assume the same object or same redshift for each trace
        self.objname = np.array([])
        self.active = np.array([])
        self.zbc = np.array([])
        self.zguess = np.array([])
        self.weight = np.zeros(self.ntel)
        self.nactive = 0

        for i in range(self.ntel):
            self.objname = np.append(self.objname, self.h[0].header['OBJECT' + str(i + 1)])

            try:
                # try to get the barycentric redshift
                self.zbc = np.append(self.zbc, float(self.h[0].header['BARYCOR' + str(i)]))
            except:
                # if the barycentric redshift not in the headers, calculate it
                ra = self.h[0].header['TARGRA' + str(i + 1)]
                dec = self.h[0].header['TARGDEC' + str(i + 1)]

                # if keyword not populated, bu
                if self.h[0].header['FLUXMID' + str(i + 1)] == 'UNKNOWN':
                    midflux = self.jd + self.h[0].header['EXPTIME'] / 2.0 / 86400.0
                else:
                    midflux = self.h[0].header['FLUXMID' + str(i + 1)]

                try:
                    pmra = self.h[0].header['PMRA' + str(i + 1)]
                except:
                    pmra = 0.0
                try:
                    pmdec = self.h[0].header['PMDEC' + str(i + 1)]
                except:
                    pmdec = 0.0
                try:
                    parallax = self.h[0].header['PARLAX' + str(i + 1)]
                except:
                    parallax = 0.0
                try:
                    rv = h[0].header['RV' + str(i + 1)]
                except:
                    rv = 0.0
                self.zbc = np.append(self.zbc, barycorr(midflux, ra, dec, pmra=pmra, pmdec=pmdec, parallax=parallax,
                                                        rv=rv) / self.c)

            try:
                self.active = np.append(self.active, self.h[0].header['FAUSTAT' + str(i + 1)] == 'GUIDING')
            except:
                print 'FAUSTAT' + str(i + 1) + ' keyword not present'
                self.active = np.append(self.active, "True")

            if self.active[i]: self.nactive += 1

            if not bstar:

                if 'HD' in self.objname[i] and 'A' in self.objname[i]:
                    self.objname[i] = self.objname[i].split('A')[0]

                templatename = None
                # get the barycentric correction of the template from kbcvel.ascii
                if 'daytimeSky' in self.objname[i]:
                    # starting point for solar spectrum template
                    self.template = np.append(self.template, readsav('templates/nso.sav'))
                    self.zguess = np.append(self.zguess, 2.8e-4)
                elif 'HD' in self.objname[i]:
                    with open('templates/kbcvel.ascii', 'rb') as fh:
                        fh.seek(1)  # skip the header
                        for line in fh:
                            entries = line.split()
                            if len(entries) >= 6:
                                obstype = entries[5]
                                tempobjname = entries[1]
                                # **this assumes all stars are designated by their HD names!**
                                if obstype == 't' and tempobjname == self.objname[i].split('D')[1]:
                                    ztemp = float(entries[2]) / self.c  # template redshift
                                    templatename = 'templates/dsst' + tempobjname + 'ad_' + entries[0].split('.')[
                                        0] + '.dat'
                                    if os.path.exists(templatename):
                                        self.template = np.append(self.template, readsav(templatename))
                                        break
                    if templatename == None:
                        print 'ERROR: no template for ' + obsname
                        self.active[i] = False
                        continue
                    if not os.path.exists(templatename):
                        print 'ERROR: no template for ' + obsname
                        self.active[i] = False
                        continue

                    # the starting guess for the redshift will be the difference 
                    # between the barycentric correction of the observation and 
                    # the template
                    self.zguess = np.append(self.zguess, (1.0 + ztemp) / (1.0 + self.zbc[i]) - 1.0)
            else:
                self.zguess = np.append(self.zguess, 0.0)
            self.bstar = bstar


class FourChunk(object):
    def __init__(self, spectrum, order, lpix, dpix, fixip=False, juststar=False, oversamp=4.0):
        """ NOTE TO SELF: the GRIND code will have to use the BC to make an informed
        guess about where in the spectrum, pixel-wise, to start the analysis so that
        everything is performed in the star's reference frame. This will result in a
        variable lpix from obs to obs
        """

        #        self.c = 2.99792458e8 # speed of light

        self.order = order
        self.pixel = lpix
        self.ntel = spectrum.ntel
        self.bstar = spectrum.bstar
        self.active = spectrum.active
        self.juststar = juststar
        self.c = spectrum.c
        self.nactive = spectrum.nactive

        if self.nactive == 0: return

        #        ffile = obsname
        #        self.fits = ffile
        #        h = fits.open(ffile)
        #        t = Time(h[0].header['DATE-OBS'], format='isot', scale='utc')
        #        self.jd = t.jd

        rpix = lpix + dpix
        obspec = spectrum.h[0].data[:, order, lpix:rpix]
        shape = obspec.shape
        npix = shape[1]

        self.xchunk = np.arange(npix) - npix/2.0
        self.oversamp = 4.0
        pad = 120
        self.xover = np.arange(-(pad+npix/2.0),(pad+npix/2.0),1.0/self.oversamp)

        w0g = spectrum.wls[lpix+npix/2  , order]  # Guess at wavelength zero point (w0)
        dwg = spectrum.wls[lpix+npix/2+1, order] - spectrum.wls[lpix+npix/2, order] # Guess at dispersion (dw)
        wmin = w0g - (npix/2.0 + 4.0*pad) * dwg # Set min and max ranges of iodine template
        wmax = w0g + (npix/2.0 + 4.0*pad) * dwg

        self.wiod, self.siod = get_iodine(spectrum.iodine, wmin, wmax)
        self.iodinterp = interp1d(self.wiod, self.siod)  # Set up iodine interpolation function

        self.tempinterp = []
        for i in range(spectrum.ntel):
            if not spectrum.active[i]: continue
            if not spectrum.bstar:
                wtemp, stemp = get_template(spectrum.template[i], wmin, wmax)
                self.tempinterp.append(interp1d(wtemp, stemp))

        obchunk = np.copy(obspec)

        #       JDE 2016-05-24: remove CR cleaning; gave DOF <= 0 error (and fixed in extraction?)
        #        for i in range(4):
        #            obchunk[i,:] = crclean(obspec[i,:]) # remove hot/dead pixels

        self.origchunk = obspec
        self.obchunk = obchunk  # Bookkeeping for what was "cleaned" by crclean

<<<<<<< HEAD
        self.xip, self.ip = get_ip(spectrum.ipdict,wmin,wmax,order)
        ipdb.set_trace()

=======
        self.xip, self.ip = get_ip(spectrum.ipdict, wmin, wmax, order, oversamp=self.oversamp)
>>>>>>> b6d657aee7f3d991bf133d45f534be5be5b2e689
        """ List of Parameters:
        par[0 + N*parspertrace] = zguess for telescope N
        par[1 + N*parspertrace] = w0 for telescope N
        par[2 + N*parspertrace] = dw/dx for telescope N
        par[3 + N*parspertrace] = continuum shape offset for telescope N
        par[4 + N*parspertrace] = continuum shape slope for telescope N
        par[5 + N*parspertrace] = IP broadening for telescope N
        par[6 + N*parspertrace] = IP skew for telescope N
        """
        self.parspertrace = 7

        npar = self.parspertrace * spectrum.ntel
        self.initpar = np.zeros(npar)

        # the fibers are tilted, which changes the wavelength offset per telescope
        # this has been previously measured and ~static (unless the fiber assembly is moved)
        coef = np.array([0.00059673, 0.06555841])  # wavelength offset per trace...per order
        dwdtrace = np.polyval(coef, order)  # find wavelength offset per trace for this order
        offset = np.arange(spectrum.ntel)[::-1] * dwdtrace

        # parameter properties for MPYFIT
        self.parinfo = [{'fixed': False, 'limited': (False, False), 'limits': (None, None), 'relstep': 0.} for i in
                        range(npar)]

        tel = 0
        for i in range(spectrum.ntel):

            # don't fit the spectrum if it wasn't active
            if not spectrum.active[i]: continue

            # redshift guess (may tie these together for each trace, if same object)
            self.initpar[0 + tel * self.parspertrace] = spectrum.zguess[i]
            self.parinfo[0 + tel * self.parspertrace]['relstep'] = 0.01
            if spectrum.bstar: self.parinfo[0 + tel * self.parspertrace]['fixed'] = True

            # wavelength zeropoint guess
            self.initpar[1 + tel * self.parspertrace] = w0g + offset[i]
            self.parinfo[1 + tel * self.parspertrace]['relstep'] = 1e-6
            if juststar: self.parinfo[1 + tel * self.parspertrace]['fixed'] = True

            # wavelength dispersion guess (may tie these together for each trace)
            self.initpar[2 + tel * self.parspertrace] = dwg
            self.parinfo[2 + tel * self.parspertrace]['relstep'] = 0.005
            if juststar: self.parinfo[2 + tel * self.parspertrace]['fixed'] = True

            # continuum offset guess
            self.initpar[3 + tel * self.parspertrace] = np.amax(self.obchunk[i, :])

            # continuum slope guess
            self.initpar[4 + tel * self.parspertrace] = 0.0

            # IP broadening guess
            self.initpar[5 + tel * self.parspertrace] = 0.2
            self.parinfo[5 + tel * self.parspertrace]['limited'] = (True, True)
            self.parinfo[5 + tel * self.parspertrace]['limits'] = (0.1, 4.0)
            if fixip: self.parinfo[5 + tel * self.parspertrace]['fixed'] = True

            # IP skew guess
            self.initpar[6 + tel * self.parspertrace] = 0.0
            self.parinfo[6 + tel * self.parspertrace]['limited'] = (True, True)
            self.parinfo[6 + tel * self.parspertrace]['limits'] = (-5.0, 5.0)
            if fixip: self.parinfo[6 + tel * self.parspertrace]['fixed'] = True

            tel += 1

        xstep = 1 / self.oversamp
        self.dxip = xstep
        self.initmod = self.model(self.initpar)

    def __call__(self, par):  # For EMCEE
        model = self.model(par)
        if model == None: return 0.0  # zero likelihood
        good = np.where(self.active)
        lnprob = (self.obchunk[good, :][0] - model) ** 2
        return -lnprob[3:len(lnprob) - 1].sum()

    def model(self, par):  # For other solvers such as MPYFIT

        model = None
        tel = 0

        for i in range(self.ntel):

            if not self.active[i]: continue

            # redshift
            z = par[0 + tel * self.parspertrace]

            center_pix = self.xover[len(self.xover) / 2]
            # observed wavelength scale
            wobs = par[1 + tel * self.parspertrace] + par[2 + tel * self.parspertrace] * self.xchunk

            # oversampled wavelength scale
            wover = par[1 + tel * self.parspertrace] + par[2 + tel * self.parspertrace] * self.xover

            # create continuum shape, defined at center pixel
            contf = par[3 + tel * self.parspertrace] + par[4 + tel * self.parspertrace] * self.xover

            # instrumental profile
            sigma = par[5 + tel * self.parspertrace]
            alpha = par[6 + tel * self.parspertrace]
            sknorm = skewnorm(self.xip, 0.0, sigma, alpha)
            ip = numconv(sknorm, self.ip)  # Convolve Zemax IP with local broadening
            ip = ip / ip.sum() / self.oversamp  # Normalize convolved IP

            # force centering IP, try to break w0-alpha degeneracy, Sharon X. Wang July 2016
            center_pos = simps(self.xip*ip, dx=1.0 / self.oversamp) / simps(ip, dx=1.0 / self.oversamp)
            pad_len = 10
            ip_ext = np.append(np.append(np.zeros(pad_len), ip), np.zeros(pad_len))
            xip_pad = np.arange(self.xip[-1] + 1.0 / self.oversamp,
                                self.xip[-1] + 1.0 / self.oversamp * (pad_len + 0.9), 1.0 / self.oversamp)
            xip_ext = np.append(np.append(-xip_pad[::-1], self.xip), xip_pad)
            xip_ext -= center_pos  # shift IP to center
            shift_ip_func = interp1d(xip_ext, ip_ext)
            ip = shift_ip_func(self.xip)  # re-centered!

            if self.bstar:
                tempover = 1.0
            else:
                # Doppler-shift stellar spectrum, put onto same oversampled scale as iodine
                try:
                    tempover = self.tempinterp[tel](wover * (1.0 - z))
                except ValueError:
                    tempover = wover * np.inf
            if self.juststar:
                iodover = contf * tempover
            else:
                try:
                    iodover = self.iodinterp(wover) * contf * tempover
                except ValueError:
                    iodover = wover * np.inf

            # oversampled model spectrum
            sover = numconv(iodover, ip)
            if tel == 0:
                try:
                    model = rebin(wover, sover, wobs)
                except:
                    model = wobs * np.inf
            else:
                try:
                    model = np.vstack((model, rebin(wover, sover, wobs)))
                except:
                    model = np.vstack((model, wobs * np.inf))

            # Single trace model evaluation for MCMC, Sharon X. Wang July 2016
            if (len(par) == self.parspertrace):
                return model

            tel += 1

        #        except ValueError:
        #            print "iodine: ", self.wiod.min(), self.wiod.max()
        #            print "wover:  ", wover.min(), wover.max()
        #            print "WLS pars: ", par[1:4]

        return model

    def lm_model(self, x, *par):
        model = self.model(par)
        # print par[0], par[1]
        return model

    def mpfit_model(self, par, fjac=None, x=None, y=None, err=None):
        model = self.model(par).flatten()

        good = np.where(self.active)
        obs = self.obchunk[good, :][0].flatten()
        err = np.sqrt(obs)

        bad = np.where(obs == 0)
        err[bad] = float('inf')

        return (obs - model) / err

    def fprof(self, par):
        oversamp = 1.0 / self.dxip
        xip = self.xip
        cenwid = par[0]
        cengau = jjgauss(xip, 1., 0, cenwid)
        sh_sep = par[1]
        sh_amp = par[2]
        lgau = jjgauss(xip, sh_amp, -sh_sep, cenwid)
        rgau = jjgauss(xip, sh_amp, sh_sep, cenwid)
        f = par[3]
        shoulders = f * lgau + (1 - f) * rgau
        ip = cengau + shoulders
        return ip / (ip.sum() / oversamp)

    def gpfunc(self, pars):
        ip = jjgauss(self.xip, 1.0, 0.0, pars[0])
        for i, sig in enumerate(self.ipsig):
            gau = jjgauss(self.xip, pars[i + 1], self.ippix[i], sig)
            ip += gau
        return ip / ip.sum() / self.dxip

    def lnprior(self, par, tel):
        """
        Log(Prior), natural log of priors, for fitter
        Note that par definition is rigid:
        par[0] - redshift, z
        par[1] - wavelength zero point, w0
        par[2] - wavelength dispersion scale, dwdx
        par[3] - continuum offset
        par[4] - continuum slope
        par[5] - IP parameter, sigma for skewed norm shape
        par[6] - IP parameter, alpha for skewed norm shape
        created by Sharon X. Wang, July 26 2016
        """
        # Flat priors for all parameters, around least-chisq best fits
        par0 = self.par[tel * self.parspertrace:(tel + 1) * self.parspertrace]

        # z: initial guess +/-31 km/s RV range, covering entire BC shift range (Earth's velocity around sun)
        cz_cond = (par[0] < (par0[0] + 1.1e-4)) and \
                  (par[0] > (par0[0] - 1.1e-4))

        # w0: +/-1 A range for wavelength zero point
        w0_cond = (par[1] < (par0[1] + 1.0)) and \
                  (par[1] > (par0[1] - 1.0))

        # dwdx: some realistic range for MINERVA, normally it's between 0.016 and 0.030
        dw_cond = (0.01 <= par[2] <= 0.04)

        # continuum slope
        cont_cond = (0 < par[3] < par0[3] * 2.0) and \
                    ((par0[4] - abs(par0[4] * 0.5)) < par[4] < (par0[4] + abs(par0[4] * 0.5)))

        # IP, a bit more than bounds set by mpfitter to allow jiggle initial walkers
        ip_cond = (0.01 <= par[5] <= 5.0) and (-5.1 <= par[6] <= 5.1)

        if cz_cond and w0_cond and dw_cond and cont_cond and ip_cond:
            return 0.0
        return -np.inf

    def lnlikelihood(self, par, tel):
        """
        Log(Likelihood), natural log of likelihood function for a model, for emcee_fitter
        See lnprior for definition for par.
        tel designates which telescope/trace.
        created by Sharon X. Wang, July 26 2016
        """
        current_model = self.model(par)
        if not np.isfinite(current_model[0]):
            ipdb.set_trace()
            return -np.inf
        resid = self.obchunk[tel, :] - current_model

        return -0.5 * np.sum(resid ** 2 / self.obchunk[tel, :])

    def lnposterior(self, par, tel):
        """
        Log(Posterior), natural log of posterior = likelihood*prior, for emcee_fitter
        created by Sharon X. Wang, July 26 2016
        """
        lp = self.lnprior(par, tel)
        return lp + self.lnlikelihood(par, tel) if np.isfinite(lp) else -np.inf

    def emcee_fitter(self, nwalkers, niter, nburn):
        # p0 = self.initpar
        s, p0 = self.mpfitter()  # initialize parameters using least-sq fit
        self.par = p0  # update self.par to pass onto self.lnprior

        bpar = np.array([])
        sampler_list = []
        for tel, is_active in enumerate(self.active):
            if is_active:
                this_p0 = p0[tel * self.parspertrace:(tel + 1) * self.parspertrace]
                ndims = len(this_p0)
                p0arr = np.array([])

                # jiggle around p0 to give different walkers different initial guesses
                jiggle_amp = np.array([0.001, 2e-5, 0.02, 0.02, 0.02, 0.02, 0.02])
                for i, p in enumerate(this_p0):
                    if p != 0:
                        amp = jiggle_amp[i % len(jiggle_amp)] * p
                    else:
                        amp = jiggle_amp[i % len(jiggle_amp)]
                    randp = p + amp * (rand.random(nwalkers) - 0.5)
                    p0arr = np.append(p0arr, randp)
                p0arr.shape = (ndims, nwalkers)
                p0arr = p0arr.transpose()

                # MCMC
                sampler = emcee.EnsembleSampler(nwalkers, ndims, self.lnposterior, args=(tel,))
                print "Starting burn-in with " + str(nburn) + " links"
                pos, prob, state = sampler.run_mcmc(p0arr, nburn)
                sampler.reset()
                print "Starting main MCMC run with " + str(nwalkers) + " walkers and " + str(niter) + " links."
                foo = sampler.run_mcmc(pos, niter, rstate0=state)

                # get the best pars, mode of each posterior
                m = np.argmax(sampler.flatlnprobability)
                this_bpar = sampler.flatchain[m, :]
                bpar = np.append(bpar, this_bpar)
                sampler_list.append(sampler)
            else:
                bpar = np.append(bpar, self.par[tel * self.parspertrace:(tel + 1) * self.parspertrace])

        # return self.model(bpar), bpar
        return sampler_list

    def lm_fitter(self):
        bestpar, cov = curve_fit(self.lm_model, self.xchunk, self.obchunk, p0=self.initpar)
        return self.model(bestpar), bestpar

    def mpfitter(self):
        # m = mpfit(self.mpfit_model, self.initpar, parinfo=self.parinfo, xtol=1e-8, quiet=True)
        pfit, results = mpyfit.fit(self.mpfit_model, self.initpar, parinfo=self.parinfo, maxiter=500, xtol=1e-9,
                                   ftol=1e-9)
        model = self.model(pfit)
        self.par = pfit
        self.mod = model
        good = np.where(self.active)
        self.resid = self.obchunk[good, :][0] - model
        npar = len(self.par)
        dim = self.obchunk.shape
        ntel = dim[0]
        npix = dim[1]
        dof = npix - self.parspertrace  # neglects any fixed parameters!
        #        dofpertrace = npix - npar
        #        self.chiarr = np.sqrt(np.sum((self.resid)**2/self.mod, axis=1) / dofpertrace)
        #        bad = np.where(self.chiarr > 3)
        """
        if bad[0]:
            nbad = len(bad[0])
            for i in range(nbad):
                print bad[0][i], 'is bad'
        """
        sigmasq = self.obchunk[good, :][0]  # sigma = sqrt(Ncts), sigma^2 = Ncts

        # mask bad values
        bad = np.where(sigmasq == 0.0)
        sigmasq[bad] = float('inf')

        chisq = np.sum(self.resid ** 2 / sigmasq, axis=1)

        if len(np.where(np.isnan(chisq))[0]) != 0: ipdb.set_trace()

        redchi = chisq / dof
        self.chisq = chisq
        self.redchi = redchi
        self.chi = np.sqrt(redchi)  # sqrt(chi^2) =~ number of sigmas

        wav = np.append(np.append(-1, self.xchunk), 1) * pfit[2] + pfit[1]
        dV = np.median(wav - np.roll(wav, -1)) / wav * self.c
        if self.bstar:
            self.weight = np.zeros(self.ntel)
        else:
            self.weight = np.array([])
            tel = 0
            for i in range(ntel):
                if not self.active[i]: continue
                I = self.tempinterp[tel](wav)
                dI = I - np.roll(I, -1)
                dIdV = dI[1:len(wav) - 1] / dV[1:len(wav) - 1]
                sigmaV = 1.0 / np.sqrt(np.sum(dIdV ** 2 / I[1:len(wav) - 1]))
                self.weight = np.append(self.weight, 1.0 / sigmaV ** 2)
                tel += 1
        return model, pfit


def grind(obsname, plot=False, printit=False, bstar=False, juststar=False):
    print 'Fitting ', obsname
    start = timer()
    order = np.arange(2, 23)
    nord = len(order)
    #    dpix = 128
    dpix = 90
    pixel = np.arange(30, 1922, dpix)
    npix = len(pixel)
    # charr = np.empty((npix,nord), dtype=object)
    chrec = np.zeros(npix * nord, dtype=[('pixel', int), ('order', int),
                                         ('z1', float), ('z2', float), ('z3', float), ('z4', float),
                                         ('w01', float), ('w02', float), ('w03', float), ('w04', float),
                                         ('dwdx1', float), ('dwdx2', float), ('dwdx3', float), ('dwdx4', float),
                                         ('cts1', float), ('cts2', float), ('cts3', float), ('cts4', float),
                                         ('slope1', float), ('slope2', float), ('slope3', float), ('slope4', float),
                                         ('sigma1', float), ('sigma2', float), ('sigma3', float), ('sigma4', float),
                                         ('alpha1', float), ('alpha2', float), ('alpha3', float), ('alpha4', float),
                                         ('wt1', float), ('wt2', float), ('wt3', float), ('wt4', float),
                                         ('chi1', float), ('chi2', float), ('chi3', float), ('chi4', float)])

    chrec = np.rec.array(chrec, dtype=chrec.dtype)
    spectrum = Spectrum(obsname, bstar=bstar)
    for i, Ord in enumerate(order):
        for j, Pix in enumerate(pixel):
            chstart = timer()
            if printit:
                print '------'
                print 'Order:', Ord, 'Pixel:', Pix
            ch = FourChunk(spectrum, Ord, Pix, dpix)

            chind = j + i * npix
            chrec[chind].pixel = Pix
            chrec[chind].order = Ord
            #            chrec[chind].bp = bp
            chrec[chind].z1 = chrec[chind].z2 = chrec[chind].z3 = chrec[chind].z4 = float('nan')
            chrec[chind].w01 = chrec[chind].w02 = chrec[chind].w03 = chrec[chind].w04 = float('nan')
            chrec[chind].dwdx1 = chrec[chind].dwdx2 = chrec[chind].dwdx3 = chrec[chind].dwdx4 = float('nan')
            chrec[chind].cts1 = chrec[chind].cts2 = chrec[chind].cts3 = chrec[chind].cts4 = float('nan')
            chrec[chind].slope1 = chrec[chind].slope2 = chrec[chind].slope3 = chrec[chind].slope4 = float('nan')
            chrec[chind].sigma1 = chrec[chind].sigma2 = chrec[chind].sigma3 = chrec[chind].sigma4 = float('nan')
            chrec[chind].alpha1 = chrec[chind].alpha2 = chrec[chind].alpha3 = chrec[chind].alpha4 = float('nan')
            chrec[chind].wt1 = chrec[chind].wt2 = chrec[chind].wt3 = chrec[chind].wt4 = float('nan')
            chrec[chind].chi1 = chrec[chind].chi2 = chrec[chind].chi3 = chrec[chind].chi4 = float('nan')
            parspertrace = 7

            if ch.nactive == 0: continue

            # mod, bp = ch.mpfitter() # Full fit
            #            try: mod, bp = ch.mpfitter() # Full fit
            #            except: return # no template for observation

            # Sharon MCMC test
            mod, bp = ch.emcee_fitter(30, 1000, 200)

            tel = 0
            for ii in range(ch.ntel):

                if not ch.active[ii]: continue

                exec ("chrec[chind].z%s     = bp[0 + tel*parspertrace]" % (ii + 1))
                exec ("chrec[chind].w0%s    = bp[1 + tel*parspertrace]" % (ii + 1))
                exec ("chrec[chind].dwdx%s  = bp[2 + tel*parspertrace]" % (ii + 1))
                exec ("chrec[chind].cts%s   = bp[3 + tel*parspertrace]" % (ii + 1))
                exec ("chrec[chind].slope%s = bp[4 + tel*parspertrace]" % (ii + 1))
                exec ("chrec[chind].sigma%s = bp[5 + tel*parspertrace]" % (ii + 1))
                exec ("chrec[chind].alpha%s = bp[6 + tel*parspertrace]" % (ii + 1))
                exec ("chrec[chind].wt%s    = ch.weight[tel]" % (ii + 1))
                exec ("chrec[chind].chi%s   = ch.chi[tel]" % (ii + 1))
                tel += 1

            if plot:
                col = ['b', 'g', 'y', 'r']

                tel = 0
                for ii in range(ch.ntel):
                    if not ch.active[ii]: continue
                    wav = bp[1 + tel * parspertrace] + bp[2 + tel * parspertrace] * np.arange(mod.shape[1])
                    pl.plot(wav, ch.obchunk[ii, :], col[ii] + '.')
                    pl.plot(wav, mod[ii, :], col[ii])
                    pl.plot(wav, ch.resid[ii, :] + 0.6 * mod.flatten().min(), col[ii] + '.')
                    tel += 1

                pl.xlabel('Wavelength [Ang]')
                pl.ylabel('Flux [cts/pixel]')
                pl.xlim((wav.min(), wav.max()))
                pl.show()
            # charr[j, i] = ch
            if printit:
                print 'chi^2 = ', ch.chi
                if len(np.where(np.isnan(ch.chi))[0]) != 0: ipdb.set_trace()
                end = timer()
                print 'Chunk time: ', (end - chstart), 'seconds'

            end = timer()
    end = timer()

    spectrum.h.close()
    print 'Total time: ', (end - start) / 60., 'minutes'
    return chrec


'''
def getparr(charr, plot=False):
    sh = charr.shape
    if len(sh) < 2: ipdb.set_trace()
    nc = sh[0]
    nord = sh[1]
    npar = len(charr[0,0].par)
    pararr = np.empty((nc,nord,npar+4), dtype=float)
    nxip = len(charr[0,0].newip)
    iparr = np.zeros((nxip, nc, nord))
    for i in range(nc):
        for j in range(nord):
            iparr[:,i,j] = charr[i,j].newip
            if plot: pl.plot(charr[i,j].newip)
            pararr[i,j,:] = np.append(charr[i,j].par, charr[i,j].chiarr)
    if plot: pl.show()       
    return pararr, iparr

def getpararray(obsname):

    night = obsname.split('.')[0]
    ofile = getpath(night=night,data=True) + '/' + obsname
    test = np.load(ofile[0])
    sh = test.shape
    parr = np.zeros((len(ofile), sh[0], sh[1], sh[2]))
    for i, ffile in enumerate(ofile):
        p = np.load(ffile)
        parr[i, :, :, :] = p
    return parr
'''


def getpath(night=''):
    hostname = socket.gethostname()
    if hostname == 'Main':
        return '/Data/kiwispec-proc/' + night
    elif hostname == 'jjohnson-mac':
        return '/Users/johnjohn/Dropbox/research/dopcode_new/MINERVA_data/'
    else:
        return '/n/home12/jeastman/minerva/data/'


#
#        print 'hostname ' + hostname + ') not recognized; exiting'
#        sys.exit()

def globgrind(globobs, bstar=False, returnfile=False, printit=False, plot=False, redo=False):
    files = glob(globobs)
    ofarr = []  # object f? array?

    for i, ffile in enumerate(files):

        ofile = os.path.splitext(ffile)[0] + '.chrec8.npy'

        firsttime = False

        # make it thread safe
        if not os.path.exists(ofile):
            open(ofile, 'a').close()
            firsttime = True

        h = fits.open(ffile)

        # if the iodine cell is not in, just fit the star without iodine
        juststar = h[0].header['I2POSAS'] != 'in'

        ofarr.append(ofile)

        if not returnfile:
            # if the user requested to redo it, it's the first time, or there's a stale empty file, run the fit
            st = os.stat(ofile)

            if redo or firsttime or (((time.time() - st.st_mtime) > 3600) and (st.st_size == 0.0)):
                chrec = grind(ffile, bstar=bstar, juststar=juststar, printit=printit, plot=plot)
                if chrec != None:
                    np.save(ofile, chrec)
                    print ofile, h[0].header['I2POSAS']
    return ofarr


def globgrindall(shuffle=False):
    datadirs = glob(getpath() + '*')
    if shuffle: random.shuffle(datadirs)
    for datadir in datadirs:
        #        ofarr = globgrind(datadir + '/*daytimeSky*.proc.fits', bstar=False, returnfile=False, printit=True, plot=False)
        #        ofarr = globgrind(datadir + '/*HD*.proc.fits', bstar=False, returnfile=False, printit=True, plot=False)
        #        ofarr = globgrind(datadir + '/*HR*.proc.fits', bstar=True, returnfile=False, printit=True, plot=False)

        ofarr = globgrind(datadir + '/*HD122064*.proc.fits', bstar=False, returnfile=False, printit=True, plot=False)


# ofarr = globgrind(datadir + '/*HD185144*.proc.fits', bstar=False, returnfile=False, printit=True, plot=False)
#        ofarr = globgrind(datadir + '/*daytimeSky*.proc.fits', bstar=False, returnfile=False, printit=True, plot=False)

# ofarr = globgrind('/Data/kiwispec-proc/n20160212/n20160212.HD191408A.0017.proc.fits',bstar=False,returnfile=False,printit=True,plot=False)





globgrind('/Data/kiwispec-proc/n20160626/n20160626.daytimeSkyExpmeter.0047.proc.fits',bstar=False, returnfile=False, printit=True, plot=False)
ipdb.set_trace()



globgrindall(shuffle=True)
ipdb.set_trace()


'''
# a quality set of daytime sky spectra
globobs = getpath(night='n20160305') + '/n20160305.daytimeSky.008*.proc.fits'
ofarr = globgrind(globobs, bstar=False, returnfile=False, printit=True, plot=True)
ipdb.set_trace()

# a quality spectrum of HD9407
globobs = getpath(night='n20160505') + '/n20160505.HD*.proc.fits'
ofarr = globgrind(globobs, bstar=False, returnfile=False, printit=True, plot=False)
ipdb.set_trace()

# poor quality spectra (missing telescopes, etc)
globobs = getpath(night='n20160504') + '/n20160504.HD*.proc.fits'
ofarr = globgrind(globobs, bstar=False, returnfile=False, printit=True, plot=True)
ipdb.set_trace()

# mixed quality B star spectra
globobs = getpath(night='n20160504') + '/n20160504.HR*.proc.fits'
ofarr = globgrind(globobs, bstar=True, returnfile=False, printit=True, plot=True)
ipdb.set_trace()
'''

#obsname = getpath(night='n20160305') + '/n20160305.daytimeSky.0065.proc.fits'
#chrec = grind(obsname, plot=False, printit=True)
#parr, iparr = getparr(charr) #This no longer needed with CHREC variable




ipdb.set_trace()
parray = getpararray(ofarr)
#######################

ipdb.set_trace()

#gfile = getpath(night='n20160323') + '/n20160323.HR4828.00*.proc.fits'
#globobs = 'n20160323.HR4828.00*.proc.fits'
globobs = 'n20160410.HR5511.00*.proc.fits'

ofarr = globgrind(globobs, bstar=True, returnfile=False)
parray = getpararray(ofarr)

wr = (parray[:,:,:,1]- np.median(parray[:,:,:,1], axis=0))
sh = wr.shape
wr = wr.reshape((sh[0], sh[1]*sh[2]))
medwr = np.median(wr, axis=1)
#pl.plot(medwr, 'o')
g = glob(globobs)

for i, ff in enumerate(g):
    h = fits.open(ff)
    this = Time(h[0].header['DATE-OBS'])
    if i == 0:
        t = this.jd
        temp = float(h[0].header['TEMPD2'])
    else:
        t = np.append(t, this.jd)
        temp = np.append(temp, float(h[0].header['TEMPD2']))
    h.close()

coef = np.polyfit(t-t.min(), medwr/5500.*3e8, 1)
fit = np.polyval(coef, t-t.min())
pl.plot((t-t.min())*24, medwr/5500.*3e8, 'o')
pl.plot((t-t.min())*24, fit)
pl.ylabel('Wavelength Shift [m/s]')
pl.xlabel('Time [hrs]')
pl.show()

#pl.plot(temp, medwr/5500.*3e8, 'o')
pl.plot(t-t.min(), temp, 'o')
#pl.xlabel('Temperature [degrees C]')
#pl.ylabel('Wavelength Shift [m/s]')
pl.xlabel('Time')
pl.ylabel('Temperature [degrees C]')

pl.show()

#charr = grind(ffile, bstar=True, plot=True, printit=True)
#parr, iparr = getparr(charr)
#pl.plot(parr[:,:,1].T.flatten(), parr[:,:,14].T.flatten(), '.')
#pl.ylim((1,3))
#pl.show()


#ffile = getpath(night='n20160323') + '/n20160323.HR4828.0020.proc.fits'
obsname = 'n20160305.daytimeSky.0065.proc.fits' #iodine
#ffile = getpath(night='n20160305') + '/n20160305.daytimeSky.0069.proc.fits'
wls = np.load('templates/MC_bstar_wls.air.npy')

ffile = getpath(night='n20160305') + '/'+obsname
h = fits.open(ffile)
lpix = 1400
dpix = 100
rpix = lpix + dpix
Ord = 3
w0 = wls[lpix, Ord]
dw = wls[lpix+1, Ord] - w0
wguess = np.array([w0, dw])
#ch = FourChunk(ffile, Ord, lpix, dpix, bstar=False, juststar=True, fixip=False)
ch = FourChunk(obsname, Ord, lpix, dpix, fixip=False)

#for i in range(len(ch.initpar)):
#    print 'Par', i, 'value', ch.initpar[i]

col = ['b', 'g', 'y', 'r']
#mod = ch.model(ch.initpar)
mod, bp = ch.mpfitter()
wav = bp[1] + bp[2]*np.arange(mod.shape[1])

for i in range(4): 
    woff = bp[3]*i
    pl.plot(wav-woff, ch.obchunk[i, :], col[i]+'.')
    pl.plot(wav-woff, mod[i, :], col[i])
    pl.plot(wav-woff, ch.resid[i, :]+0.6*mod.flatten().min(), col[i]+'.')
pl.xlabel('Wavelength [Ang]')
pl.ylabel('Flux [cts/pixel]')
pl.show()

#print h[0].data[:, 13, 500:600].shape
#h.close()

"""
