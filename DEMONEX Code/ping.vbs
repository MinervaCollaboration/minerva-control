Const ForReading = 1
Const ForAppending = 8

Set WshShell = WScript.CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.fileSystemObject")

Set objFile = objFSO.OpenTextFile("jd.vbs", ForReading)
Execute objFile.ReadAll()

Do While True

  'Ensure we ping at even, 1 minute intervals
  WScript.Sleep 1000 'make sure we don't wait 1 second
  WScript.Sleep (60 - second(now))*1000

  'get the weather
  Call GetWeather(strWindSpeed,strWindDir,strHumidity,strRain,strPressure,strTemp)

  Set WshExec = WshShell.Exec("ping -n 1 209.104.1.58")
  strPingResults = LCase(WshExec.StdOut.ReadAll)
  Set objPingFile = objFSO.OpenTextFile("C:\demonex\share\ping.txt", ForAppending)

  cstart = InStr(strPingResults, "time=")+5
  If cstart <> 5 Then
    cstart2 = InStr(cstart, strPingResults, "ms")
    latency = Mid(strPingResults, cstart, cstart2-cstart)
    objPingFile.WriteLine(Now & " 1 " & latency & " " & strWindSpeed & " " & strWindDir) 
  Else 
    objPingFile.WriteLine(Now & " 0 -1 " & strWindSpeed & " " & strWindDir)
  End If
  objPingFile.Close

  'send a bigger packet (more like VNC)
  Set WshExec = WshShell.Exec("ping -n 1 63.225.34.2")
  strPingResults = LCase(WshExec.StdOut.ReadAll)
  Set objPingFile = objFSO.OpenTextFile("C:\demonex\share\pingnewisp.txt", ForAppending)

  cstart = InStr(strPingResults, "time=")+5
  If cstart <> 5 Then
    cstart2 = InStr(cstart, strPingResults, "ms")
    latency = Mid(strPingResults, cstart, cstart2-cstart)
    objPingFile.WriteLine(Now & " 1 " & latency & " " & strWindSpeed & " " & strWindDir) 
  Else 
    objPingFile.WriteLine(Now & " 0 -1 " & strWindSpeed & " " & strWindDir)
  End If
  objPingFile.Close


  'send a bigger packet (more like VNC)
  Set WshExec = WshShell.Exec("ping -n 1 cassini.mps.ohio-state.edu")
  strPingResults = LCase(WshExec.StdOut.ReadAll)
  Set objPingFile = objFSO.OpenTextFile("C:\demonex\share\pingosu.txt", ForAppending)

  cstart = InStr(strPingResults, "time=")+5
  If cstart <> 5 Then
    cstart2 = InStr(cstart, strPingResults, "ms")
    latency = Mid(strPingResults, cstart, cstart2-cstart)
    objPingFile.WriteLine(Now & " 1 " & latency & " " & strWindSpeed & " " & strWindDir) 
  Else 
    objPingFile.WriteLine(Now & " 0 -1 " & strWindSpeed & " " & strWindDir)
  End If
  objPingFile.Close

Loop

'Get the weather parameters from the winer site (and convert to metric)
Function GetWeather(strWindSpeed,strWindDir,strHumidity,strRain,strPressure,strTemp)

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
       xml.open "GET", "http://192.168.2.1/weather.html"
       xml.setRequestHeader "Content-Type", "application/x-www-form-urlencoded"
       xml.send

       Do
         xml.waitForResponse 1*1000
       Loop Until xml.readyState=4 Or Err.Number<>0

       'If error return unknown
       If xml.readyState<>4 Or Err.Number<>0 Then
         xml.abort
         Exit Function
       End If
   On Error Goto 0
   If xml.Status = 200 Then
       return = xml.ResponseText

      'Make sure the page is current
       cstart = InStr(return,"LASTUPDATED")
       If cstart=0 Then
'
       Else 
         cstart2 = InStr(cstart, return, ">")
         jdLastUpdated = Mid(return,cstart+13,cstart2-cstart-13)       
         jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now)) + 0.5
         If ((jdNow - jdLastUpdated)*1440) > 5 Then Exit Function
       End If

       'Make sure the RainWise is up
       cstart = InStr(return,"RWISE_VALID=")+12
       If cstart=12 Then
           RainWiseUp = True
       Else          
         cstart2 = InStr(cstart, return, ">")
         If cstart2 > cstart Then RainWiseUp = Mid(return,cstart,cstart2-cstart)
         If RainWiseUp = "1" Then 
           RainWiseUp = True
         Else
           RainWiseUp = False
         End If
       End If

       'Make sure the Omega is up
       cstart = InStr(return,"OMEGA_VALID=")+12
       If cstart=12 Then
           OmegaUp = True
       Else        
         cstart2 = InStr(cstart, return, ">")
         If cstart2 > cstart Then OmegaUp = Mid(return,cstart,cstart2-cstart)
         If OmegaUp = "1" Then 
           OmegaUp = True
         Else
           OmegaUp = False
         End If
       End If

       'Make sure the DPM is up
       cstart = InStr(return,"DPM_VALID=")+10
       If cstart=10 Then
           DPMUp = True
       Else 
         cstart2 = InStr(cstart, return, ">")
         If cstart2 > cstart Then DPMUp = Mid(return,cstart,cstart2-cstart)
         If DPMUp = "1" Then 
           DPMUp = True
         Else
           DPMUp = False
         End If
       End If

       If Not DPMUp Then 
'
       Else
         
         If Not RainWiseUp and Not OmegaUp Then        
           'Get the Temperature
           cstart = InStr(return,"DPM_TEMP_F=")+11
           If cstart=11 Then
'
           Else
             cstart2 = InStr(cstart, return, " F>")
             If cstart2 > cstart Then strTemp = (Mid(return,cstart,cstart2-cstart) - 32)/1.8
           End If
         End If
       
         'Get the Pressure
         cstart = InStr(return,"PRESSURE=")+9
         If cstart=9 Then
'
         Else
           cstart2 = InStr(cstart, return, "inHg>") 
           If cstart2 > cstart Then strPressure = Mid(return,cstart,cstart2-cstart)*3.386      
         End If

       End If

       If Not OmegaUp Then
'
       Else
       
         If Not RainWiseUp Then      
           'Get the Humidity
           cstart = InStr(return,"OMEGA_RELHUMID=")+15
           If cstart=15 Then
'
           Else
             cstart2 = InStr(cstart, return, " %>")       
             If cstart2 > cstart Then strHumidity = Mid(return,cstart,cstart2-cstart)
           End If  
       
           'Get the Temperature
           cstart = InStr(return,"OMEGA_TEMP_F=")+13
           If cstart=13 Then
'
           Else
             cstart2 = InStr(cstart, return, " F>")
             If cstart2 > cstart Then strTemp = (Mid(return,cstart,cstart2-cstart) - 32)/1.8
           End If
         End If
         
       End If

       If Not RainWiseUp Then
'
       Else 
         'Get the Wind Speed
         cstart = InStr(return,"WINDSPEED=")+10
         If cstart=10 Then
'
         Else
           cstart2 = InStr(cstart, return, "MPH >")
           If cstart2 > cstart Then strWindSpeed = Mid(return,cstart,cstart2-cstart)*0.44704
         End If

         'Get the Wind Direction
         cstart = InStr(return,"WINDDIR=")+8
         If cstart=8 Then
'
         Else
           cstart2 = InStr(cstart, return, "EofN >")
           If cstart2 > cstart Then strWindDir = Mid(return,cstart,cstart2-cstart)
         End If

         'Get the Humidity
         cstart = InStr(return,"HUMIDITY=")+9
         If cstart=9 Then
'
         Else
           cstart2 = InStr(cstart, return, "%>")       
           If cstart2 > cstart Then strHumidity = Mid(return,cstart,cstart2-cstart)
         End If

         'Get the Rain
         cstart = InStr(return,"RAIN=")+5
         If cstart=5 Then
'
         Else
           cstart2 = InStr(cstart, return, "in>")
           If cstart2 > cstart Then strRain = Mid(return,cstart,cstart2-cstart)*25.4
         End If

         If Not DPMUp Then
           'Get the Pressure
           cstart = InStr(return,"RWISE_PRESS_IN=")+15
           If cstart=15 Then
'
           Else
             cstart2 = InStr(cstart, return, "inHg>") 
             If cstart2 > cstart Then strPressure = Mid(return,cstart,cstart2-cstart)*3.386
           End If
         End If

         'Get the Temperature
         cstart = InStr(return,"TEMPERATURE=")+12
         cstart2 = InStr(cstart, return, "F>") 
         If cstart2 > cstart Then strTemp = (Mid(return,cstart,cstart2-cstart) - 32)/1.8

       End If

   Else 
'
   End If  ' xml.Status block

   Set xml = Nothing

End Function