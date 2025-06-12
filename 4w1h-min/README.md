# 4W1H 產品頁面生成工具

## 📁 專案結構

```
4w1h-min/
├── products/           # 產品資料目錄
│   └── 4w1h_XXX/      # 各產品目錄
│       ├── config.json    # 產品配置檔
│       ├── images/        # 產品圖片
│       └── index.html     # 生成的產品頁面
├── scripts/           # 工具腳本
│   ├── black.py          # 圖片顏色轉換工具
│   ├── crawl.py          # 網頁爬蟲工具
│   ├── render_template.py # HTML 模板渲染工具
│   └── translate_config.py # 配置檔翻譯工具
└── 4w1h_images/      # 共用圖片資源
```

## 🛠️ 主要工具

### 1. 圖片處理工具

#### black.py

- 功能：將白色主題圖片轉換為黑色版本
- 使用方式：
  ```bash
  python black.py
  ```
- 處理邏輯：
  - 自動搜尋所有產品目錄下的 `thema.webp` 圖片
  - 檢測圖片是否主要為白色
  - 將白色圖片轉換為黑色版本
  - 原始白色版本會加上 `_white` 後綴

### 2. 網頁生成工具

#### render_template.py

- 功能：根據配置檔生成產品頁面
- 使用方式：
  ```bash
  python render_template.py <config.json> [output.html]
  ```
- 支援功能：
  - 多語言配置
  - YouTube 影片嵌入
  - 響應式設計
  - 自動 CDN 圖片轉換

### 3. 資料抓取工具

#### crawl.py

- 功能：從原始網頁抓取產品資料
- 使用方式：
  ```bash
  python crawl.py <url>
  ```
- 特點：
  - 自動處理全形字元
  - 支援多媒體內容
  - 錯誤處理機制
  - 配置化 selector

## 🔄 工作流程

1. 使用 `crawl.py` 抓取原始產品資料
2. 使用 `translate_config.py` 翻譯配置檔
3. 使用 `black.py` 處理主題圖片
4. 使用 `render_template.py` 生成產品頁面

## 📝 配置檔格式

```json
{
    "code": "產品代碼",
    "name": "產品名稱",
    "brand": "品牌名稱",
    "desc": "產品描述",
    "spec": [
        {
            "label": "規格項目",
            "value": "規格值"
        }
    ],
    "features": [
        {
            "title": "特點標題",
            "desc": "特點描述",
            "youtube": "YouTube 影片網址"
        }
    ]
}
```

## 🎯 未來計劃

1. 自動化測試機制
2. 多語言支援擴展
3. 圖片優化工具
4. 效能監控系統

## 📄 授權

本專案採用 MIT 授權條款。
