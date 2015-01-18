Const ForReading = 1
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("TalkToLX200.vbs", ForReading)
Execute objFile.ReadAll()

Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
objTel.Connect()

'Reset The Scope
Call TalkToLX200(":ES6004#:EK13#",Tx,0,1)

'Wait for Reset
WScript.Sleep 30000

'Choose Max Mount
Call TalkTOLX200(":EK10#",Tx,0,1)

'Type 4064<return> For Focal Length
Call TalkToLX200(":EK 52#:EK 48#:EK 54#:EK 52#:EK13#",Tx,0,1)

'Press Mode to Cancel Alignment
Call TalkToLX200(":EK9#",Rx,0,1)
  
'Wait for Telescope to Find Home/More initialization
WScript.Sleep 60000

'Cancel Back to Main Menu
Call TalkToLX200(":EK9#:EK9#:EK9#:EK9#:EK9#",Rx,0,1)

