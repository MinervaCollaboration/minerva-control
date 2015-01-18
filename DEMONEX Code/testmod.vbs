Set objFSO = CreateObject("Scripting.fileSystemObject")
If not objFSO.FileExists("C:\demonex\share\solve.txt") Then
  msgbox("file doesn't exist")
else 
  msgbox("file exists!")        
End If