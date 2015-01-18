
'Get the weather parameters from the winer site
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
       xml.open "GET", "http://192.168.2.1/metricWeather.html"
       xml.setRequestHeader "Content-Type", "application/x-www-form-urlencoded"
       xml.send

       Do
         objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Waiting for response from server")
         xml.waitForResponse 1*1000
       Loop Until xml.readyState=4 Or Err.Number<>0

       'If error return unknown
       If xml.readyState<>4 Or Err.Number<>0 Then
         objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): Error: cannot connect to http://www.winer.org/metricWeather.html")
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

   Else 

       objEngFile.WriteLine("GetWeather (" & FormatDateTime(Now,3) & "): WARNING: Weather data retrieval failed, setting to unknown")  

   End If  ' xml.Status block

   Set xml = Nothing

End Function
