Sub ErrorCheck
  If Err.number <> 0 Then
    'If exists, attach the engineering file

    strTo = "jdeast@astronomy.ohio-state.edu"
    strSubject = "DEMONEX Error n" & night
    strBody = "The following error was encountered:" & VBCrLf &_
      Err.Description & VBCrLf & apgSeverityError & VBCrLf & Err.Number
    strAttachment = datapath & "n" & night & ".eng"

    'don't actually email me during testing... don't want to spam myself...
    'MsgBox(Err.Description & VBCrLf & apgSeverityError & VBCrLf & Err.Number)
    Email
    
    WScript.Quit
  End If
End Sub