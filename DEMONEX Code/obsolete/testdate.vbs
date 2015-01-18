Set Utils = CreateObject("TheSky6.Utils")
'angle = 15.5373876571156
'DMS = Utils.ConvertAngleToDMS(Angle)
'msgbox(DMS(0) & ":" & DMS(1) & ":" & DMS(2))

'test = utils.ConvertStringToRA("+83ß03:09")
'msgbox(test)

Const ForReading = 1
Const ForAppending = 8

'SExtractor inventory constants:
Const cdInventoryX=0
Const cdInventoryY=1
Const cdInventoryMagnitude=2
Const cdInventoryClass=3
Const cdInventoryFWHM=4
Const cdInventoryMajorAxis=5
Const cdInventoryMinorAxis=6
Const cdInventoryTheta=7
Const cdInventoryEllipticity=8


'On Error Resume Next

dim objCam, objTel, objTheSky

'Camera Event variables
dim AcquireObject, Calibrate, MeridianFlip, strFileName, adNow, autoguider

BadGuideCounter = 0

'Include functions
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("CheckCam.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("CheckTel.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ConnectAll.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DisconnectAll.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DoBias.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DoDark.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DoObject.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DoSkyFlat.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("Email.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("EndNight.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("FindGuideStar.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("Focus.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("GetIndex.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("GetWeather.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("imstat.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("jd.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("LX200Cancel.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("PointAndSync.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("PowerCycle.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("PrepNight.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("RebootScope.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("RoofOpen.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ScopeOff.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ScopeOn.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("SunAlt.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("SyncTime.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("TalkToLX200.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("WriteLog.vbs", ForReading)
Execute objFile.ReadAll()

  'Connect to the Telescope
  Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
  objTel.Connect()

  Randomize
  Az = 270 'Rnd*360
  Alt = 60 'Rnd*50 + 30

  RADec = Utils.ConvertAzAltToRADec(Az, Alt)
msgbox(radec(0) & " " & radec(1))