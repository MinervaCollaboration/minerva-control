  Set objMessage = CreateObject("CDO.Message")
  objMessage.Subject = "April Fools!"
  objMessage.From = """Calen Henderson"" <henderson@astronomy.ohio-state.edu>"
  objMessage.To = "tbeatty@astronomy.ohio-state.edu"
  objMessage.TextBody = "pwned! It wasn't Jason and Roberto... I just got them to agree to admit to it. It was me the whole time. God I am so good I just love myself sometimes." & VbCRLF & vbCRLF & "PS: I did the bubbles too."
  objMessage.Send