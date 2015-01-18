'Connect to TheSky
Set objTheSky = WScript.CreateObject("TheSky6.RASCOMTheSky")
objTheSky.Connect()

'Connect to the Telescope
Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
objTel.Connect()

'Connect to the Camera
Set objCam = CreateObject("CCDSoft.Camera")
objCam.Connect()

'Connect to the Focuser
objCam.focConnect

call focus.vbs 30