Sub Email(strTo,strSubject,strBody,strAttachment)   

'  On Error Resume Next

  Set objMessage = CreateObject("CDO.Message")
  objMessage.Subject = strSubject
  objMessage.From = """DEMONEX"" <demonex@winer.org>"
  objMessage.To = strTo
  objMessage.TextBody = strBody

  Set objFSO = CreateObject("Scripting.FileSystemObject")

  If objFSO.FileExists(strAttachment) Then
    objMessage.AddAttachment strAttachment
msgbox(strAttachment)
  End If

  objEngFile.WriteLine("Email (" & FormatDateTime(Now,3) & "): Sending Email") 
  objMessage.Send

'  On Error Goto 0

End Sub