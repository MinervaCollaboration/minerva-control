import main, glob, os, subprocess, ipdb, pyfits, math, logging, time

#site, aqawan, telescope, imager = main.prepNight()


# setting up main logger
fmt = "%(asctime)s [%(filename)s:%(lineno)s - %(funcName)s()] %(levelname)s: %(message)s"
datefmt = "%Y-%m-%dT%H:%M:%S"

#    logging.basicConfig(level=logging.DEBUG, format=fmt, datefmt=datefmt)
logger = logging.getLogger('main')
formatter = logging.Formatter(fmt,datefmt=datefmt)
formatter.converter = time.gmtime
    
fileHandler = logging.FileHandler('logs/n20150521/main.log', mode='a')
fileHandler.setFormatter(formatter)

console = logging.StreamHandler()
console.setFormatter(formatter)
console.setLevel(logging.INFO)
    
logger.setLevel(logging.DEBUG)
logger.addHandler(fileHandler)
logger.addHandler(console)

files = glob.glob("D:/minerva/data/*/*.fits*")
#files = glob.glob("D:/minerva/data/n20150603/*.fits*")
for filename in files:

    if not "Bias" in filename and not "Dark" in filename and not "SkyFlat" in filename:
        baseName = os.path.splitext(filename)[0]
        if 'fits' in baseName:
            baseName = os.path.splitext(baseName)[0]
            ext = 1
        else: ext = 0

        if os.path.exists(baseName + '.new'):

            f = pyfits.open(filename, mode='update')

            # is it close to what we thought?
            origcd11 = float(f[ext].header['CD1_1'])
            origcd12 = float(f[ext].header['CD1_2'])
            origPA = 180.0/math.pi*math.atan2(origcd12,-origcd11)
            origracen = float(f[ext].header['CRVAL1'])*math.pi/180.0
            origdeccen = float(f[ext].header['CRVAL2'])*math.pi/180.0

            f[ext].header['WCSSOLVE'] = 'True'

            # copy the WCS solution to the file
            newhdr = pyfits.getheader(baseName + '.new')
            f[ext].header['WCSAXES'] = newhdr['WCSAXES']
            f[ext].header['CTYPE1'] = newhdr['CTYPE1']
            f[ext].header['CTYPE2'] = newhdr['CTYPE2']
            f[ext].header['EQUINOX'] = newhdr['EQUINOX']
            f[ext].header['LONPOLE'] = newhdr['LONPOLE']
            f[ext].header['LATPOLE'] = newhdr['LATPOLE']
            f[ext].header['CRVAL1'] = newhdr['CRVAL1']
            f[ext].header['CRVAL2'] = newhdr['CRVAL2']
            f[ext].header['CRPIX1'] = newhdr['CRPIX1']
            f[ext].header['CRPIX2'] = newhdr['CRPIX2']
            f[ext].header['CUNIT1'] = newhdr['CUNIT1']
            f[ext].header['CUNIT2'] = newhdr['CUNIT2']
            f[ext].header['CD1_1'] = newhdr['CD1_1']
            f[ext].header['CD1_2'] = newhdr['CD1_2']
            f[ext].header['CD2_1'] = newhdr['CD2_1']
            f[ext].header['CD2_2'] = newhdr['CD2_2']
            f[ext].header['IMAGEW'] = newhdr['IMAGEW']
            f[ext].header['IMAGEH'] = newhdr['IMAGEH']
            f[ext].header['A_ORDER'] = newhdr['A_ORDER']
            f[ext].header['A_0_2'] = newhdr['A_0_2']
            f[ext].header['A_1_1'] = newhdr['A_1_1']
            f[ext].header['A_2_0'] = newhdr['A_2_0']
            f[ext].header['B_ORDER'] = newhdr['B_ORDER']
            f[ext].header['B_0_2'] = newhdr['B_0_2']
            f[ext].header['B_1_1'] = newhdr['B_1_1']
            f[ext].header['B_2_0'] = newhdr['B_2_0']
            f[ext].header['AP_ORDER'] = newhdr['AP_ORDER']
            f[ext].header['AP_0_1'] = newhdr['AP_0_1']
            f[ext].header['AP_0_2'] = newhdr['AP_0_2']
            f[ext].header['AP_1_0'] = newhdr['AP_1_0']
            f[ext].header['AP_1_1'] = newhdr['AP_1_1']
            f[ext].header['AP_2_0'] = newhdr['AP_2_0']
            f[ext].header['BP_ORDER'] = newhdr['BP_ORDER']
            f[ext].header['BP_0_1'] = newhdr['BP_0_1']
            f[ext].header['BP_0_2'] = newhdr['BP_0_2']
            f[ext].header['BP_1_0'] = newhdr['BP_1_0']
            f[ext].header['BP_1_1'] = newhdr['BP_1_1']
            f[ext].header['BP_2_0'] = newhdr['BP_2_0']

            cd11 = float(newhdr['CD1_1'])
            cd12 = float(newhdr['CD1_2'])
            racen = float(newhdr['CRVAL1'])*math.pi/180.0
            deccen = float(newhdr['CRVAL2'])*math.pi/180.0       
    #        PA = 180.0/math.pi*math.atan2(-cd12,-cd11) # this one?
            PA = 180.0/math.pi*math.atan2(cd12,-cd11) # or this one?

            dPA = 180.0/math.pi*math.atan2(math.sin((PA-origPA)*math.pi/180.0), math.cos((PA-origPA)*math.pi/180.0))
            dRA = 648000.0/math.pi*(racen-origracen)/math.cos(deccen)
            dDec = 648000.0/math.pi*(deccen-origdeccen)
            dtheta = 648000.0/math.pi*math.acos(math.sin(deccen)*math.sin(origdeccen) + math.cos(deccen)*math.cos(origdeccen)*math.cos(racen-origracen))

#            print("Telescope PA = " + str(origPA) + '; solved PA = ' + str(PA) + '; offset = ' + str(dPA) + ' degrees')
#            print("Telescope RA = " + str(origracen) + '; solved RA = ' + str(racen) + '; offset = ' + str(dRA) + ' arcsec')
#            print("Telescope Dec = " + str(origdeccen) + '; solved Dec = ' + str(deccen) + '; offset = ' + str(dDec) + ' arcsec')
#            print("Total pointing error = " + str(dtheta) + ' arcsec')

            if abs(dPA) > 5:
                print "PA out of range for " + filename
            if dtheta > 600:
                print "Pointing error too large for " + filename
                
            f.flush()
            f.close()
            print "Updated " + filename

            # clean up extra files
            extstodelete = ['-indx.png','-indx.xyls','-ngc.png','-objs.png','.axy','.corr','.match','.new','.rdls','.solved','.wcs']
            for ext in extstodelete:
                if os.path.exists(baseName + ext):
                    os.remove(baseName + ext)

        else:            
            f = pyfits.open(filename, mode='update')
            try:
                solved = f[ext].header['WCSSOLVE']
                print filename + ' already solved'
                f.close()
            except:
                f.close()
                print "No astrometric solution for " + filename
                subprocess.call(['cfitsio/funpack.exe','-D',filename])
                baseName2 = baseName.replace("\\" , "/")
                main.getPA(baseName2 + '.fits',email=False)
                subprocess.call(['cfitsio/fpack.exe','-D',baseName2 + '.fits'])
   
