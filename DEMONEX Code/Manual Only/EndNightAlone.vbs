'Make a backup of the night's data onto the external drive
Set objFSO = CreateObject("Scripting.fileSystemObject")
sourcedrive = "E"
destinationdrive = "I"
night = "20110107"

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

    Set objFolder = objFSO.GetFolder(Source)

    folderSize = objFolder.Size/1024/1024 'MB
    tstart = now
    Msgbox("EndNight (" & FormatDateTime(Now,3) & "): Copying data from " & source & " to " & destination &_
           " (" & objFolder.Files.Count & " files, " & Round(FolderSize) & " MB)")
    objFSO.CopyFolder source, destination
    CopyTime = (now - tstart)*86400
    MsgBox("EndNight (" & FormatDateTime(Now,3) & "): Done copying data in " & Round(CopyTime) & " seconds (" & Round(FolderSize/CopyTime,2) & " MB/s)")

  Else
    MsgBox("EndNight (" & FormatDateTime(Now,3) & "): Source folder doesn't exist; cannot copy data")
  End If
