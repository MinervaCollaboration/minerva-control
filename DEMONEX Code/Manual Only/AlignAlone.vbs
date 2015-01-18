Const ForReading = 1
Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
objTel.Connect()

'Include functions
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("../TalkToLX200.vbs", ForReading)
Execute objFile.ReadAll()

Call TalkToLX200(":hF#", Rx, 0, 0) 

msgbox("done")