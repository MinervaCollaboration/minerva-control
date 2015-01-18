Sub ViewLog

  Set ObjWS = WScript.CreateObject("WScript.Shell")
  objWS.Run "tail -f C:\demonex\logs\n" & night & ".eng", 4, False

End Sub