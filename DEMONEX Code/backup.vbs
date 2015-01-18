'This script ensures there are two copies of every raw fits file
'one on a (shared) internal drive and one on an external drive
'Writes names files in danger (1 copy) or gluttonous files (3+ copies) to drive.log

Set WshShell = WScript.CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.fileSystemObject")

Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8

strLogFile = "drivebak.txt"
Set objLogFile = objFSO.OpenTextFile(strLogFile, ForWriting)

f1 = "C:\demonex\data"
f2 = "D:\demonex\data"
f3 = "E:\demonex\data"
f4 = "F:\demonex\data"
f5 = "H:\demonex\data"
f6 = "I:\demonex\data"
f7 = "J:\demonex\data"

fs = Array(f1,f2,f3,f4,f5,f6,f7)


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
        NFiles = 0

        For Each drive2 In fs
          If objFSO.FileExists(drive2 & "\" & SubFolderName & "\" & objFSO.GetFileName(File)) Then
            NFiles = NFiles+1
          End If
        Next
        
        If NFiles = 2 Then
          ' This is how it should be -- don't do anything
          'MsgBox("good!")
        ElseIf NFiles = 1 Then
	        objLogFile.WriteLine("WARNING: " & file & " only has one copy")
	        
	        destfolder = "E:\demonex\data\" & SubFolderName & "\"
	               
	        If objFSO.GetParentFolderName(File) & "\" = destfolder Then
            destfolder = "I:\demonex\data\" & SubFolderName & "\"
          End If 
  	      
	        'Create SubDirectory
          If Not objFSO.FolderExists(destFolder) Then
            Set objFolder = objFSO.CreateFolder(destFolder)
          End If
  	      
  	      objFSO.CopyFile File, destFolder
'   	      MsgBox("check for " & file & " in " & destfolder)
          
	      ElseIf NFiles > 2 Then
          objLogFile.WriteLine("WARNING: " & file & " has too many copies")
        Else
          objLogFile.WriteLine("WARNING: " & file & " has " & NFiles & " copies. (VBScript shouldn't get here...)")
	      End If

'        msgbox("done checking " & file & "; it had " & Nfiles & " matches")

      End If
    Next
  Next
Next

objLogFile.Close