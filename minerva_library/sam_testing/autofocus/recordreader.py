import glob
import numpy as np
import matplotlib.pyplot as plt
import ipdb
import itertools

def get_af_data(tele_num,night):
    path = '/Data/t%s/%s/'%(str(tele_num),night)
    print('Getting autorecords from %s'%(path))
    files = glob.glob(path+'*autorecord*')
    data_dict = {}
    first_flag = True
    for filename in files:
        with open(filename) as af_file:
            header = af_file.readline()
            data = af_file.readline()
        ind = 0
        if first_flag:
            first_flag = False
            for key in header.split():
                data_dict[key] = []
        try:
            temp_list = [float(x) for x in data.split()]
            for key in header.split():
                data_dict[key].append(temp_list[ind])
                ind+=1
        except:
            pass

    for key in data_dict.keys():
        data_dict[key] = np.array(data_dict[key])
    return data_dict


if __name__ == '__main__':
    ipdb.set_trace()
    tele_nums = ['1','2','3','4']
    while True:
        tele_data = {}
        dates = raw_input('Enter glob compatible dates:\n')
        for num in tele_nums:
            tele_data[num] = get_af_data(num,dates)



        ind = 0
        plt.figure()
        
        for ind in np.arange(len(tele_nums)):
            plt.subplot(2,2,ind+1)
            print tele_nums[ind]
            pltdict = tele_data[tele_nums[ind]]
            pltind = np.where(pltdict['Old']!=pltdict['New'])[0]
            plt.title(tele_nums[ind])
            ax = plt.gca()
            for key in ['Tamb','TM1','TM2','TM3','Tback']:
                color = next(ax._get_lines.color_cycle)
                plt.plot(pltdict[key][pltind],pltdict['New'][pltind],'-',\
                             label=key, color = color)
                plt.plot(pltdict[key][pltind],pltdict['New'][pltind],'o',\
                             color = color)
#        ind+=1
                plt.margins(0.1)
                plt.ylabel('Focus Position [$\mu$m]')
                plt.xlabel('Temperature [C]')
                plt.legend()
        plt.show()
    ipdb.set_trace()
            
