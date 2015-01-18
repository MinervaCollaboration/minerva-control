'Sub ViewLog

  'If started between midnight and noon, use the yesterday's date
  If Hour(Now) < 12 Then
    night = Right(string(4,"0") & Year(Now-1), 4) &_
    Right(string(2,"0") & Month(Now-1), 2) &_
    Right(string(2,"0") & Day(Now-1), 2)
  Else 
    night = Right(string(4,"0") & Year(Now), 4) &_
      Right(string(2,"0") & Month(Now), 2) &_
      Right(string(2,"0") & Day(Now), 2)
  End If

  Set ObjWS = WScript.CreateObject("WScript.Shell")
  objWS.Run "tail -f C:\demonex\logs\n" & night & ".eng", 4, False

'End Sub