Set WshShell = WScript.CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.fileSystemObject")

'the range of dates to copy
startdate = "20080101"
stopdate = "20090101"

'The Destination Drive letter
Destination = "H"

'The Source Drives
Source = Array("C","D","E","F","I","J","K")

For Each drive in source

  'Find all Source data folders for each night in each drive 
  strFolder = drive & ":\demonex\data"
  Dim Folder: Set Folder = objFSO.GetFolder(strFolder)
  Dim SubFolders: Set SubFolders = Folder.SubFolders
  Dim Files, strSubFolder, subFolder

  For Each strSubfolder In SubFolders
  
    strdate = Split(StrSubFolder,"n")
  
    If strDate(0) >= startdate And strDate(0) <= stopdate Then
  
      Set SubFolder = objFSO.GetFolder(strSubFolder)
      Set Files = SubFolder.Files
    
      'For every file that exists in the source (sub)folder...
      For each StrSourceFile in Files
    
        'See if the corresponding file exists on the destination drive
        parts = Split(StrSourceFile,":")
        StrDestFile = Destination & ":" & Parts(UBound(parts))
        Set objSource = objFSO.GetFile(StrSourceFile)

        'If the file exists, makes sure it's the same size      
        If objFSO.FileExists(StrDestFile) Then
          Set objDest = objFSO.GetFile(StrDestFile)       
          If objSource.Size <> objDest.Size Then
            'If not the same size, overwrite it with the correct one
            objFSO.CopyFile StrSourceFile, StrDestFile, True
          End If
        Else
          'If the file doesn't exist on the destination drive...
        
          'Create the data folder (for the night), if it doesn't already exist
          DestFolder = objFSO.GetParentFolderName(StrDestFile)
          If Not objFSO.FolderExists(DestFolder) Then
            Set objFolder = objFSO.CreateFolder(DestFolder)
          End If
        
          'Copy the file to the destination drive
          objFSO.CopyFile StrSourceFile, StrDestFile
        
        End If
      Next
    End If
  Next
Next




