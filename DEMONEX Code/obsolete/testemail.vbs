Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8

Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("Email.vbs", ForReading)
Execute objFile.ReadAll()

night = "20081016"
datadir = "C:\demonex\data\n" & night & "\"

  strTo = "jdeast@gmail.com"
  strSubject = "DEMONEX Log n" & night
  strBody = "Tonight's (tab delimited) log, the engineering log, and the target file are attached."
  strAttachment1 = datadir & "n" & night & ".log"
  strAttachment2 = datadir & "n" & night & ".eng"
  strAttachment3 = "C:\demonex\targets\n" & night & ".tgt"


  Call Email(strTo,strSubject,strBody,strAttachment1,strAttachment2,strAttachment3)
msgbox("done")