Sub FindGuideStar

  objCam.AutoGuider = 1
  objCam.Asynchronous = 0

  'Bounds the area of the prospective guide stars
  Edge = 50 + GuideBoxSize/2
  MaxMag = 2.0
  MinFWHM = 1.5
  MaxEllipticity = 1.25
  MaxClass = 0.1

  MaxX = objCam.WidthInPixels - Edge
  MinX = Edge
  MaxY = objCam.HeightInPixels - Edge
  MinY = Edge

  objCam.AutoSaveOn = 1
  objCam.AutoSavePrefix = "AutoGuider"
  objCam.AutoSavePath = datadir
  Set objImage = WScript.CreateObject("CCDSoft.Image")

  'Minimum Distance between stars (don't confuse guider)
  objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Setting MinDist")
  Mindist = sqr(2)*GuideBoxSize/2 + 3

  'Double exposure time until adequate signal, up to 51.2 seconds
  For i=0 to 10
    objCam.ExposureTime = 0.1*(2^i)
    objCam.AutoGuiderExposureTime = 0.1*(2^i)

    objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Taking Autoguiding acquisition image for " &_
      objCam.AutoGuiderExposureTime & " seconds")
    objCam.TakeImage

    objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Attaching to Image")
    objImage.AttachToActiveAutoGuider

    objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Determining coordinates of brightest star")
    objImage.ShowInventory

    X = objImage.InventoryArray(cdInventoryX)
    Y = objImage.InventoryArray(cdInventoryY)
    Magnitude    = objImage.InventoryArray(cdInventoryMagnitude)
    objClass     = objImage.InventoryArray(cdInventoryClass)
    FWHM         = objImage.InventoryArray(cdInventoryFWHM)
    MajorAxis    = objImage.InventoryArray(cdInventoryMajorAxis)
    MinorAxis    = objImage.InventoryArray(cdInventoryMinorAxis)
    Theta        = objImage.InventoryArray(cdInventoryTheta)
    Ellipticity  = objImage.InventoryArray(cdInventoryEllipticity)

    Star = -1
    Nstars = UBound(X)
    'Make sure the guide star is bright enough and not near an edge
    If Nstars > 0 Then
      For j=0 to Nstars - 1
        If Magnitude(j) > maxMag Then
          Exit For
        Else
          NearestNeighbor = 9999
          For k=0 to NStars - 1
            If k <> j Then            
              Dist = sqr((x(j)-x(k))^2 + (y(j) - y(k))^2)
              If Dist < NearestNeighbor and Dist <> 0 Then      
                NearestNeighbor = Dist
              End If
            End If
          Next
         
          objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): MinDist " & NearestNeighbor)

          If X(j) < MaxX and x(j) > MinX and Y(j) < MaxY and Y(j) > MinY and FWHM(j) > MinFWHM and NearestNeighbor > MinDist and Ellipticity(j) < MaxEllipticity and objClass(j) < MaxClass Then
            Star = j
            Exit For
          Else

            If x(j) > Maxx then 
              objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide Star " & j+1 & " Rejected: X = " & x(j) & " > " & Maxx)
            End If
            If x(j) < Minx Then
              objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide Star " & j+1 & " Rejected: X = " & x(j) & " < " & Minx)
            End If
            If Y(j) > MaxY Then
              objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide Star " & j+1 & " Rejected: Y = " & Y(j) & " > " & Maxy)
            End If
            If Y(j) < MinY Then
              objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide Star " & j+1 & " Rejected: Y = " & Y(j) & " < " & MinY)
            End If
            If FWHM(j) < MinFWHM Then
              objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide Star " & j+1 & " Rejected: FWHM = " & FWHM(j) & " < " & MinFWHM)
            End If
            If NearestNeighbor < MinDist Then
              objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide Star " & j+1 & " Rejected: Nearest Neighbor = " & NearestNeighbor & " < " & MinDist)
            End If
            If Ellipticity(j) > MaxEllipticity Then
              objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide Star " & j+1 & " Rejected: Ellipticity = " & Ellipticity(j) & " > " & MaxEllipticity) 
            End if
            If objClass(j) > MaxClass Then
              objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide Star " & j+1 & " Rejected: Class = " & objClass(j) & " > " & MaxClass) 
            End if

          End If       
        End If
      Next
    End If

    'Found Good Guide Star
    If Star <> -1 Then 
      Exit For
    End If 
    objImage.Close

    objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): No Guide star found with exposure time " & objCam.ExposureTime)
  Next

  If Star = -1 Then
    objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): No Guide Star Found; bad focus?") 
    Exit Sub
  End If

  objCam.GuideStarX = X(Star)
  objCam.GuideStarY = Y(Star)

  If CBool(MeridianFlip) = True Then
    objCam.ReverseX = 1
  ElseIf CBool(MeridianFlip) = False Then
    objCam.ReverseX = 0
  Else
    objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): ERROR: Unknown meridian flip (" & MeridianFlip & "); this could get interesting")
  End If

  objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Meridian Flip = " & MeridianFlip & " set reverseX to " & objCam.ReverseX)
  objCam.TelescopeDeclination = adNow(1)
  objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Set declination to " & adNow(1) & " for guiding")


  objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Setting up subframe")
  objCam.PropLng("m_TrackBoxHiRes.cx") = GuideBoxSize
  objCam.PropLng("m_TrackBoxHiRes.cy") = GuideBoxSize

  objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide star found at (x,y) = (" & X(Star) & "," & Y(Star) &_ 
    "); Magnitude = " & Magnitude(Star) & ", Class = " & objClass(Star) & ", FWHM = " & FWHM(Star) & ", Ellipticity = " & Ellipticity(Star))
  AcquireGuideStar = False

'I DID THIS TWICE!!
'  objEngFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Beginning Autoguiding at (x,y)=(" &_
'    objCam.GuideStarX & "," & objCam.GuideStarY & ")")
'  RestartGuider = False
'  objCam.Asynchronous = 1
'  objCam.AutoGuide

  objCam.Autoguider = 0

End Sub


