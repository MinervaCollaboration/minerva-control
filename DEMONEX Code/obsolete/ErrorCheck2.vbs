'Check for errors; email me with error and engineering log if encountered
Function ErrorCheck
  If Err.number <> 0 Then
    Const cdoSendUsingPickup = 1 'Send message using the local SMTP service pickup directory.
    Const cdoSendUsingPort = 2 'Send the message using the network (SMTP over the network).
    Const cdoAnonymous = 0 'Do not authenticate
    Const cdoBasic = 1 'basic (clear-text) authentication
    Const cdoNTLM = 2 'NTLM

    Set objMessage = CreateObject("CDO.Message")
    objMessage.Subject = "DEMONEX Error n" & night
    objMessage.From = """DEMONEX"" <demonex3041@gmail.com>"
    objMessage.To = "jdeast@astronomy.ohio-state.edu"
    objMessage.TextBody = "The following error was encountered:" & VBCrLf &_
      Err.Description & VBCrLf & apgSeverityError & VBCrLf & Err.Number

    '==This section provides the configuration information for the remote SMTP server.
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/sendusing") = 2
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/smtpserver") = "smtp.gmail.com"
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/smtpauthenticate") = cdoBasic
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/sendusername") = "demonex3041"
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/sendpassword") = "TheDEMON666"
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/smtpserverport") = 25
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/smtpusessl") = True
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/smtpconnectiontimeout") = 60
    objMessage.Configuration.Fields.Update
    '==End remote SMTP server configuration section==

    'If exists, attach the engineering file
    attachment = path & "n" & night & ".eng"
    Set objFSO = CreateObject("Scripting.FileSystemObject")
    If objFSO.FileExists(attachment) Then
      objMessage.AddAttachment attachment
    End If
    
    don't actually email me during testing... don't want to spam myself...
    'MsgBox(Err.Description & VBCrLf & apgSeverityError & VBCrLf & Err.Number)
    'objMessage.Send
    WScript.Quit
  End If
End Function
