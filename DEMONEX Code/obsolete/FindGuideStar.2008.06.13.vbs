Sub FindGuideStar

  objCam.AutoGuider = 1
  objCam.SubFrame = 0

  'Bounds the area of the prospective guide stars
  Edge = 100
  MaxMag = 2.0
  MinFWHM = 0

  MaxX = objCam.WidthInPixels - Edge
  MinX = Edge
  MaxY = objCam.HeightInPixels - Edge
  MinY = Edge

  objCam.AutoSaveOn = 1
  objCam.AutoSavePrefix = "AutoGuider"
  objCam.AutoSavePath = datapath
  Set objImage = WScript.CreateObject("CCDSoft.Image")

  'Double exposure time until adequate signal, up to 51.2 seconds
  For i=0 to 10
    objCam.ExposureTime = 1*(2^i)
    objCam.AutoGuiderExposureTime = 1*(2^i)

    objGdrFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Taking Autoguiding acquisition image for " &_
      objCam.AutoGuiderExposureTime & " seconds")
    objCam.TakeImage

    objGdrFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Attaching to Image")
    objImage.AttachToActiveAutoGuider

    objGdrFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Determining coordinates of brightest star")
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

    objGdrFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Found " & NStars & " stars")

    'Make sure the guide star is bright enough and not near an edge
    If Nstars > 0 Then
      For j=0 to Nstars - 1
        If Magnitude(j) > maxMag Then
          Exit For
        Else        
          If X(j) < MaxX and x(j) > MinX and Y(j) < MaxY and Y(j) > MinY and FWHM(j) > MinFWHM Then
            Star = j
            Exit For
          Else           
            objGdrFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide Star Rejected; (x,y)=(" & X(j) & "," & Y(j) & "); FWHM=" & FWHM(j))
          End If
          
        End If
      Next
    End If

    'Found Good Guide Star
    If Star <> -1 Then 
      Exit For
    End If 
    objImage.Close

  Next

  If Star = -1 Then
    objGdrFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): No Guide Star Found; bad focus?")    
    objCam.GuideStarX = -1
    objCam.GuideStarY = -1    
    Exit Sub
  End If


  objCam.GuideStarX = X(Star)
  objCam.GuideStarY = Y(Star)
  objGdrFile.WriteLine("FindGuideStar (" & FormatDateTime(Now,3) & "): Guide star found at (x,y) = (" & X(Star) & "," & Y(Star) &_ 
    "); Magnitude = " & Magnitude(Star) & ", Class = " & objClass(Star) & ", FWHM = " & FWHM(Star) & ", MajorAxis = " & MajorAxis(Star) &_
    ", MinorAxis = " & MinorAxis(Star) & ", Theta = " & Theta(Star) & ", Ellipticity = " & Ellipticity(Star))

End Sub


