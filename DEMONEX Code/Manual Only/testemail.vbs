Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8

Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("../Email.vbs", ForReading)
Execute objFile.ReadAll()

night = "20090114"
datadir = "C:\demonex\data\n" & night & "\"
logdir = "C:\demonex\logs\"

  strTo = "jdeast@astronomy.ohio-state.edu"
  strSubject = "DEMONEX Test"
  strBody = "This is a test of the email."
  strAttachment1 = ""'logdir & "n" & night & ".log"
  strAttachment2 = ""'logdir & "n" & night & ".eng"
  strAttachment3 = ""'"C:\demonex\targets\n" & night & ".tgt"


  Call Email(strTo,strSubject,strBody,strAttachment1,strAttachment2,strAttachment3)
msgbox("done")