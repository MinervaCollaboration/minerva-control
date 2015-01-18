' Windows Script Host Sample Script
'
' ------------------------------------------------------------------------
'               Copyright (C) Software Bisque
'
' ------------------------------------------------------------------------


'Global Objects
Dim objTheSky
Dim objTel
Dim objCam

'Global User Variables see InitGlobalUserVariables()
Dim szPathToMapFile
Dim bIgnoreErrors

Const ForReading = 1
Const ForAppending = 8
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("Align.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("CheckCam.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("CheckTel.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("ConnectAll.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("DisconnectAll.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("LX200Cancel.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("RebootScope.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("SyncTime.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("TalkToLX200.vbs", ForReading)
Execute objFile.ReadAll()

'If started between midnight and noon, use the yesterday's date
If Hour(Now) < 12 Then
  night = Right(string(4,"0") & Year(Now), 4) &_
  Right(string(2,"0") & Month(Now), 2) &_
  Right(string(2,"0") & Day(Now)-1, 2)
Else 
  night = Right(string(4,"0") & Year(Now), 4) &_
    Right(string(2,"0") & Month(Now), 2) &_
    Right(string(2,"0") & Day(Now), 2)
End If
datapath = "C:\demonex\data\n" & night & "\"

'Open log and engineering files
strLogFile = datapath & "n" & night & ".log"
strEngFile = datapath & "n" & night & ".eng"
Set objLogFile = objFSO.OpenTextFile(strLogFile, ForAppending)
Set objEngFile = objFSO.OpenTextFile(strEngFile, ForAppending)


' ********************************************************************************
' *
' * Below is the flow of program execution
' * See the subroutine TargetLoop to see where the real work is done

Call InitGlobalUserVariables()
Call CreateObjects()

Call ConnectObjects()

Call TargetLoop()

Call DisconnectObjects()
Call DeleteObjects()


' ********************************************************************************
' *
' * Below are all the subroutines used in this sample
' *
Sub Welcome()
    Dim intDoIt

    intDoIt =  MsgBox(L_Welcome_MsgBox_Message_Text, _
                      vbOKCancel + vbInformation,    _
                      L_Welcome_MsgBox_Title_Text )
    If intDoIt = vbCancel Then
        WScript.Quit
    End If
End Sub

Sub InitGlobalUserVariables()

	'Use TheSky to generate a text file of mapping points
	szPathToMapFile = "c:\demonex\scripts\map.txt"

	'If you want your script to run all night regardless of errors, set bIgnoreErrors = True
	bIgnoreErrors = True

End Sub

Sub GetCoordinatesFromLine(LineFromFile, dAz, dAlt)

	dAz  = Mid(LineFromFile,22,8)
	dAlt = Mid(LineFromFile,38,7)

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

	if (Err.Number) then 
		bErrorOccurred = True
		bExitScript = MsgBox ("An error has occurred running this script.  Error # " & CStr(Hex(Err.Number)) & " " & Err.Description + CRLF + CRLF + "Exit Script?", vbYesNo + vbInformation)
	end if

	If bExitScript = vbYes Then
		WScript.Quit
	End if 

End Sub

Sub TargetLoop()

	'Debugging-add a single quote before line below
	On Error Resume Next

	Dim MyFile
	Dim fso
	Const ForReading = 1
	Dim dAz
	Dim dAlt
	Dim bErrorOccurred

	Set fso = CreateObject("Scripting.FileSystemObject")
	Set MyFile = fso.OpenTextFile(szPathToMapFile, ForReading)

	Do While (MyFile.AtEndOfStream <> True)

		Err.Clear 'Clear the error object
		bErrorOccurred = FALSE 'No error has occurred
		
		Call GetCoordinatesFromLine(MyFile.ReadLine, dAz, dAlt)

'msgbox(daz & " " & dalt)
		if (bErrorOccurred = False) then
                        SyncTime
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
			Call objTheSky.AutoMap()
			Call PromptOnError(bErrorOccurred)
		end if
	Loop

End Sub


Sub CreateObjects()
	Set objTheSky = WScript.CreateObject("TheSky6.RASCOMTheSky")
	Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
	Set objCam = WScript.CreateObject("CCDSoft.Camera")
End Sub

Sub ConnectObjects()
	objTheSky.Connect()
	objTel.Connect()
	objCam.Connect()
End Sub

Sub DisconnectObjects()
	objTheSky.Disconnect()
	objTel.Disconnect()
	objCam.Disconnect()
End Sub 

Sub DeleteObjects()
	Set objTheSky = Nothing
	Set objTel = Nothing
	Set objCam = Nothing
End Sub 

	
