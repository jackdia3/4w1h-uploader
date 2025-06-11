# validate_html_structure.py

from bs4 import BeautifulSoup
import os

# 設定要檢查的基準順序
EXPECTED_SECTION_ORDER = ["why", "when", "who", "what", "how"]

# 輸入 HTML 路徑與範本比對名稱
TARGET_HTML = "./products/hotsand/index.html"


def extract_section_order(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    order = []
    for img in soup.select(".wh-block img"):
        src = img.get("src", "")
        for key in EXPECTED_SECTION_ORDER:
            if key in src:
                order.append(key)
                break
    return order


def compare_order(actual, expected):
    if actual == expected:
        print("✅ 頁面順序符合預期：", actual)
    else:
        print("⚠️ 頁面順序不一致！")
        print("實際順序：", actual)
        print("應有順序：", expected)


if __name__ == "__main__":
    if os.path.exists(TARGET_HTML):
        actual_order = extract_section_order(TARGET_HTML)
        compare_order(actual_order, EXPECTED_SECTION_ORDER)
    else:
        print(f"❌ 找不到檔案：{TARGET_HTML}")
