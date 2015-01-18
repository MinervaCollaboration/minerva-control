Const ForReading = 1
Const ForAppending = 8
'Set objCam = CreateObject("CCDSoft.Camera")
dim objCam, objTel

'Include functions
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("ConnectAll.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DoSkyFlat.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("PrepNight.vbs", ForReading)
Execute objFile.ReadAll()



night = "20080204"
path = "C:\demonex\data\n" & night & "\"

PrepNight(night)

'Open log and engineering files
strLogFile = path & "n" & night & ".log"
strEngFile = path & "n" & night & ".eng"
Set objLogFile = objFSO.OpenTextFile(strLogFile, ForAppending)
Set objEngFile = objFSO.OpenTextFile(strEngFile, ForAppending)

ConnectAll

arrFilters = Array(3)
NImages = 1
Call DoSkyFlat(arrFilters, NImages)
