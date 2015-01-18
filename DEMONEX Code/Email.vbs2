Sub Email(strTo,strSubject,strBody,strAttachment1, strAttachment2, strAttachment3)   

  Set objMessage = CreateObject("CDO.Message")

  objMessage.Subject = strSubject
  objMessage.From = """DEMONEX"" <demonex@winer.org>"
  objMessage.To = strTo
  objMessage.TextBody = strBody

  Set objFSO = CreateObject("Scripting.FileSystemObject")
  If objFSO.FileExists(strAttachment1) Then
    objMessage.AddAttachment strAttachment1
  End If

  If objFSO.FileExists(strAttachment2) Then
    objMessage.AddAttachment strAttachment2
  End If

  If objFSO.FileExists(strAttachment3) Then
    objMessage.AddAttachment strAttachment3
  End If
 
  objMessage.Send

End Sub