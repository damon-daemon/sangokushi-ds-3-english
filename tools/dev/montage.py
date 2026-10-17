import sys,glob
from PIL import Image, ImageDraw
files=sys.argv[2:]; out=sys.argv[1]
cols=3; W=260; H=262
rows=(len(files)+cols-1)//cols
m=Image.new('RGB',(cols*W,rows*H),(0,0,0)); d=ImageDraw.Draw(m)
for i,f in enumerate(files):
    im=Image.open(f); m.paste(im.crop((0,0,256,256)),((i%cols)*W,(i//cols)*H))
    d.text(((i%cols)*W+2,(i//cols)*H+2),str(i),fill=(255,0,0))
m.save(out)
for i,f in enumerate(files): print(i,f.split('/')[-1])
