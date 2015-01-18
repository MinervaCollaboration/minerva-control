'Function ConnectAll

  Const ForReading = 1
'  On Error Resume Next

  'Connect to TheSky


msgbox("ConnectAll (" & FormatDateTime(Now,3) & "): Starting TheSky6")
  set objTheSky6 = CreateObject("TheSky6.RASSERVERAPP")
  objTheSky6.SetVisible(1)

msgbox("ConnectAll (" & FormatDateTime(Now,3) & "): Connecting to TheSky6")
  Set objTheSky = WScript.CreateObject("TheSky6.RASCOMTheSky")
  objTheSky.Connect()

msgbox("ConnectAll (" & FormatDateTime(Now,3) & "): Connecting to the telescope")
  Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
  objTel.Connect()


  'Connect to CCDSoft
msgbox("ConnectAll (" & FormatDateTime(Now,3) & "): Starting CCDSoft")
   set objCCDSoft = CreateObject("CCDSOFT.RASSERVERAPP")
   objCCDSoft.SetVisible(1)

  'Connect to the Camera
  Set objCam = WScript.CreateObject("CCDSoft.Camera","MyCamera_")
msgbox("ConnectAll (" & FormatDateTime(Now,3) & "): Connecting to the Autoguider")
  objCam.Autoguider = 1
  objCam.Connect()

'  'read the previous set temp
'  Set objFSO = CreateObject("Scripting.fileSystemObject")
'  Set CamTempFile = objFSO.OpenTextFile("camtemp.txt", ForReading)
'  CamSetPoint = CamTempFile.Readline
'  GuiderSetPoint = CamTempFile.Readline
'  CamTempFile.Close

  'These should never change, but in case they do...
  objCam.AutoSavePath = datadir
  objCam.AutoSaveOn = True
  objCam.BinX = 1
  objCam.BinY = 1
  objCam.SubFrame = False
'  objCam.TemperatureSetPoint = GuiderSetPoint
'  objCam.RegulateTemperature = 1

msgbox("ConnectAll (" & FormatDateTime(Now,3) & "): Connecting to the camera")  
  objCam.Autoguider = 0
  objCam.Connect()
  objCam.AutoSavePath = datadir
  objCam.AutoSaveOn = True
  objCam.BinX = 1
  objCam.BinY = 1
  objCam.SubFrame = False
'  objCam.TemperatureSetPoint = CamSetPoint
'  objCam.RegulateTemperature = 1

'  'Connect to the Focuser
'msgbox("ConnectAll (" & FormatDateTime(Now,3) & "): Connecting to the focuser")
'  objCam.focConnect

'  'Disconnect from the Focuser
'msgbox("DisconnectAll (" & FormatDateTime(Now,3) & "): Disconnecting from the focuser")
'  objCam.focDisconnect

  'Disconnect to the Camera
msgbox("DisconnectAll (" & FormatDateTime(Now,3) & "): Disconnecting from the camera")
  objCam.Disconnect()
msgbox("DisconnectAll (" & FormatDateTime(Now,3) & "): Disconnecting from the guider")
  objCam.AutoGuider = 1
  objCam.Disconnect()

msgbox("DisconnectAll (" & FormatDateTime(Now,3) & "): Closing CCDSoft")
  objCCDSoft.Quit(1)

  'Disconnect from the Telescope
msgbox("DisconnectAll (" & FormatDateTime(Now,3) & "): Disconnecting from the telescope")
  objTel.Disconnect
msgbox("DisconnectAll (" & FormatDateTime(Now,3) & "): Disconnecting from The Telescope")
  objTheSky.DisconnectTelescope
msgbox("DisconnectAll (" & FormatDateTime(Now,3) & "): Disconnecting from TheSky6")
  objTheSky.Disconnect
msgbox("DisconnectAll (" & FormatDateTime(Now,3) & "): Closing TheSky6")
  objTheSky6.Quit(1)


'msgbox("EVERYTHING ABOUT TO BE KILLED")
'  WScript.Sleep 1000
'  'Kill all remaining processes
'  strComputer = "."
'  Set objWMIService = GetObject("winmgmts:" _
'      & "{impersonationLevel=impersonate}!\\" & strComputer & "\root\cimv2")
'  Set colProcessList = objWMIService.ExecQuery _
'      ("SELECT * FROM Win32_Process WHERE Name = 'CCDSoft.exe' or Name = 'TP.exe' or Name = 'TheSky6.exe' or Name = 'Orch.exe' or Name = 'my_imstat.exe'")
'  For Each objProcess in colProcessList
'      objProcess.Terminate()
'  Next
'  WScript.Sleep 1000


'End Function