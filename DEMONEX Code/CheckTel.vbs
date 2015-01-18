Sub CheckTel
On Error Resume Next
  If Not CBool(objTel.IsConnected) Then
    TStart = Now

    'First try reconnecting the telescope
    objEngFile.WriteLine("CheckTel (" & FormatDateTime(Now,3) & "): Telescope not connected, trying simple reconnect")
    objTel.Connect()         

    'If still not connected, restart software
    If Not CBool(objTel.IsConnected) Then

      objEngFile.WriteLine("CheckTel (" & FormatDateTime(Now,3) & "): Simple reconnect failed; restarting software")

      Disconnectall
      ConnectAll
  
      'If still not connected, power cycle the mount; motor stall?
      If Not CBool(objTel.IsConnected) Then
        objEngFile.WriteLine("CheckTel (" & FormatDateTime(Now,3) & "): Restarting software failed; power cycling mount")

        DisconnectAll
        ScopeOff
        WScript.Sleep 30000
        ScopeOn
        ConnectAll

        'If still not connected, give up and email error
        If Not CBool(objTel.IsConnected) Then 
          objEngFile.WriteLine("CheckTel (" & FormatDateTime(Now,3) & "): Power cycling mount failed; cannot connect to telescope")

          'Email error about failed connection    
          strTo = StudentEmail & "," & EmergencyTxt
          strSubject = "DEMONEX Error"
          strBody = "Could not connect to the telescope"
          strAttachment = logdir & "n" & night & ".eng"
          objEngFile.Close

          'Email log
          Call Email(strTo,strSubject,strBody,strAttachment,"","")
          WScript.Quit(0)
        Else
          'Realign the Telescope
'          objEngFile.WriteLine("CheckTel (" & FormatDateTime(Now,3) & "): Realigning the telescope")

          NotAligned = True 'realigne the scope
	  AcquireObject = True 'reacquire object

          objEngFile.WriteLine("CheckTel (" & FormatDateTime(Now,3) & "): Power cycling and mount realignment successful in " & (Now - TStart)*86400 & " seconds")

          'Email warning about successful power cycle        
          strTo = StudentEmail
          strSubject = "DEMONEX Warning"
          strBody = "Power Cycle Necessary"

          Call Email(strTo,strSubject,strBody,strAttachment)

         End If
      Else
        objEngFile.WriteLine("CheckTel (" & FormatDateTime(Now,3) & "): Restarting software successful in " & (Now - TStart)*86400 & " seconds")    
      End If
    Else
      objEngFile.WriteLine("CheckTel (" & FormatDateTime(Now,3) & "): Simple reconnect successful in " & (Now - TStart)*86400 & " seconds")  
    End If    
  End If

On Error Goto 0
End Sub