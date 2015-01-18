'Create a Folder for the night's data and begin log files
'C:\demonex\data\nyymmdd\nyymmdd.log (nightly data log)
'C:\demonex\data\nyymmdd\nyymmdd.eng (verbose engineering log)

night = WScript.Arguments(0)

Dim objFSO, objFolder, objShell, strDirectory
strDirectory = "C:\demonex\data\n" & night
strSubDirectory = "C:\demonex\data\n" & night
strLogFile = CStr(strSubDirectory & "\n" & night & ".log")
strEngFile = CStr(strSubDirectory & "\n" & night & ".eng")
Set objFSO = CreateObject("Scripting.FileSystemObject")

'Create the Folder
If objFSO.FolderExists(strDirectory) Then
   Set objFolder = objFSO.GetFolder(strDirectory)
Else
   Set objFolder = objFSO.CreateFolder(strDirectory)
End If

'Create the Log File (don't overwrite)
If objFSO.FileExists(strLogFile) Then
   Set objFolder = objFSO.GetFolder(strSubDirectory)
Else
   Set objFile = objFSO.CreateTextFile(strLogFile)
End If

'write the header
objFile.WriteLine("Filename" & VBTab &  "Object" & VBTab &_
  "Local Time" & VBTab & "ExpTime" & VBTab & "Airmass" & VBTab &_
  "Filter" & VBTab & "Meridian Flip" & VBTab & "T_Outside (C)" & VBTab &_
  "T_Camera (C)" & VBTab & "T_Focus" & VBTab & "T_Telescope" & VBTab &_
  "WindSpeed (M/S)" & VBTab & "WindDir (deg EofN)" & VBTab &_
  "Humidity (%)" & VBTab & "Rain (mm)" & VBTab & "Pressure (kPa)")

'Create the engineering file (don't overwrite)
If objFSO.FileExists(strEngFile) Then
   Set objFolder = objFSO.GetFolder(strSubDirectory)
Else
   Set objFile = objFSO.CreateTextFile(strEngFile)
End If

objFile.Close
Set objFSO = Nothing

'Set the data path to be tonight's folder
Set Cam = CreateObject("CCDSoft.Camera")
Cam.AutoSavePath = strSubDirectory




WScript.Quit(0)