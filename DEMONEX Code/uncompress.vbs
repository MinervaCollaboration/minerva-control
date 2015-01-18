Set WshShell = WScript.CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.fileSystemObject")

f1 = "E:\demonex\data\n20100412\"

Dim Folder: Set Folder = objFSO.GetFolder(f1)

Set Files = Folder.Files
For each File in Files
  Length = Len(file)

  If InStr(file,".fits.fz") = (length - 7) Then
     WshShell.Run "funpack " & file,7,1
  End If
Next






