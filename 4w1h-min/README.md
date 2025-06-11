# 4W1H 產品頁面生成器

## 資料夾結構

```
4w1h-min/
├── products/                # 產生的產品頁面
│   ├── flat-kettle/        # 平底水壺
│   │   └── index.html      # 產生的靜態頁面
│   ├── flyer/             # 餃子鍋
│   │   └── index.html
│   └── hotsand/           # 熱壓吐司鍋
│       └── index.html
├── scripts/                # 腳本和模板
│   ├── generate_html.py    # 主要生成腳本，根據 config.json 產生靜態頁
│   ├── crawl.py            # 爬蟲腳本，自動抓取商品資料與圖片，產生 config.json
│   ├── translate_json_gpt.py # 多語系翻譯腳本，將 config.json 轉換為 config.zh.json
│   ├── black.py            # 批次處理圖片，將非透明像素轉為黑色
│   ├── resize.py           # 圖片尺寸調整腳本
│   ├── html.bat            # Windows 批次檔，批次產生多個商品頁
│   ├── index.html          # HTML 樣板，靜態頁產生的主模板
│   ├── config.json         # 範例商品設定檔
│   ├── image_selectors.json # 圖片選擇器設定，供爬蟲用
│   ├── temp/               # 參考用靜態頁（設計稿）
│   │   ├── flyer.html      # 餃子鍋參考頁面
│   │   └── hotsand.html    # 熱壓吐司鍋參考頁面
│   └── ... 其他備份或測試用檔案
└── README.md              # 本文件
```

## scripts/ 目錄說明與執行指令

| 檔案名稱                               | 執行指令                           | 功能說明                                                                |
| -------------------------------------- | ---------------------------------- | ----------------------------------------------------------------------- |
| generate_html.py                       | `python generate_html.py`          | 根據 config.json 產生靜態 HTML 頁面，結構與設計稿一致。                 |
| crawl.py                               | `python crawl.py`                  | 自動爬取 4w1h.jp 商品頁，下載圖片並產生結構化 config.json。             |
| translate_json_gpt.py                  | `python translate_json_gpt.py`     | 使用 GPT API 將 config.json 內容自動翻譯為多語系（如 config.zh.json）。 |
| black.py                               | `python black.py`                  | 批次處理圖片，將非透明像素轉為黑色，維持透明背景。                      |
| resize.py                              | `python resize.py`                 | 圖片尺寸調整工具，可批次縮放圖片。                                      |
| html.bat                               | `html.bat`（Windows 雙擊或命令列） | Windows 批次檔，依序對多個商品資料夾執行 HTML 產生與翻譯。              |
| index.html                             | -                                  | HTML 樣板，所有靜態頁的主結構模板。                                     |
| config.json                            | -                                  | 範例商品設定檔，供測試與參考。                                          |
| image_selectors.json                   | -                                  | 圖片選擇器設定，供爬蟲腳本自訂 CSS selector。                           |
| temp/                                  | -                                  | 參考用靜態頁（設計稿），如 flyer.html、hotsand.html。                   |
| index copy.html / index berry.html ... | -                                  | 備份或測試用的 HTML 樣板。                                              |

---

## 各腳本詳細說明

### generate_html.py

- **執行指令**：
  ```bash
  python generate_html.py
  ```
- **功能**：
  - 讀取 products/ 下每個商品的 config.json
  - 套用 scripts/index.html 樣板
  - 產生對應的靜態頁 index.html

### crawl.py

- **執行指令**：
  ```bash
  python crawl.py
  ```
- **功能**：
  - 自動爬取 4w1h.jp 商品頁
  - 下載所有商品圖片（自動轉 webp）
  - 產生結構化 config.json

### translate_json_gpt.py

- **執行指令**：
  ```bash
  python translate_json_gpt.py
  ```
- **功能**：
  - 讀取指定商品資料夾的 config.json
  - 使用 GPT API 自動翻譯內容，產生 config.zh.json

### black.py

- **執行指令**：
  ```bash
  python black.py
  ```
- **功能**：
  - 批次處理 images/webp 目錄下所有圖片
  - 將非透明像素轉為黑色，維持透明背景

### resize.py

- **執行指令**：
  ```bash
  python resize.py
  ```
- **功能**：
  - 批次調整 images/webp 目錄下所有圖片尺寸

### html.bat

- **執行方式**：
  - 直接在 Windows 檔案總管雙擊，或命令列執行：
    ```cmd
    html.bat
    ```
- **功能**：
  - 依序對多個商品資料夾執行 generate_html.py 與 translate_json_gpt.py

---

## 其他注意事項

1. 所有圖片路徑會自動加上 CDN 前綴
2. 支援 YouTube 影片嵌入
3. 支援多行文字（使用 `<br>` 分隔）
4. 所有區塊都有響應式設計
