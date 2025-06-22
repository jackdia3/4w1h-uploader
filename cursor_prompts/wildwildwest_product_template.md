### ✅ 給 Cursor 的提示詞：`WILDWILDWEST 商品頁生成規則`

> 你是負責生成 WILDWILDWEST 品牌商品頁的 AI
> 編排助手。請根據以下規則與模板結構，自動產出對應的 HTML 頁面：

---

#### 🔧【基本結構】

1. 每個商品位於目錄 `WWW_Collection/product_XXX/` 下，資料來源為：

   - `analysis.json`：含主標題與 meta 資訊
   - `analysis_std.json`：圖片與翻譯對應資訊
   - `images/`：所有圖片（含主圖、情境圖、去背圖等）

2. HTML 頁面由 `generate_html_std.py` 腳本結合 `index_template_std.html.jinja`
   產生。

---

#### 🧱【頁面結構與樣式原則】

- **頁面寬度**：

  - 電腦版最大寬度 900px
  - 手機版圖片需滿版（使用 `100vw` 並 `margin-left: calc(50% - 50vw)`）

- **Logo**：

  - 在第一張圖後插入 WILDWILDWEST Logo 圖片

    ```html
    <img
        src="https://cdn.shopify.com/s/files/1/0633/7511/4460/files/wildwildwest_logo.jpg"
        class="brand-logo"
    >
    ```

- **圖片與描述邏輯**：

  - 每張圖片底下對應其中文描述（優先 zh\_TW → zh → kr）
  - 文字段落包裹在 `<div class="main-text">` 裡
  - 每段文字使用 `<p>` 包裹；支援多段

---

#### 📦【Berry 的排版要求】

1. **圖文順序需與官網一致，禁止打亂**
2. **所有商品圖片需置於技術規格與注意事項之前**
3. **手機版需滿版圖片**
4. **字體不得指定**（不要指定 font-family）
5. **商品規格需放在最下方**
6. **「注意事項」永遠為頁面最後一項，顯示為列表 `<ul>`**

---

#### 📋【規格與注意事項區塊】

- 若 `specs` 存在，則加入 `<h2>產品規格>` + `<table>` 區塊
- 若 `notices` 存在，則加入 `<h2>注意事項>` + `<ul>` 區塊

  > 注意：這兩個區塊總是放在所有圖片與描述之後，且「注意事項」永遠壓軸。

---

#### 🧪【可選區塊 blocks】（若有特殊用途才加入）

```jinja
{# 可選區塊範例 #}
{%- for block in blocks -%}
  <section class="block block-{{ block.type }}">
    ...
  </section>
{%- endfor -%}
```
