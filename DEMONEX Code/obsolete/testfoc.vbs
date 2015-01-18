'Device/Setup Specific Parameters
stepsPerDegreeC = 200
MaxFocus = 7000
MinFocus = 0
MidTemp = 15


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
msgbox(objCam.focIsConnected)
msgbox(objCam.focPosition)



PosAtMidTemp = (MaxFocus + MinFocus)/2 

currPos = objCam.focPosition

 Temp = 20
'msgbox(objCam.focTemperature)

'Calculate the focus offset
focusOffset = (Temp - MidTemp)*stepsPerDegreeC + PosAtMidTemp - CurrPos

'Move to the desired Focus Position. 
'If it's out of bounds, move to the limit
If FocusOffset < 0 Then
  If (FocusOffset + CurrPos) > 0 Then
    objCam.focMoveIn(-focusOffset)
  Else 
    objCam.focMoveIn(currPos)
  End If
ElseIf FocusOffset > 0 Then
  If (FocusOffset + CurrPos) < MaxFocus Then 
    objCam.focMoveOut(focusOffset)
  Else 
    objCam.focMoveOut(MaxFocus - currPos)
  End If
End If