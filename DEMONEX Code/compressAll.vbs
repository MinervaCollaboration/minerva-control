Set WshShell = WScript.CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.fileSystemObject")

f1 = "C:\demonex\data"
f2 = "D:\demonex\data"
f3 = "E:\demonex\data"
f4 = "F:\demonex\data"
f5 = "H:\demonex\data"
f6 = "I:\demonex\data"
f7 = "J:\demonex\data"

fs = Array(f1,f2,f3,f4,f5,f6,f7)


For Each drive in fs

  Dim Folder: Set Folder = objFSO.GetFolder(drive)
  Dim SubFolders: Set SubFolders = Folder.SubFolders
  Dim Files, strSubFolder, subFolder

  For Each strSubfolder In SubFolders
    Set SubFolder = objFSO.GetFolder(strSubFolder)
    Set Files = SubFolder.Files
    For each File in Files
      Length = Len(file)
      If InStr(file,".fits") = (length - 4) Then
         WshShell.Run "fpack -D " & file,7,1
      End If
    Next
  Next
Next





