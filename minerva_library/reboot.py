import imager, cdk700
import os, socket, time, subprocess, psutil
import ipdb

computername = socket.gethostname()
if computername == 'Minervared2-PC':
    imager_config = 'imager_mred.ini'
    telescope_config = 'telescope_mred.ini'
else:
    telnum = socket.gethostname()[1]
    imager_config = 'imager_t' + telnum + '.ini'
    telescope_config = 'telescope_' + telnum + '.ini'

base_directory = 'C:/minerva-control//'

for p in psutil.process_iter():

    print p
    
    try:
        print p.name()
        if p.name() == 'MaxIm_DL.exe':
            print 'here'
            try:
                # create a camera object
                camera = imager.imager(imager_config,base_directory)
                # gracefully disconnect from the camera
                camera.disconnect_camera()
                # kill MaxIm
                p.kill()
#                subprocess.call(['Taskkill','/IM','MaxIm_DL.exe','/F'])
            except:
                print 'failed to kill maxim'
                pass
        elif p.name() == 'PWI.exe':
            try:
                # create a telescope object
                telescope = cdk700.CDK700(telescope_config, base_directory)
                # gracefully disconnect from the telescope
                telescope.shutdown()
                # kill PWI
                p.kill()
#                subprocess.call(['Taskkill','/IM','PWI.exe','/F'])
            except: pass
    except: pass

# reboot computer
os.system('shutdown -r -t 60')


