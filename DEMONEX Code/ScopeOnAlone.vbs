  'Must have GPS disabled; assumes ungraceful (not parked) shutdown.

  Set objFSO = CreateObject("Scripting.fileSystemObject")
  Set objFile = objFSO.OpenTextFile("PowerControl.vbs", 1)
  Execute objFile.ReadAll()

  Call PowerControl("Mount",True)

  WScript.Sleep 30000

  Set ObjWS = WScript.CreateObject("WScript.Shell")
  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"
  WScript.Sleep 30000

  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "cmd /c C:\demonex\scripts\LX200Cancel.bat"

msgbox("Done")