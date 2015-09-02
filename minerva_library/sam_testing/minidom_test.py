import urllib2
import ipdb
from xml.dom import minidom

ipdb.set_trace()

url_str = 'http://192.168.10.91/outlet.htm'
usr = 'snmp'
pss = '1234'
p = urllib2.HTTPPasswordMgrWithDefaultRealm()
p.add_password(None, url_str, usr, pss)

handler = urllib2.HTTPBasicAuthHandler(p)
opener = urllib2.build_opener(handler)
urllib2.install_opener(opener)

page = urllib2.urlopen(url_str).read()

xml_doc = minidom.parseString(page)
"""
can also use
req = requests.get(url,auth=(user,pass))
print req.content
for page stuff. Read on a forum that there is no way to have requests.get run JavaScript
stuff before grapping. Could look into scraping, but going to check snmp first.
Scrapping with authentication needed will probably be a pain.
"""

