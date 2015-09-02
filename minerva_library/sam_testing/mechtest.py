import ipdb
import mechanize
ipdb.set_trace()

usr = 'snmp'
pss = '1234'
url = 'http://192.168.10.91/outlet.htm'

br = mechanize.Browser()

br.set_handle_robots(False)
br.add_password(url,usr,pss)
resp = br.open(url)
text = resp.read()
print text
