'This script ensures there are two copies of every raw fits file
'one on a (shared) internal drive and one on an external drive
'Writes names files in danger (1 copy) or gluttonous files (3+ copies) to drive.log

Set WshShell = WScript.CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.fileSystemObject")

Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8

f1 = "C:\demonex\data"
f2 = "D:\demonex\data"
f3 = "E:\demonex\data"
f4 = "F:\demonex\data"
f5 = "H:\demonex\data"
f6 = "I:\demonex\data"

fs = Array(f1,f2,f3,f4,f5,f6)


For Each drive1 in fs

  Dim Folder: Set Folder = objFSO.GetFolder(drive1)
  Dim SubFolders: Set SubFolders = Folder.SubFolders
  Dim Files, strSubFolder, subFolder

  For Each strSubfolder In SubFolders
    Set SubFolder = objFSO.GetFolder(strSubFolder)
    Set Files = SubFolder.Files
    For each File in Files
      Length = Len(file)

      'If it's a fits file...
      If Instr(file, ".fits.fz") = (length - 7) Then
 
        SubFolderName = objFSO.GetFileName(objFSO.GetParentFolderName(File))
      	destFolder = "J:\demonex\data\" & SubFolderName & "\"

      	If objFSO.FileExists(destfolder & objFSO.GetFileName(File)) Then
          ' This is how it should be -- don't do anything
        Else        
	        'Create SubDirectory
          If Not objFSO.FolderExists(destFolder) Then
            Set objFolder = objFSO.CreateFolder(destFolder)
          End If
	        
          objFSO.CopyFile File, destFolder
        End If
      End If
    Next
  Next
Next

MsgBox("Done")