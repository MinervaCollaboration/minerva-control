
NFilters = 4
ReDim arrFlatFilters(NFilters)

arrFlatFilters(0) = 3
arrFlatFilters(1) = 2
arrFlatFilters(2) = 1
arrFlatFilters(3) = 0


msgbox("before " & arrFlatFilters(0) & " " & arrFlatFilters(1) & " " & arrFlatFilters(2) & " " & arrFlatFilters(3))
reversedarrFlatFilters = reverse(arrFlatFilters)
msgbox("after " & reversedarrFlatFilters(0) & " " & reversedarrFlatFilters(1) & " " & reversedarrFlatFilters(2)  & " " & reversedarrFlatFilters(3))

Function Reverse( myarray )

  Dim i, idxLast
  idxLast = UBound( myarray )
  redim ReversedArray(idxLast)

  For i = 0 To idxLast - 1
    ReversedArray(i) = myarray(idxLast - i - 1)
  Next

  Reverse = ReversedArray

End Function