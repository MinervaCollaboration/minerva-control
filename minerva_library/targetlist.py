import json, unicodecsv
import gspread
from oauth2client.client import SignedJwtAssertionCredentials
import warnings # suppress SSL security warnings!
from collections import OrderedDict
import ipdb
import copy
import datetime

def downloadList(bstar=False):

    filename = 'MINERVA target list'
    if bstar:
        sheetname = 'B stars'
        csvname = 'bstar.csv'
    else:
        sheetname = 'targets'
        csvname = 'targets.csv'

    key = '1w7RwP8P2hMYtM3MGusw8k7gXdCHzanRZZpvnWQtGkas'

    # authenticate with JSON credentials
    json_key = json.load(open('../credentials/MINERVA_Key.json'))
    scope = ['https://spreadsheets.google.com/feeds']
    credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'], scope)
    gc = gspread.authorize(credentials)

    # open the spreadsheet and worksheet
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wks = gc.open_by_key(key)
        sheet = wks.worksheet(sheetname)

    # export to CSV (for backup)
    with open(csvname, 'wb') as f:
        writer = unicodecsv.writer(f)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            writer.writerows(sheet.get_all_values())


def rdlist(bstar=False, update=True):

    if update:
        try:
            downloadList(bstar=bstar)
        except:
            print "unable to download target file, using old file"

    if bstar:
        csvname = 'bstar.csv'
    else:
        csvname = 'targets.csv'

    # parse the CSV file                                        
    with open(csvname,'rb') as f:
        reader = unicodecsv.reader(f)
        headers = reader.next()
        targetlist = {}
        for h in headers:
            targetlist[h.split('(')[0].strip()] = []
        for row in reader:
            for h,v in zip(headers,row):
                targetlist[h.split('(')[0].strip()].append(v)
        return targetlist


# make a list of target dictionaries for each (active) target based on the target spreadsheet
def mkdict(name=None, bstar=False, includeInactive=False):

    targetlist = rdlist(bstar=bstar)

    targets = []
    for i in range(len(targetlist['name'])):
        target = OrderedDict()
        target['name'] = targetlist['name'][i]
        target['ra'] = float(targetlist['ra'][i])
        target['dec'] = float(targetlist['dec'][i])
        target['starttime'] = "2015-01-01 00:00:00"
        target['endtime'] = "2115-01-01 00:00:00"
        target['spectroscopy'] = True
        target['filter'] = ["rp"]
        target['num'] = [1]
        target['exptime'] = [float(targetlist['exptime'][i])]
        target['fauexptime'] = 1
        target['defocus'] = 0.0
        target['selfguide'] = True
        target['guide'] = False
        target['cycleFilter'] = True
        target['positionAngle'] = 0.0
        target['pmra'] = float(targetlist['pmra'][i])
        target['pmdec'] = float(targetlist['pmdec'][i])
        target['parallax'] = float(targetlist['parallax'][i])
        target['rv'] = float(targetlist['rv'][i])
        target['i2'] = True
        target['vmag'] = float(targetlist['vmag'][i])
        target['comment'] = targetlist['comment'][i]
        
        if name <> None:
            if targetlist['name'][i] == name:
                return target
        elif targetlist['active'][i] ==  '1' or includeInactive:
            targets.append(target)

    if len(targets) == 0: return -1
    return targets
    
def target2json(target):
    
    tmptarget = copy.deepcopy(target)

    tmptarget['starttime'] = datetime.datetime.strftime(target['starttime'],'%Y-%m-%d %H:%M:%S')
    tmptarget['endtime'] = datetime.datetime.strftime(target['endtime'],'%Y-%m-%d %H:%M:%S')
    return json.dumps(tmptarget)    
   
if __name__ == '__main__':

    bstar = False
#    print target2json('HD191408A')
    ipdb.set_trace()


    targetlist = rdlist(bstar=bstar)
    print targetlist['name']
