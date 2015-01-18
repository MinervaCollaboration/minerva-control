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
