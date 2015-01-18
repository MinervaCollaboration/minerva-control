Function Guide(raWant, decWant)

  Set objFile = objFSO.OpenTextFile("TalkToDevice.vbs", ForReading)
  Execute objFile.ReadAll()

  Call objTel.GetRaDec
  raNow = objTel.dRa
  decNow = objTel.dDec

  'Set Slew rate to guide
  Call TalkToDevice("#:RG#",Response,0,1)

  'if motion less than this (degrees), don't move
  MinOffset = 0.075/3600 'one tenth of a pixel

  Pi = 4*Atn(1)
  DecOffset = Abs(DecNow-DecWant)*60 'arcminutes
  RAOffset = Abs(RaNow-RaWant)*cos(DecNow*Pi/180)*900 'arcminutes

  If raNow > raWant and RAOffset > minOffset Then
    Call objTel.Jog(RAOffset,"West")
  ElseIf raNow < raWant Then
    Call objTel.Jog(RAOffset,"East")
  End If

  If decNow > decWant and DecOffset > minOffset Then
    Call objTel.Jog(DecOffset,"South")
  ElseIf decNow < decWant Then
    Call objTel.Jog(DecOffset,"North")
  End If

  'Set Slew rate back to normal
  Call TalkToDevice("#:RS#",Response,0,1) 

End Function

