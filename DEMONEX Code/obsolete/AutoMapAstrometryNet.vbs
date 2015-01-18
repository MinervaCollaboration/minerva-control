'Global Objects
Dim objTheSky
Dim objTel
Dim objCam

'Global User Variables see InitGlobalUserVariables()
Dim szPathToMapFile
Dim bIgnoreErrors


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

MsgBox("Done")

' ********************************************************************************
' *
' * Below are all the subroutines used in this sample
' *

Sub InitGlobalUserVariables()

	'Use TheSky to generate a text file of mapping points
	szPathToMapFile = "c:\demonex\scripts\finemap.txt"

	'If you want your script to run all night regardless of errors, set bIgnoreErrors = True
	bIgnoreErrors = True

End Sub

Sub GetCoordinatesFromLine(LineFromFile, dAz, dAlt)

	dAz  = Mid(LineFromFile,23,8)
	dAlt = Mid(LineFromFile,40,7)

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

        'change to R filter (better for mapping solution)
        objCam.FilterIndexZeroBased = 2

	Do While (MyFile.AtEndOfStream <> True)

		Err.Clear 'Clear the error object
		bErrorOccurred = FALSE 'No error has occurred
		
		Call GetCoordinatesFromLine(MyFile.ReadLine, dAz, dAlt)

		if (bErrorOccurred = False) then
			Call objTel.SlewToAzAlt(dAz, dAlt, "")

                        'Wait for Telescope to finish slewing
                        RACurrent = -1
                        RAPrevious = -2
                        DecCurrent = -1
                        DecPrevious = -2
                        Do While Round(RAPrevious,5) <> Round(RACurrent,5) and Round(DecPrevious,4) <> Round(DecCurrent,4)
                          RAPrevious = RACurrent
                          DecPrevious = DecCurrent
                          Call objTel.GetRaDec()
                          RACurrent  = objTel.dRa
                          DecCurrent = objTel.dDec
                          WScript.Sleep 5000
                        Loop
                        WScript.Sleep 10000

			Call PromptOnError(bErrorOccurred)
		end if
		
		if (bErrorOccurred = False) then
			objCam.ExposureTime = 15.0
			Call objCam.TakeImage()
			Call PromptOnError(bErrorOccurred)
		end if

		if (bErrorOccurred = False) then
			'Make sure TheSky's server settings allow remote clients to map
			'Uses TheSky's current settings for image scale
                        Set Image = CreateObject("CCDSoft.Image")
                        Image.AttachToActiveImager
                        Image.Save
                        Call SolveField(Image.Path, RACenter, DecCenter)
                        If RACenter <> "FAIL" Then

   RADecActNow = Utils.Precess2000ToNow(RACenter,DecCenter)
   StrADAct = Utils.ConvertEquatorialToString(RADecActNow(0),RADecActNow(1),4)
   a = split(StrADAct)
   strRAAct = a(1) & a(2) & a(3)
   strDecAct = a(6)

                          Set SolvedFile = objFSO.OpenTextFile("C:\demonex\scripts\tpoint.txt", ForAppending)
                          SolvedFile.WriteLine(ActRA & " " & ActDec & " " & RA & " " & Dec & " " & LST)
                          SolvedFile.Close
                        End If
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

        objCam.BinX = 1
        objCam.BinY = 1
        objCam.Abort
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

	
