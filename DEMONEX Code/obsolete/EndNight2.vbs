'Make a backup of the night's data onto the external drive

night = WScript.Arguments(0)

Dim objFSO, objFolder, objShell, strDirectory
Set objFSO = CreateObject("Scripting.FileSystemObject")

Source = "C:\demonex\data\n" & night
strDriveLetter = "D"

strRoot = strDriveLetter & ":\demonex"
strSubDir = "\data\"

Destination = strRoot & strSubDir
'Create Root Directory
If objFSO.FolderExists(strRoot) Then
   Set objFolder = objFSO.GetFolder(strRoot)
Else
   Set objFolder = objFSO.CreateFolder(strRoot)
End If


'Create SubDirectory
If objFSO.FolderExists(strRoot & strSubDir) Then
   Set objFolder = objFSO.GetFolder(strRoot & Subdir)
Else
   Set objFolder = objFSO.CreateFolder(strRoot & Subdir)
End If

If objFSO.FolderExists(Source) Then
   objFSO.CopyFolder source, destination
End If

WScript.Quit(0)