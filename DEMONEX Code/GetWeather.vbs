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
         objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Waiting for response from server")
         xml.waitForResponse 1*1000
       Loop Until xml.readyState=4 Or Err.Number<>0

       'If error return unknown
       If xml.readyState<>4 Or Err.Number<>0 Then
         objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: cannot connect to http://www.winer.org/weather.html")
         xml.abort
         Exit Function
       End If
   On Error Goto 0
   If xml.Status = 200 Then
       return = xml.ResponseText

      'Make sure the page is current
       cstart = InStr(return,"LASTUPDATED")
       If cstart=0 Then
         objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: cannot find 'LASTUPDATED' tag, assuming everything is current")
       Else 
         cstart2 = InStr(cstart, return, ">")
         jdLastUpdated = Mid(return,cstart+13,cstart2-cstart-13)       
         jdNow = jd(Year(Now),Month(Now),Day(Now),Hour(Now),Minute(Now),Second(Now)) + 0.5

         objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): weather page last updated " & ((jdNow - jdLastUpdated)*1440) & " minutes ago")

         If ((jdNow - jdLastUpdated)*1440) > 5 Then
             objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: page not updated for " & ((jdNow - jdLastUpdated)*1440) & " minutes; returning unknown")
             If NotEmailedDaemon Then
               Call Email(curatoremail & "," & studentEmail ,_
                          "obsDaemon Down","Mark and Pat," & vbCrLf & vbCrLf &_
                          "The obsDaemon last updated the weather page " &_
                          Round((jdNow - jdLastUpdated)*1440,2) &_
                          " minutes ago, can you please check it out for me?" &_
                          vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
                NotEmailedDaemon = False
              End If
              Exit Function
         End If
       End If

       If Not NotEmailedDaemon Then
         NotEmailedDaemon = True
               Call Email(curatoremail & "," & studentEmail ,_
                    "obsDaemon Back Up","Mark and Pat," & vbCrLf & vbCrLf &_
                    "The obsDaemon is back online and last updated the roof page " &_
                    Round((jdNow - jdLastUpdated)*1440,2) &_
                    " minutes ago." &_
                    vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
       End If

       'Make sure the RainWise is up
       cstart = InStr(return,"RWISE_VALID=")+12
       If cstart=12 Then
           objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: cannot find 'RWISE_VALID' tag, assuming online")
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
           objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: cannot find 'OMEGA_VALID' tag, assuming online")
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
           objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: cannot find 'DPM_VALID' tag, assuming online")
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
         objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: DPM down")          
         If NotEmailedDPM Then
'               Call Email(curatoremail & "," & studentEmail ,_
               Call Email(studentEmail ,_
                        "DPM Down","Mark and Pat," & vbCrLf & vbCrLf &_
                        "DPM is down, can you please check it out for me?" &_
                        vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
             NotEmailedDPM = False
         End If
       Else
         
         If Not RainWiseUp and Not OmegaUp Then        
           'Get the Temperature
           cstart = InStr(return,"DPM_TEMP_F=")+11
           If cstart=11 Then
             objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: 'DPM_TEMP_F' tag does not exist")
           Else
             cstart2 = InStr(cstart, return, " F>")
             If cstart2 > cstart Then strTemp = (Mid(return,cstart,cstart2-cstart) - 32)/1.8
           End If
         End If
       
         'Get the Pressure
         cstart = InStr(return,"PRESSURE=")+9
         If cstart=9 Then
           objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: 'PRESSURE' tag does not exist")
         Else
           cstart2 = InStr(cstart, return, "inHg>") 
           If cstart2 > cstart Then strPressure = Mid(return,cstart,cstart2-cstart)*3.386      
         End If

         If Not NotEmailedDPM Then
           NotEmailedDPM = True
'               Call Email(curatoremail & "," & studentEmail ,_
               Call Email(studentEmail ,_
                      "DPM Back Up","Mark and Pat," & vbCrLf & vbCrLf &_
                      "DPM is back online." &_
                      vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
         End If
       End If

       If Not OmegaUp Then
         objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: Omega down")          
         If NotEmailedOmega Then
'               Call Email(curatoremail & "," & studentEmail ,_
               Call Email(studentEmail ,_
                        "Omega Down","Mark and Pat," & vbCrLf & vbCrLf &_
                        "Omega is down, can you please check it out for me?" &_
                        vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
             NotEmailedOmega = False
         End If
       Else
       
         If Not RainWiseUp Then      
           'Get the Humidity
           cstart = InStr(return,"OMEGA_RELHUMID=")+15
           If cstart=15 Then
             objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: 'OMEGA_RELHUMID' tag does not exist")
           Else
             cstart2 = InStr(cstart, return, " %>")       
             If cstart2 > cstart Then strHumidity = Mid(return,cstart,cstart2-cstart)
           End If  
       
           'Get the Temperature
           cstart = InStr(return,"OMEGA_TEMP_F=")+13
           If cstart=13 Then
             objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: 'OMEGA_TEMP_F' tag does not exist")
           Else
             cstart2 = InStr(cstart, return, " F>")
             If cstart2 > cstart Then strTemp = (Mid(return,cstart,cstart2-cstart) - 32)/1.8
           End If
         End If
         
         If Not NotEmailedOmega Then
           NotEmailedOmega = True
'               Call Email(curatoremail & "," & studentEmail ,_
               Call Email(studentEmail ,_
                      "Omega Back Up","Mark and Pat," & vbCrLf & vbCrLf &_
                      "Omega is back online." &_
                      vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
         End If
       End If

       If Not RainWiseUp Then
         objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: RainWise down")          
         If NotEmailedRainWise Then
'               Call Email(curatoremail & "," & studentEmail ,_
               Call Email(studentEmail ,_
                        "RainWise Down","Mark and Pat," & vbCrLf & vbCrLf &_
                        "The RainWise is down, can you please check it out for me?" &_
                        vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
             NotEmailedRainWise = False
         End If
       Else 
         'Get the Wind Speed
         cstart = InStr(return,"WINDSPEED=")+10
         If cstart=10 Then
           objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: 'WINDSPEED' tag does not exist")
         Else
           cstart2 = InStr(cstart, return, "MPH >")
           If cstart2 > cstart Then strWindSpeed = Mid(return,cstart,cstart2-cstart)*0.44704
         End If

         'Get the Wind Direction
         cstart = InStr(return,"WINDDIR=")+8
         If cstart=8 Then
           objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: 'WINDDIR' tag does not exist")
         Else
           cstart2 = InStr(cstart, return, "EofN >")
           If cstart2 > cstart Then strWindDir = Mid(return,cstart,cstart2-cstart)
         End If

         'Get the Humidity
         cstart = InStr(return,"HUMIDITY=")+9
         If cstart=9 Then
           objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: 'HUMIDITY' tag does not exist")
         Else
           cstart2 = InStr(cstart, return, "%>")       
           If cstart2 > cstart Then strHumidity = Mid(return,cstart,cstart2-cstart)
         End If

         'Get the Rain
         cstart = InStr(return,"RAIN=")+5
         If cstart=5 Then
           objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: 'RAIN' tag does not exist")
         Else
           cstart2 = InStr(cstart, return, "in>")
           If cstart2 > cstart Then strRain = Mid(return,cstart,cstart2-cstart)*25.4
         End If

         If Not DPMUp Then
           objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Warning: DPM down; using RainWise Pressure")            
           'Get the Pressure
           cstart = InStr(return,"RWISE_PRESS_IN=")+15
           If cstart=15 Then
             objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: 'RWISE_PRESS_IN' tag does not exist")
           Else
             cstart2 = InStr(cstart, return, "inHg>") 
             If cstart2 > cstart Then strPressure = Mid(return,cstart,cstart2-cstart)*3.386
           End If
         End If

         'Get the Temperature
         cstart = InStr(return,"TEMPERATURE=")+12
         cstart2 = InStr(cstart, return, "F>") 
         If cstart2 > cstart Then strTemp = (Mid(return,cstart,cstart2-cstart) - 32)/1.8

         If Not NotEmailedRainWise Then
           NotEmailedRainWise = True
'               Call Email(curatoremail & "," & studentEmail ,_
               Call Email(studentEmail ,_
                     "RainWise Back Up","Mark and Pat," & vbCrLf & vbCrLf &_
                      "The RainWise is back online." &_
                      vbCrLf & vbCrLf & "Love," & vbCrLf & "DEMONEX","","","") 
         End If

       End If

   Else 

       objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: Weather data retrieval failed, setting to unknown")  

   End If  ' xml.Status block

   Set xml = Nothing

End Function