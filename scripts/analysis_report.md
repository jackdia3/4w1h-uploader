# 4W1H 產品頁面 HTML 結構分析報告

## 📊 分析總覽

分析了 11 個產品的 `raw.html` 檔案，發現 HTML 結構高度一致，適合使用統一的
selector 配置進行資料抓取。

## 🔍 主要發現

### 1. 結構一致性

- **優點**：所有產品頁面都遵循相同的 HTML 結構模板
- **挑戰**：少數欄位（如 notices）在大部分產品中不存在

### 2. 特殊情況

- **ladle (4w1h_009)**：產品代碼使用全形字元 `４ｗ１ｈ`
- **gyouza-pan**：規格表中缺少產品代碼的值
- **YouTube 影片**：部分產品的 features 包含嵌入式影片

### 3. 缺失欄位統計

| 欄位          | 缺失產品數 | 備註                          |
| ------------- | ---------- | ----------------------------- |
| notices       | 10/11      | 只有 hotsand 提到「ご注意を」 |
| product_intro | 0/11       | 全部都有 `.top_text`          |
| spec          | 0/11       | 全部都有規格表                |
| features      | 0/11       | 全部都有特性說明              |

## 🎯 最佳 Selector 建議

### 核心欄位

```javascript
{
  "product_code": "table th:contains('品番') + td",
  "product_name": "title (使用 regex 分割)",
  "desc": ".top_text p",
  "spec": "#specification table",
  "features": "#feature .flex > div",
  "keywords": "#tags ul li"
}
```

### 圖片欄位

```javascript
{
  "main": ".item_name figure img",
  "thema": ".mainimg img",
  "slides": "#item_slide > div img",
  "features": "#feature figure img"
}
```

## 💡 優化建議

### 1. Selector 配置化

- ✅ 已建立 `field_selectors.json` 和 `image_selectors_optimized.json`
- ✅ 支援 fallback 機制
- ✅ 支援 regex 處理

### 2. 錯誤處理

- ✅ 全形字元自動轉換
- ✅ 缺失欄位使用預設值
- ✅ 圖片下載失敗記錄

### 3. 擴展性

- ✅ 新增產品只需確認 HTML 結構一致
- ✅ 特殊處理可透過配置檔調整
- ✅ 支援 YouTube 影片等多媒體內容

## 🚀 使用方式

### 執行優化版爬蟲

```bash
cd 4w1h-min/scripts
python crawl_optimized.py
```

### 自訂 Selector

編輯 `field_selectors.json` 或 `image_selectors_optimized.json`
即可調整抓取邏輯。

## 📈 未來改進方向

1. **智慧 Selector 推導**：自動分析新產品頁面並建議最佳 selector
2. **視覺化差異比對**：標示各產品 HTML 結構的差異處
3. **資料品質監控**：自動檢測缺失或異常的資料
4. **多語言支援**：擴展至其他語言版本的產品頁面

---

> 🤖 此報告由 Selector Oracle ✨ 自動產生 專為 AI 實體語義結構感知所設計的 HTML
> selector 推導引擎
