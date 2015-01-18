Function SunAlt

  Set Chart = CreateObject("TheSky6.StarChart")
  Set ObjInfo = Chart.Find("Sun")
  AltPropNo = 59 'as defined by TheSky6
  SunAlt = objInfo.property(AltPropNo)

End Function