Sub PrepNight(night)

Dim objFSO, objFolder, objShell, strDirectory

strLogFile = CStr(logdir & "\n" & night & ".log")
strEngFile = CStr(logdir & "\n" & night & ".eng")
Set objFSO = CreateObject("Scripting.FileSystemObject")

'Create the data folder
If objFSO.FolderExists(datadir) Then
   Set objFolder = objFSO.GetFolder(datadir)
Else
   Set objFolder = objFSO.CreateFolder(datadir)
End If

'Create the log folder
If objFSO.FolderExists(logdir) Then
   Set objFolder = objFSO.GetFolder(logdir)
Else
   Set objFolder = objFSO.CreateFolder(logdir)
End If

'Create the Log File (don't overwrite)
If objFSO.FileExists(strLogFile) Then
   Set objFolder = objFSO.GetFolder(logdir)
Else
   Set objFile = objFSO.CreateTextFile(strLogFile)
   'write the header
   objFile.WriteLine("Filename" & VBTab &  "Object" & VBTab &_
     "Local Time" & VBTab & "ExpTime" & VBTab & "Airmass" & VBTab &_
     "Filter" & VBTab & "Meridian Flip" & VBTab & "T_Outside (C)" & VBTab &_
     "T_Camera (C)" & VBTab & "T_Focus" & VBTab & "T_Telescope" & VBTab &_
     "WindSpeed (M/S)" & VBTab & "WindDir (deg EofN)" & VBTab &_
     "Humidity (%)" & VBTab & "Rain (mm)" & VBTab & "Pressure (kPa)")
   objFile.Close
End If

'Create the engineering file (don't overwrite)
If objFSO.FileExists(strEngFile) Then
   Set objFolder = objFSO.GetFolder(logdir)
Else
   Set objFile = objFSO.CreateTextFile(strEngFile)
   objFile.Close
End If

Set objFSO = Nothing

End Sub