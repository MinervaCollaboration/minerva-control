'Make a backup of the night's data onto the external drive
Sub EndNight(SourceDrive,DestinationDrive)

  Source = SourceDrive & ":\demonex\data\n" & night
  Destination = DestinationDrive & ":\demonex\data\"

  strRoot = DestinationDrive & ":\demonex"
  strSubDir = "\data\"

  'Create Root Directory
  If objFSO.FolderExists(strRoot) Then
    Set objFolder = objFSO.GetFolder(strRoot)
  Else
    Set objFolder = objFSO.CreateFolder(strRoot)
  End If

  'Create SubDirectory
  If objFSO.FolderExists(strRoot & strSubDir) Then
    Set objFolder = objFSO.GetFolder(strRoot & strSubdir)
  Else
    Set objFolder = objFSO.CreateFolder(strRoot & strSubdir)
  End If

  If objFSO.FolderExists(Source) Then

    objEngFile.WriteLine("EndNight (" & FormatDateTime(Now,3) & "): Deleting Autoguider images")
    On Error Resume Next
    objFSO.DeleteFile(source & "\AutoGuider.*.*")
'    objFSO.DeleteFile(source & "\TmpPrefix.*")
    Err.Clear
    On Error Goto 0

    Set objFolder = objFSO.GetFolder(Source)

    Set WshShell = WScript.CreateObject("WScript.Shell")
    'Compress raw fits files (with fpack)
    Set Files = objFolder.Files
    For each File in Files
      Length = Len(file)
      If InStr(file,".fits") = (length - 4) Then
         WshShell.Run "fpack -D " & file,7,1
      End If
    Next

    FolderSize = objFolder.Size/1024/1024 'MB
    tstart = now

    objEngFile.WriteLine("EndNight (" & FormatDateTime(Now,3) & "): Copying data from " &_
                         source & " to " & destination & " (" & objFolder.Files.Count &_
                         " files, " & Round(FolderSize) & " MB)")
    objFSO.CopyFolder source, destination
    CopyTime = (now - tstart)*86400
    objEngFile.WriteLine("EndNight (" & FormatDateTime(Now,3) & "): Done copying data in " &_
                         Round(CopyTime) & " seconds (" & Round(FolderSize/CopyTime,2) & " MB/s)")

  Else
    objEngFile.WriteLine("EndNight (" & FormatDateTime(Now,3) & "): Source folder doesn't exist; cannot copy data")
  End If

End Sub