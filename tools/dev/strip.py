# strip.py out.png a.png b.png ... : side-by-side, half size
import sys
from PIL import Image
ims=[Image.open(f) for f in sys.argv[2:]]
ims=[i.resize((i.width//2,i.height//2)) for i in ims]
m=Image.new('RGB',(sum(i.width+4 for i in ims),max(i.height for i in ims)))
x=0
for i in ims: m.paste(i,(x,0)); x+=i.width+4
m.save(sys.argv[1])
