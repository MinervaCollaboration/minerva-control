Sub AutoMap

  On Error Resume Next

  'Use TheSky to generate a text file of mapping points
  szPathToMapFile = "c:\demonex\scripts\map.txt"

  'If you want your script to run all night regardless of errors, set bIgnoreErrors = True
  bIgnoreErrors = True

  Const ForReading = 1


  objFSO = CreateObject("Scripting.FileSystemObject")
  MyFile = objFSO.OpenTextFile(szPathToMapFile, ForReading)

  'Reboot the scope and align on Home
  objEngFile.WriteLine("AutoMap (" & FormatDateTime(Now,3) & "): Rebooting Scope")
  RebootScope
  objEngFile.WriteLine("AutoMap (" & FormatDateTime(Now,3) & "): Realigning Scope")
  Align

  'First jog in Dec to get a more accurate sync
  For i=1 to 5

    Err.Clear 'Clear the error object
    bErrorOccurred = FALSE 'No error has occurred

    If (bErrorOccurred = False) then
      SyncTime
      objEngFile.WriteLine("AutoMap (" & FormatDateTime(Now,3) & "): Jogging South 5 degrees")
      Call objTel.Jog(300, "South")
      WScript.Sleep 10000
      Call PromptOnError(bErrorOccurred)
    end if
		
    if (bErrorOccurred = False) then
      objCam.ExposureTime = 5.0
      Call objCam.TakeImage()
      Call PromptOnError(bErrorOccurred)
    end if

    If (bErrorOccurred = False) then
      'Make sure TheSky's server settings allow remote clients to map
      'Uses TheSky's current settings for image scale
      objEngFile.WriteLine("AutoMap (" & FormatDateTime(Now,3) & "): Mapping Point")
      Call objTheSky.AutoMap()
      Call PromptOnError(bErrorOccurred)
    end if
  Next

  Do While (MyFile.AtEndOfStream <> True)

    Err.Clear 'Clear the error object
    bErrorOccurred = FALSE 'No error has occurred
		
    LineFromFile = MyFile.ReadLine
    dAz  = Mid(LineFromFile,22,8)
    dAlt = Mid(LineFromFile,38,7)

    if (bErrorOccurred = False) then
      SyncTime
      objEngFile.WriteLine("AutoMap (" & FormatDateTime(Now,3) & "): Moving to next map point")
      Call objTel.SlewToAzAlt(dAz, dAlt, "")
      'Wait for telescope to settle
      WScript.Sleep 10000
      Call PromptOnError(bErrorOccurred)
    end if
		
    if (bErrorOccurred = False) then
      objCam.ExposureTime = 5.0
      Call objCam.TakeImage()
      Call PromptOnError(bErrorOccurred)
    end if

    if (bErrorOccurred = False) then
      'Make sure TheSky's server settings allow remote clients to map
      'Uses TheSky's current settings for image scale
      objEngFile.WriteLine("AutoMap (" & FormatDateTime(Now,3) & "): Mapping point")
      Call objTheSky.AutoMap()
      Call PromptOnError(bErrorOccurred)
    end if

  Loop

End Sub

Sub PromptOnError(bErrorOccurred)
	Dim bExitScript

	'Debugging-remove the single quote from the line below
	'Exit Sub
		
	bErrorOccurred = False
	bExitScript = False

	if (bIgnoreErrors = True) then 
		'Ignore all errors except when the user Aborts
		if (CStr(Hex(Err.Number)) = "800404BC") then 
			'Do nothing and let the user abort
		else
			Err.Clear
		end if
	end if

	If bExitScript = vbYes Then
		WScript.Quit
	End if 

End Sub
