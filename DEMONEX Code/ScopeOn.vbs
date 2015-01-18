Sub ScopeOn

  'Must have GPS disabled; assumes ungraceful (not parked) shutdown.

  objEngFile.WriteLine("ScopeOn (" & FormatDateTime(Now,3) & "): Turning on the Scope")
  Call PowerControl("Mount",True)

  objEngFile.WriteLine("ScopeOn (" & FormatDateTime(Now,3) & "): Waiting for scope to turn on")  
  WScript.Sleep 30000


  objEngFile.WriteLine("ScopeOn (" & FormatDateTime(Now,3) & "): Waiting for scope to home")
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 30000

  objEngFile.WriteLine("ScopeOn (" & FormatDateTime(Now,3) & "): Cancel to main menu")
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 1000

'just in case...
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 1000
  ObjWS.Run "LX200Cancel.bat"
  WScript.Sleep 1000

  ConnectAll

  objEngFile.WriteLine("ScopeOn (" & FormatDateTime(Now,3) & "): Aligning on home")
  HomeScope

End Sub