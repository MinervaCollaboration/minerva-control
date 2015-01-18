Dim objTheSky

dJD = 2452066.00 '06/05/2001; ignored if UseCompterClock=1
nDST = 17 'North American Daylight Savings Time Rules
dTZ = 5 'MST
dElev = 0 'unknown, but RCX400 already corrects for elevation; use 0
bUseComputerClock = 1
dLat = 39.9977222 'N 39°59'51.8"
dLong = 83.0435556 'W 83°02'36.8"
szLoc = "Birdhouse"

'Create the TheSky object
Set objTheSky = WScript.CreateObject("TheSky6.RASCOMTheSky")
objTheSky.Connect()
Call objTheSky.SetWhenWhere(dJD,nDST,bUseComputerClock, szLoc, dLong, dLat, dTZ, dElev)
objTheSky.Disconnect()

Set objTheSky = Nothing