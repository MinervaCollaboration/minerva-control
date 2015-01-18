Set objFSO = CreateObject("Scripting.fileSystemObject")
SolveName = "C:\demonex\share\solve.txt"
If objFSO.FileExists(solvename) Then
  set file = objFSO.getFile(SolveName)
  If File.size > 0 Then 
    Msgbox("Exists!")
  Else
    Msgbox("Empty!")
  End If
Else 
  Msgbox("Does not exist")
End If