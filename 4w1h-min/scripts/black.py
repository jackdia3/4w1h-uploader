import sys
from PIL import Image

if len(sys.argv) < 2:
    print("用法: python black.py <圖片路徑>")
    sys.exit(1)

img_path = sys.argv[1]
img = Image.open(img_path).convert("RGBA")

datas = img.getdata()
new_data = []
for item in datas:
    if item[3] == 0:
        new_data.append(item)
    else:
        new_data.append((0, 0, 0, item[3]))

img.putdata(new_data)
out_path = img_path.replace('.webp', '_black.webp')
img.save(out_path)
print("已產生黑色版本：", out_path)