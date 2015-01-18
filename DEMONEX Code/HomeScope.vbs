Sub HomeScope

 
  objEngFile.WriteLine("HomeScope (" & FormatDateTime(Now,3) & "): Checking the telescope time")
  CheckTime
  CheckPos

  'Align on Home
  objEngFile.WriteLine("HomeScope (" & FormatDateTime(Now,3) & "): Homing Scope")
  CheckTel
  Call TalkToDevice(":hF#", Rx, 0, 5)
  WScript.Sleep 1000

  Call TalkToDevice(":h?#", Rx, 1, 5)
  WScript.Sleep 1000
  HomeStart = Now

  objEngFile.WriteLine("HomeScope (" & FormatDateTime(Now,3) & "): Homing Status = " & Rx)

  Do While Rx <> "1"
    Call TalkToDevice(":h?#", Rx, 1, 5)
    WScript.Sleep 1000

    objEngFile.WriteLine("HomeScope (" & FormatDateTime(Now,3) & "): Homing Status = " & Rx)

    If Rx = "0" or (Now - Homestart) > 180.0/86400.0 Then

      If nHomeFail > 3 Then

        objEngFile.WriteLine("HomeScope (" & FormatDateTime(Now,3) & "): Error: Homing Failed! Entering safe mode to prevent cable wrapping")

        DisconnectAll
        Status = PowerControl("Mount",False)
        objEngFile.WriteLine("HomeScope (" & FormatDateTime(Now,3) & "): Mount off status: " & status)
        Status = PowerControl("Camera",False)
        objEngFile.WriteLine("HomeScope (" & FormatDateTime(Now,3) & "): Camera off status: " & status)
        Status = PowerControl("Guider",False)
        objEngFile.WriteLine("HomeScope (" & FormatDateTime(Now,3) & "): Guider off status: " & status)

        'Email error about failed home
        strTo = StudentEmail & "," & EmergencyTxt
        strSubject = "DEMONEX Homing Error"
        strBody = "Could not home the telescope; attempting to prevent cable wrapping. Entering safe mode -- Must rename DoNight.vbs.ERROR to DoNight.vsb to resume operation."
        strAttachment = logdir & "n" & night & ".eng"
        objEngFile.Close

        'Prevents it from running the next night
        objFSO.MoveFile "DoNight.vbs" , "DoNight.vbs.ERROR"

        'Email log
        Call Email(strTo,strSubject,strBody,strAttachment,"","")
        WScript.Quit(0)
      Else
        objEngFile.WriteLine("HomeScope (" & FormatDateTime(Now,3) & "): Error: Homing Failed " & nHomeFail & " time(s) -- power cycling mount")       
        DisconnectAll
        ScopeOff
        WScript.Sleep 30000
        ScopeOn
        nHomeFail = nHomeFail + 1
        Exit Sub
      End If
    End If

  Loop

CheckPos
nHomeFail = 0

End Sub