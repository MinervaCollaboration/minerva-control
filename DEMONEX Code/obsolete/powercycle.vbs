Sub PowerCycle

  Set ObjWS = WScript.CreateObject("WScript.Shell")
  ObjWS.Run "powercycle.bat"
  WScript.Sleep 30000

End Sub