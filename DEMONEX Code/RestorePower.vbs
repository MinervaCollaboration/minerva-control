'Read the current status (in case of ungraceful exit)
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set statusFile = objFSO.OpenTextFile("status.txt", 1)
status = statusFile.Readline
statusFile.Close

Set objFile = objFSO.OpenTextFile("Email.vbs", 1)
Execute objFile.ReadAll() 

'Send email of power recovery
strTo = "jdeast@astronomy.ohio-state.edu"
strSubject = "DEMONEX rebooted"
strBody = "DEMONEX has rebooted."
Call Email(strTo,strSubject,strBody,"","","")

'restart the observing script if it's in the middle of it
If Status <> "Done" and (hour(now) < 12 or hour(now) > 16) Then
  Set objFile = objFSO.OpenTextFile("DoNight.vbs", 1)
  Execute objFile.ReadAll()
End If