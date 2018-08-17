import glob, subprocess

files = glob.glob("D:/minerva/data/*/*.fits")
for filename in files:
    print 'Compressing ' + filename
    subprocess.call(['cfitsio/fpack.exe','-D',filename])
