Const ForReading = 1
Const ForWriting = 2
Const ForAppending = 8
Set objFSO = CreateObject("Scripting.fileSystemObject")
Set objFile = objFSO.OpenTextFile("Email.vbs", ForReading)
Execute objFile.ReadAll()
Set objFile = objFSO.OpenTextFile("jd.vbs", ForReading)
Execute objFile.ReadAll()
night = "20090127"
PIEmail = "gaudi@astronomy.ohio-state.edu"
CuratorEmail = "winer.obs@gmail.com,pat.trueblood@gmail.com,mtrueblood@noao.edu"
StudentEmail = "jdeast@astronomy.ohio-state.edu"
EmergencyTxt = "6178403045@txt.att.net"
NotEmailed = True

'Get the weather parameters from the winer site
'Function GetWeather(strWindSpeed,strWindDir,strHumidity,strRain,strPressure,strTemp)

   'Reset the Values
   strWindSpeed = "??"
   strWindDir = "??"
   strHumidity = "??"
   strRain = "??"
   strPressure = "??"
   strTemp = "??"

   Dim cstart, state
   Dim xml : Set xml = CreateObject("MSXML2.ServerXMLHTTP")

'   On Error Resume Next
       xml.open "GET", "http://192.168.2.1/weather.html"
       xml.setRequestHeader "Content-Type", "application/x-www-form-urlencoded"
       xml.send

       Do
         xml.waitForResponse 1*1000
       Loop Until xml.readyState=4 Or Err.Number<>0

       'If error return unknown
       If xml.readyState<>4 Or Err.Number<>0 Then
         MsgBox("GetWeather (" & FormatDateTime(Now,3) & "): Error: cannot connect to http://www.winer.org/weather.html")
         xml.abort
'         Exit Function
       End If
'   On Error Goto 0

'msgbox(xml.Status)

'   If xml.Status = 200 Then
       return = xml.ResponseText

      'Make sure the page is current
       cstart = InStr(return,"LASTUPDATED")
       If cstart=0 Then
           MsgBox("GetWeather (" & FormatDateTime(Now,3) & "): Error: cannot find 'LASTUPDATED' tag, assuming roof is open")
'           Exit Function
       End If 
  
       cstart2 = InStr(cstart, return, " >")
       jdLastUpdated = Mid(return,cstart+13,cstart2-cstart-13)       
       jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now)) + 0.5

MsgBox(jdLastUpdated & " " & jdNow)

       If ((jdNow - jdLastUpdated)*1440) > 1 Then
           MsgBox("GetWeather (" & FormatDateTime(Now,3) & "): Error: page not updated for " & ((jdNow - jdLastUpdated)*1440) & " minutes; returning unknown")
           If NotEmailed Then
             Call Email(studentEmail,_ 
                        "obsDaemon Down","Phil," & vbCrLf & vbCrLf &_
                        "The obsDaemon last updated the weather page " &_
                        Round((jdNow - jdLastUpdated)*1440,2) &_
                        " minutes ago, can you please check it out for me?" &_
                        vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
              NotEmailed = False
            End If
'            Exit Function
       End If

       'Get the Wind Speed
       cstart = InStr(return,"WINDSPEED=")+10
       cstart2 = InStr(cstart, return, "MPH >")
       If cstart2 > cstart Then strWindSpeed = Mid(return,cstart,cstart2-cstart)*0.44704
 
       'Get the Wind Direction
       cstart = InStr(return,"WINDDIR=")+8
       cstart2 = InStr(cstart, return, "EofN >")
       If cstart2 > cstart Then strWindDir = Mid(return,cstart,cstart2-cstart)

       'Get the Humidity
       cstart = InStr(return,"HUMIDITY=")+9
       cstart2 = InStr(cstart, return, "%>")       
       If cstart2 > cstart Then strHumidity = Mid(return,cstart,cstart2-cstart)

       'Get the Rain
       cstart = InStr(return,"RAIN=")+5
       cstart2 = InStr(cstart, return, "in>") 
       If cstart2 > cstart Then strRain = Mid(return,cstart,cstart2-cstart)*25.4

       'Get the Pressure
       cstart = InStr(return,"PRESSURE=")+9
       cstart2 = InStr(cstart, return, "inHg>") 
       If cstart2 > cstart Then strPressure = Mid(return,cstart,cstart2-cstart)*3.386

       'Get the Temperature
       cstart = InStr(return,"TEMPERATURE=")+12
       cstart2 = InStr(cstart, return, "F>") 
       If cstart2 > cstart Then strTemp = (Mid(return,cstart,cstart2-cstart) - 32)/1.8

msgbox(strWindSpeed & " " & StrWindDir & " " & strHumidity & " " & strRain & " " & strPressure & " " & strTemp)

'   Else 
'       MsgBox("GetWeather (" & FormatDateTime(Now,3) & "): WARNING: Weather data retrieval failed, setting to unknown")  
'   End If  ' xml.Status block

   Set xml = Nothing

'End Function