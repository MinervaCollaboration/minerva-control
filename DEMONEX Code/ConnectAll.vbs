Function ConnectAll
On Error Resume Next
'  ViewLog

  'Start TheSky6
  objEngFile.WriteLine("ConnectAll (" & FormatDateTime(Now,3) & "): Starting TheSky6")
  set objTheSky6 = CreateObject("TheSky6.RASSERVERAPP")
  objTheSky6.SetVisible(1)
  Set objTheSky = WScript.CreateObject("TheSky6.RASCOMTheSky")
  objTheSky.Connect()

  'Utils gets killed when TheSky6 closes, re-initialize it
  Set Utils = CreateObject("TheSky6.Utils")

  'Connect to the Telescope
  objEngFile.WriteLine("ConnectAll (" & FormatDateTime(Now,3) & "): Connecting to the Telescope")
  Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
  objTel.Connect()

  objEngFile.WriteLine("ConnectAll (" & FormatDateTime(Now,3) & "): Starting CCDSoft")
  set objCCDSoft = CreateObject("CCDSOFT.RASSERVERAPP")
  objCCDSoft.SetVisible(1)

  'read the previous set temp
  Set CamTempFile = objFSO.OpenTextFile("camtemp.txt", ForReading)
  CamSetPoint = CamTempFile.Readline
  GuiderSetPoint = CamTempFile.Readline
  CamTempFile.Close

  'Connect to the Camera
  Set objCam = WScript.CreateObject("CCDSoft.Camera","MyCamera_")

'  If UseGuider Then
    objEngFile.WriteLine("ConnectAll (" & FormatDateTime(Now,3) & "): Connecting to the guider")
    objCam.Autoguider = 1
    objCam.Connect()

    'These should never change, but in case they do...
    objCam.AutoSavePath = datadir
    objCam.AutoSaveOn = 1'True
    objCam.BinX = 1
    objCam.BinY = 1
    objCam.SubFrame = False
    objCam.TemperatureSetPoint = GuiderSetPoint
    objCam.RegulateTemperature = 1
'  End If

  objEngFile.WriteLine("ConnectAll (" & FormatDateTime(Now,3) & "): Connecting to the camera")  
  objCam.Autoguider = 0
  objCam.Connect()
  objCam.AutoSavePath = datadir
  objCam.AutoSaveOn = 1'True
  objCam.BinX = 1
  objCam.BinY = 1
  objCam.SubFrame = False
  objCam.TemperatureSetPoint = CamSetPoint
  objCam.RegulateTemperature = 1

On Error goto 0

End Function