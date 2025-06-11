import os
from PIL import Image

TARGET_SIZE = (1000, 1000)
BG_COLOR = (0, 0, 0, 0)  # 黑色，若要不透明可用 (0,0,0,255)

def pad_to_square(img, size=TARGET_SIZE, bg_color=BG_COLOR):
    w, h = img.size
    new_img = Image.new("RGBA", size, bg_color)
    left = (size[0] - w) // 2
    top = (size[1] - h) // 2
    new_img.paste(img, (left, top), img if img.mode == "RGBA" else None)
    return new_img

def process_all_slides(products_dir="products"):
    for prod in os.listdir(products_dir):
        slide_dir = os.path.join(products_dir, prod, "images", "webp")
        if not os.path.isdir(slide_dir):
            continue
        for fname in os.listdir(slide_dir):
            if "_slide_" in fname and fname.endswith(".webp"):
                fpath = os.path.join(slide_dir, fname)
                img = Image.open(fpath)
                padded = pad_to_square(img)
                padded.save(fpath)
                print(f"處理完成: {fpath}")

if __name__ == "__main__":
    process_all_slides()