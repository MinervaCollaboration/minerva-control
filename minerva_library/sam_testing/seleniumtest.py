import selenium
import time
print selenium.__file__
from selenium import webdriver
import ipdb
from bs4 import BeautifulSoup

#ipdb.set_trace()

dr = selenium.webdriver.Chrome('C:\Users\Kiwispec\Desktop\chromedriver.exe')

dr.get('http://snmp:1234@192.168.10.91/outlet.htm')
time.sleep(2)
ipdb.set_trace()
html = dr.page_source
parsed = BeautifulSoup(html)

print parsed.find(id='A13')
while True:
    s= raw_input()

