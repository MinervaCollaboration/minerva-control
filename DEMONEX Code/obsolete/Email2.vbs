night = WScript.Arguments(0)

Const cdoSendUsingPickup = 1 'Send message using the local SMTP service pickup directory.
Const cdoSendUsingPort = 2 'Send the message using the network (SMTP over the network).
Const cdoAnonymous = 0 'Do not authenticate
Const cdoBasic = 1 'basic (clear-text) authentication
Const cdoNTLM = 2 'NTLM

Set objMessage = CreateObject("CDO.Message")
objMessage.Subject = "DEMONEX Log n" & night
objMessage.From = """DEMONEX"" <demonex3041@gmail.com>"
objMessage.To = "jdeast@astronomy.ohio-state.edu"
objMessage.TextBody = "Tonight's log is attached."

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

attachment = "C:\demonex\data\n" & night & "\n" & night & ".log"

objMessage.AddAttachment attachment
objMessage.Send
