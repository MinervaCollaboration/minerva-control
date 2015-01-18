Dim objTheSky

dJD = 2452066.00 '06/05/2001; ignored if UseCompterClock=1
nDST = 0 'No Daylight Savings
dTZ = 7 'MST
dElev = 0 '1515 meters, but RCX400 already corrects for elevation; use 0
bUseComputerClock = 1
dLat = 31.65 'N 31° 39'
dLong = 110.6 'W 110° 36'
szLoc = "Winer"

'Create the TheSky object
Set objTheSky = WScript.CreateObject("TheSky6.RASCOMTheSky")
objTheSky.Connect()
Call objTheSky.SetWhenWhere(dJD,nDST,bUseComputerClock, szLoc, dLong, dLat, dTZ, dElev)
objTheSky.Disconnect()

Set objTheSky = Nothing