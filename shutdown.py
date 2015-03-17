import main

site, aqawan, telescope, imager = main.prepNight()
imager.connect()
main.endNight(site, aqawan, telescope, imager)
