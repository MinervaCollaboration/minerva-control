import numpy as np
import matplotlib.pyplot as plt
import subprocess
import newauto
import ipdb


steps = 20
step = .25
poslist = np.linspace(-step*steps/2,step*steps/2,steps)

datapath = '/Data/t3/n20151016/'

sexfiles = ['autofocus2.sex','debtest.sex']

filenums = np.linspace(70,89,20)

filenames = []



for num in filenums:
    filenames.append('n20151016.T3.autofocus.V.01'+str(int(num))+'.fits.fz')



#for name in filenames:
#    subprocess.call(['funpack','-O','./'+name.split('.fz')[0],datapath+name])


catfiles = []

tothfr = []
totstd = []
bestfocus = []
coeffs = []
hfr_med = []
hfr_std = []

ipdb.set_trace()
for name in filenames:
    try: 
        med,std = newauto.get_hfr_med('./'+newauto.sextract('./',name.split('.fz')[0],sexfile=sexfiles[1]))
        hfr_med.append(med)
        hfr_std.append(std)
    except:
        print 'failed getting hfr and shit'
        med = -999
        std = 999
        hfr_med.append(med)
        hfr_std.append(std)

ipdb.set_trace()
nphfr = np.array(hfr_med)
npstd = np.array(hfr_std)
goodind = np.where(nphfr<>-999)[0]
newfoc = newauto.fitquadfindmin(poslist[goodind],nphfr[goodind])

for i in range(len(sexfiles)):
    hfr_med = []
    hfr_std = []

    for name in filenames:
        med,std = newauto.get_hfr_med('./'+newauto.sextract('./',name.split('.fz')[0],sexfile=sexfiles[i]))
        hfr_med.append(med)
        hfr_std.append(std)

    #here it is, not sure why i converted them here but it must have made it work
    hfr_med = np.array(hfr_med)
    hfr_std = np.array(hfr_std)

#    coeffs.append( np.polyfit(poslist,hfr_med,2,w=(1/hfr_std)))
#    ipdb.set_trace()
    z = newauto.fitquadfindmin(poslist,hfr_med,hfr_std)
    coeffs.append( np.polyfit(poslist[1:],hfr_med[1:],2,w=(1/hfr_std[1:])))

    bestfocus.append( -coeffs[i][1]/(2.*coeffs[i][0]))

    tothfr.append(hfr_med)
    totstd.append(hfr_std)
xfit = np.linspace(poslist.min(),poslist.max(),100)

ipdb.set_trace()
for i in range(len(sexfiles)):
    label = sexfiles[i] + ' %e '%(bestfocus[i])
    plt.plot(poslist,tothfr[i],'o',label=label)
    plt.plot(xfit,coeffs[i][0]*xfit**2+coeffs[i][1]*xfit+coeffs[i][2],label = sexfiles[i])
    plt.errorbar(poslist,tothfr[i],yerr=totstd[i],linestyle='None')
plt.legend()
#plt.plot(xfit,coeffs[0]*xfit**2 + coeffs[1]*xfit + coeffs[2],'r')
plt.show()

ipdb.set_trace()
