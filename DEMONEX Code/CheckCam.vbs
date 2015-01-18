Sub CheckCam

  On Error Resume Next

  objCam.Connect
  If Err.Number <> 0 Then 
    TStart = Now

    'First try reconnecting the camera
    objEngFile.WriteLine("CheckCam (" & FormatDateTime(Now,3) & "): Camera connection error: " & Err.Description & "; restarting software")
    Err.Clear

    Disconnectall
    ConnectAll

    objCam.Connect
    If Err.Number <> 0 Then 
      Err.Clear
      objEngFile.WriteLine("CheckCam (" & FormatDateTime(Now,3) & "): Restarting software failed; attempting power cycle")
      Call PowerControl("Camera",False)
      Call PowerControl("Guider",False)
      WScript.Sleep 5000
      Call PowerControl("Camera",True)
      Call PowerControl("Guider",True)
      WScript.Sleep 5000
  
      Disconnectall
      ConnectAll
      
      If Err.Number <> 0 Then

        objEngFile.WriteLine("CheckCam (" & FormatDateTime(Now,3) & "): Restarting software failed; cannot connect to camera")

        'Email error about failed connection    
        strTo = StudentEmail & "," & EmergencyTxt
        strSubject = "DEMONEX Error"
        strBody = "Could not connect to the camera"
        strAttachment = logdir & "n" & night & ".eng"

        Call Email(strTo,strSubject,strBody,strAttachment,"","")
        WScript.Quit(0)
      Else
        objEngFile.WriteLine("CheckCam (" & FormatDateTime(Now,3) & "): Powercycling cameras successful in " & (Now - TStart)*86400 & " seconds")    
      End If
    Else
      objEngFile.WriteLine("CheckCam (" & FormatDateTime(Now,3) & "): Restarting software successful in " & (Now - TStart)*86400 & " seconds")    
    End If
  End If
End Sub