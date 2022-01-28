import numpy as np
import matplotlib.pyplot as plt
import glob
import os

import af_utils

def plot_autofocus(night):
    img_filenames = []
    for j in range(1, 5):
        filepath = '/Data/t' + str(j) + '/' + night + '/'
        autorecords = glob.glob(filepath + night + '.T' + str(j) +'.autorecord.*.txt')
        if len(autorecords) == 0:
            continue
        img_filename = filepath + night + '.T' + str(j) +'.autorecord.png'

        N_im = len(autorecords)
        N_x = np.ceil(np.sqrt(N_im))
        N_y = np.ceil(float(N_im) / N_x)
        plt.figure(figsize = (6 * N_x, 4 * N_y))

        for i, autorecord in enumerate(autorecords):
            fail = False
            
            im0 = autorecord.split('.')[4]
            im1 = autorecord.split('.')[5]

            with open(autorecord) as f:
                f.readline()
                fm = f.readline()
                fm = fm.split('#')[1].split()

                old_best_focus = int(float(fm[0]))
                try:
                    new_best_focus = int(float(fm[1]))
                except:
                    new_best_focus = old_best_focus
                    fail = True


                if new_best_focus == old_best_focus:
                    fail = True

            plt.subplot(N_y, N_x, i + 1)
            ax = plt.gca()

            af = np.loadtxt(autorecord)

            poslist = af[:, 1]
            focusmeas_list = af[:, 2]
            goodind = np.where(np.logical_not(np.isnan(focusmeas_list)))[0]

            ax.plot(poslist, focusmeas_list, 'bo')
            ax.set_xlim(new_best_focus - 3000, new_best_focus + 3000)
            ax.set_ylim(np.min(focusmeas_list[goodind]) - np.max(focusmeas_list[goodind]) * 0.4, np.max(focusmeas_list[goodind]) + 1)
            ax.set_title('T' + str(j) + '.' + im0 + '.' + im1)


            pos = np.linspace(new_best_focus - 3000, new_best_focus + 3000)
            
            coeff = af_utils.quadfit_rlsq(poslist[goodind], focusmeas_list[goodind])
            if not np.any(np.isnan(coeff)):
                quad = coeff[0] * pos ** 2 + coeff[1] * pos + coeff[2]
                ax.plot(pos, quad, 'b--')
            
            ax.vlines(old_best_focus, - 1, np.max(focusmeas_list[goodind]) + 1, 'red', linestyle=':',
                       label = 'Old best focus = {}'.format(old_best_focus))
            if fail:
                ax.vlines(new_best_focus, - 1, np.max(focusmeas_list[goodind]) + 1, 'red', label = 'Autofocus failed; used old best focus')
            else:
                ax.vlines(new_best_focus, - 1, np.max(focusmeas_list[goodind]) + 1, 'red', label = 'New best focus = {}'.format(new_best_focus))
            ax.legend(loc = 'lower left')
        plt.savefig(img_filename, bbox_inches='tight', dpi = 72)
        plt.show()
        img_filenames.append(img_filename)
    return img_filenames
