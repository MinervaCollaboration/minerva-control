Dim objFileSystem, objOutputFile
Dim strOutputFile

Const ForAppending = 8
Const ForReading = 1

'Include functions
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("ConnectAll.vbs", ForReading)
Execute objFile.ReadAll()




Pi = 4*Atn(1)

ra = Cdbl(WScript.Arguments(0))
dec = Cdbl(WScript.Arguments(1))
jdstart = Cdbl(WScript.Arguments(2))
jdend = Cdbl(WScript.Arguments(3))
objName = WScript.Arguments(4)
night = WScript.Arguments(5)

path = "C:\demonex\data\n" & night & "\"

'Open log and engineering files
strLogFile = path & "n" & night & ".log"
strEngFile = path & "n" & night & ".eng"
Set objLogFile = objFSO.OpenTextFile(strLogFile, ForAppending)
Set objEngFile = objFSO.OpenTextFile(strEngFile, ForAppending)

'Connects to everything
ConnectAll


'calculate the current JD
y = Year(Now)
m = Month(Now)
d = Day(Now)
h = Hour(Now)
mn = Minute(Now)
sec = Second(Now)
jdNow = jd(y, m, d, h, mn, sec)

'Wait until start time
if jdNow < jdStart then
  sleepTime = (jdStart - jdNow)*86400000
  objEngFile.WriteLine("DoObs (" & Now & "): Script Started before jdStart; waiting for " & sleeptime/1000 & " seconds")
  WScript.Sleep sleepTime
End If

objEngFile.WriteLine("DoObs (" & Now & "): Setting exposure time")
ExpTime = 10
objCam.ExposureTime = ExpTime

objEngFile.WriteLine("DoObs (" & Now & "): Setting Filename")
objCam.AutoSavePrefix = "TmpFileName"

'Run other commands while exposing and slewing
objEngFile.WriteLine("DoObs (" & Now & "): Setting Asynchronous Behavior")
objCam.Asynchronous = 1
objTel.Asynchronous = 1

'Initial Focus
Call FocusOffset = GetFocusOffset
'objEngFile.WriteLine("DoObs (" & Now & "): Focusing Telescope (T=" & objCam.focTemperature & "Focus=" & objCam.focPosition + focusOffset)


Do While (jdNow < jdEnd)
  objEngFile.WriteLine("DoObs (" & Now & "): Entering Loop; JDNow=" & jdNow & " JDEnd=" & jdEnd )

'  If RoofOpen Then
    objEngFile.WriteLine("DoObs (" & Now & "): Roof Open; observing")

    'SlewToRaDec
    slewStart = Now
    objEngFile.WriteLine("DoObs (" & Now & "): Slewing to " & ra & " " & dec )
    objTel.SlewToRaDec(ra,dec,objName)
    objEngFile.WriteLine("DoObs (" & Now & "): Slew Completed in " & Round((now - slewStart)*86400) & " seconds")

    'Focus Telescope
    Focus(Temp)

    'Set ExpTime (based on previous image?)
    'objCam.ExposureTime = ExpTime

    'wait for slew to complete
    Do While (objTel.IsSlewComplete = 0)
      'wait
    Loop

    'TakeImage
    objEngFile.WriteLine("DoObs (" & Now & "): Taking image")
    objCam.TakeImage
 
    'Calculate the Airmass from the telescope's altitude
    objTel.GetAzAlt
    strAirmass = 1/cos((90-objtel.dAlt)*Pi/180)

    'Write to the Log (Filename | Object | Local Time | Exptime | Airmass | Filter | Merian Flip | T_Outside (C) | T_Camera (C) | T_Focus (C) | T_Tele (C) | WindSpeed (M/S) | WindDir (deg EofN) | Humidity (%) | Rain (mm)| Pressure (kPa))
    strFileName = "n" & night & "." & objName & "." & GetIndex & ".fits"
    strFilter = objCam.szFilterName(objCam.FilterIndexZeroBased)
    strTCam = objCam.Temperature
    strTFoc = objCam.focTemperature
    strTTel = "??" 'not currently supported, but soon?
    strMerFlip = "??" 'how can I know that?

    'Gets weather info from http://www.winer.org/metricWeather.html
    strWindSpeed = "??"
    strWindDir = "??"
    strHumidity = "??"
    strRain = "??"
    strPressure = "??"
    strTemp = "??"
    GetWeather

    'Write to the log file
    objEngFile.WriteLine("DoObs (" & Now & "): Writing to Log")
    objLogFile.WriteLine(strFilename & VBTab & objName & VBTab & Now & VBTab &_
	strExpTime & VBTab & strAirmass & VBTab & strFilter & VBTab &_
        strMerFlip & VBTab & strTemp & VBTab &_
	strTCam & VBTab & strTFocus & VBTab & strTTel & VBTab &_
	strWindSpeed & VBTab & strWindDir & VBTab &_
	strHumidity & VBTab & strRain & VBTab & strPressure)

    'AutoMap
'    coorSolveStart = Now
'    objEngFile.WriteLine("DoObs (" & Now & "): Beginning Coordinate Solution)
'    Call objTheSky.AutoMap()
'    objEngFile.WriteLine("DoObs (" & Now & "): Completed Coordinate Solution in " & Round((coorSolveStart - Now)*86400) & " seconds")

    'CalcExpTime (based on previous image)?

     'Get the focus
'    GetFocus(strTFoc)
    

    'wait for exposure to complete
    objEngFile.WriteLine("DoObs (" & Now & "): Waiting for Exposure to Complete")
    Do While (objCam.IsExposureComplete = 0)
      'wait
    Loop

    'Rename file to something reasonable
    objFSO.MoveFile path & objCam.LastImageFileName, path & strFileName

'  Else
'    objEngFile.WriteLine("DoObs (" & Now & "): Roof Closed; retry in 5 minutes")
'    WScript.Sleep 300000  
'  End if

  'Recalculate the current time
  y = Year(Now)
  m = Month(Now)
  d = Day(Now)
  h = Hour(Now)
  mn = Minute(Now)
  sec = Second(Now)
  jdNow = jd(y, m, d, h, mn, sec)
wscript.quit
Loop

objEngFile.WriteLine("DoObs (" & Now & "): Exiting Loop " & jdNow & " " & jdEnd )
'msgbox("DoObs (" & Now & "): Exiting Loop " & jdNow & " " & jdEnd )

objEngFile.WriteLine("DoObs (" & Now & "): Done with Object " & adstr)
'msgbox("DoObs (" & Now & "): Done with Object " & ra & " " & dec)

objEngFile.Close
objLogFile.Close
Set objFSO = Nothing

WScript.Quit(0)

Function jd(yy, mm, dd, hr, mn, sec)
if yy < 0 then
  yy = yy + 1
End If
hr = hr + (mn / 60) + sec/3600
ggg = 1
if yy <= 1585 then
  ggg = 0
End If
jd = -1 * Int(7 * (Int((mm + 9) / 12) + yy) / 4)
s = 1
if (mm - 9) < 0 then
  s = -1
End If
a = abs(mm - 9)
j1 = Int(yy + s * Int(a / 7))
j1 = -1 * Int((Int(j1 / 100) + 1) * 3 / 4)
jd = jd + Int(275 * mm / 9) + dd + (ggg * j1)
jd = jd + 1721027 + 2 * ggg + 367 * yy - 0.5
jd = round(jd + (hr / 24), 5)
End Function

Function RoofOpen()
RoofOpen = False   ' False means not open

   Dim cstart, state
   Dim xml : Set xml = CreateObject("MSXML2.ServerXMLHTTP")

   On Error Resume Next
       xml.open "GET", "http://www.winer.org/roof.html", aSynch
       xml.setRequestHeader "Content-Type", "application/x-www-form-urlencoded"
       xml.send

       Do
         xml.waitForResponse 1*1000
       Loop Until xml.readyState=4 Or Err.Number<>0

       'assume roof is open if unknown
       If xml.readyState<>4 Or Err.Number<>0 Then
         xml.abort
         RoofOpen = True
         Exit Function
       End If
   On Error Goto 0

   If xml.Status = 200 Then
       return = xml.ResponseText

       cstart = InStr(return,"Roof State")
       If cstart=0 Then ' assume roof is open
           RoofOpen = True
           Exit Function
       End If

       state = Mid(return,cstart,40)
       If InStr(state,"OPEN<")=0 Then
           RoofOpen = False
       Else
           RoofOpen = True
       End If

   End If  ' xml.Status block
   Set xml = Nothing

End Function

'Check for errors; email me with error and engineering log if encountered
Function ErrorCheck
  If Err.number <> 0 Then
    Const cdoSendUsingPickup = 1 'Send message using the local SMTP service pickup directory.
    Const cdoSendUsingPort = 2 'Send the message using the network (SMTP over the network).
    Const cdoAnonymous = 0 'Do not authenticate
    Const cdoBasic = 1 'basic (clear-text) authentication
    Const cdoNTLM = 2 'NTLM

    Set objMessage = CreateObject("CDO.Message")
    objMessage.Subject = "DEMONEX Error n" & night
    objMessage.From = """DEMONEX"" <demonex3041@gmail.com>"
    objMessage.To = "jdeast@astronomy.ohio-state.edu"
    objMessage.TextBody = "The following error was encountered:" & VBCrLf &_
      Err.Description & VBCrLf & apgSeverityError & VBCrLf & Err.Number

    '==This section provides the configuration information for the remote SMTP server.
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/sendusing") = 2
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/smtpserver") = "smtp.gmail.com"
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/smtpauthenticate") = cdoBasic
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/sendusername") = "demonex3041"
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/sendpassword") = "TheDEMON666"
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/smtpserverport") = 25
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/smtpusessl") = True
    objMessage.Configuration.Fields.Item ("http://schemas.microsoft.com/cdo/configuration/smtpconnectiontimeout") = 60
    objMessage.Configuration.Fields.Update
    '==End remote SMTP server configuration section==

    'If exists, attach the engineering file
    attachment = path & "n" & night & ".eng"
    Set objFSO = CreateObject("Scripting.FileSystemObject")
    If objFSO.FileExists(attachment) Then
      objMessage.AddAttachment attachment
    End If
    
    don't actually email me during testing... don't want to spam myself...
    'MsgBox(Err.Description & VBCrLf & apgSeverityError & VBCrLf & Err.Number)
    'objMessage.Send
    WScript.Quit
  End If
End Function

'Get the weather parameters from the winer site
Function GetWeather()

   'Reset the Values
   strWindSpeed = "??"
   strWindDir = "??"
   strHumidity = "??"
   strRain = "??"
   strPressure = "??"
   strTemp = "??"

   Dim cstart, state
   Dim xml : Set xml = CreateObject("MSXML2.ServerXMLHTTP")

   On Error Resume Next
       xml.open "GET", "http://www.winer.org/metricWeather.html"
       xml.setRequestHeader "Content-Type", "application/x-www-form-urlencoded"
       xml.send

       Do
         xml.waitForResponse 1*1000
       Loop Until xml.readyState=4 Or Err.Number<>0

       'If error return empty strings
       If xml.readyState<>4 Or Err.Number<>0 Then
         xml.abort
         Exit Function
       End If
   On Error Goto 0

   If xml.Status = 200 Then
       return = xml.ResponseText

       'Get the Wind Speed
       cstart = InStr(return,"WINDSPEED=")+10
       cstart2 = InStr(cstart, return, "M/S >")
       strWindSpeed = Mid(return,cstart,cstart2-cstart)
  
       'Get the Wind Direction
       cstart = InStr(return,"WINDDIR=")+8
       cstart2 = InStr(cstart, return, "EofN >")
       strWindDir = Mid(return,cstart,cstart2-cstart)

       'Get the Humidity
       cstart = InStr(return,"HUMIDITY=")+9
       cstart2 = InStr(cstart, return, "%>")       
       strHumidity = Mid(return,cstart,cstart2-cstart)

       'Get the Rain
       cstart = InStr(return,"RAIN=")+5
       cstart2 = InStr(cstart, return, "mm>") 
       strRain = Mid(return,cstart,cstart2-cstart)

       'Get the Pressure
       cstart = InStr(return,"PRESSURE=")+9
       cstart2 = InStr(cstart, return, "kPa>") 
       strPressure = Mid(return,cstart,cstart2-cstart)

       'Get the Temperature
       cstart = InStr(return,"TEMPERATURE=")+12
       cstart2 = InStr(cstart, return, "C>") 
       strTemp = Mid(return,cstart,cstart2-cstart)

   End If  ' xml.Status block

   Set xml = Nothing


End Function

Function GetIndex()
     Dim objFSO, folder, colFiles, strFolder
     strExt = ".fits"

     Set objFSO = CreateObject("Scripting.FileSystemObject")
     Set objFolder = objFSO.GetFolder(path)
     Set colFiles = objFolder.Files

     dtmNewestDate = Now - 10000
     objFileFound = False
     For each objFile In colFiles
        objNamePos = InStr(objFile,objName)
        objExtPos = InStr(objFile,strExt)
        If objNamePos <> 0 and objExtPos <> 0 Then
  	  If objFile.DateCreated > dtmNewestDate Then
            dtmNewestDate = objFile.DateCreated
            strNewestFile = objFile.Path
            objNewestExt = objExtPos
            objFileFound = True
          End If
        End If
     Next

     If Not objFileFound Then
        GetIndex = "0001"
     Else
        objExtPos = InStr(strNewestFile,strExt)
        objIndex = Mid(strNewestFile, objExtPos-4,4)+1
        GetIndex = Right(string(4,"0") & objIndex, 4)
     End If
End Function

Function Connect()
  'Connect to TheSky
  objEngFile.WriteLine("DoObs (" & Now & "): Connecting to TheSky6")S
  On Error Resume Next
  Set objTheSky = WScript.CreateObject("TheSky6.RASCOMTheSky")
  ErrorCheck
  On Error Resume Next
  objTheSky.Connect()
  ErrorCheck

  'Connect to the Telescope
  objEngFile.WriteLine("DoObs (" & Now & "): Connecting to the telescope")
  On Error Resume Next
  Set objTel = WScript.CreateObject("TheSky6.RASCOMTele")
  ErrorCheck
  On Error Resume Next
  objTel.Connect()
  ErrorCheck

  'Connect to the Camera
  objEngFile.WriteLine("DoObs (" & Now & "): Connecting to the camera")
  On Error Resume Next
  Set objCam = CreateObject("CCDSoft.Camera")
  ErrorCheck
  On Error Resume Next
  objCam.Connect()
  ErrorCheck

  'Connect to the Focuser
  objEngFile.WriteLine("DoObs (" & Now & "): Connecting to the focuser")
  On Error Resume Next
  objCam.focConnect
  ErrorCheck
End Function

  