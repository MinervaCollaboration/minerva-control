pro plotcross

spawn, 'grep "Star found in" ~/minerva-control/log/n20200731/control_red.log', output

npoints = n_elements(output)
xpixel = dblarr(npoints)
ypixel = dblarr(npoints)
tip = dblarr(npoints)
tilt = dblarr(npoints)
for i=0L, npoints-1 do begin
   print, output[i]
   entries = strsplit(output[i],' ,',/extract)
   xpixel[i] = double(entries[11])
   ypixel[i] = double(entries[12])
   tip[i] = double(entries[15])
   tilt[i] = double(entries[16])
endfor

stop

end
