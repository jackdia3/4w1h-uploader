# analysis.json 結構分析報告

## 偵測到的結構類型

### 結構類型 1

**蹤跡發現於以下產品:** product_321, product_383, product_516, product_630, product_907 (5 個)

```json
{
  "features": [
    [
      "str"
    ]
  ],
  "images": [
    {
      "alt": "str",
      "class": [],
      "generic_images": [],
      "id": "str",
      "is_main": "bool",
      "local_path": "str",
      "parent_class": [],
      "parent_id": "str",
      "parent_tag": "str",
      "selling_points": [],
      "spec_images": [],
      "src": "str",
      "use_cases": []
    }
  ],
  "meta_description": "str",
  "product_id": "str",
  "product_name": "str",
  "specs": [
    [
      {
        "label": "str",
        "value": "str"
      }
    ]
  ],
  "title": "str",
  "url": "str"
}
```

### 結構類型 2

**蹤跡發現於以下產品:** product_956, product_974 (2 個)

```json
{
  "features": [
    [
      "str"
    ]
  ],
  "images": [
    {
      "alt": "str",
      "class": [],
      "id": "str",
      "is_main": "bool",
      "local_path": "str",
      "parent_class": [],
      "parent_id": "str",
      "parent_tag": "str",
      "src": "str"
    }
  ],
  "meta_description": "str",
  "product_id": "str",
  "product_name": "str",
  "specs": [
    [
      {
        "label": "str",
        "value": "str"
      }
    ]
  ],
  "title": "str",
  "url": "str"
}
```

---

## 結構差異比較

### 頂層屬性 (Top-Level Keys)

**所有檔案中出現過的頂層屬性:** `features,images,meta_description,product_id,product_name,specs,title,url`


**結構類型 1** (用於 `product_321` 等 5 個產品):
  - **包含:** `features,images,meta_description,product_id,product_name,specs,title,url`

**結構類型 2** (用於 `product_956` 等 2 個產品):
  - **包含:** `features,images,meta_description,product_id,product_name,specs,title,url`

### `images` 陣列內物件的屬性 (Image-Level Keys)

**所有檔案中出現過的圖片層級屬性:** `alt,class,generic_images,id,is_main,local_path,parent_class,parent_id,parent_tag,selling_points,spec_images,src,use_cases`


**結構類型 1** (用於 `product_321` 等 5 個產品):
  - **包含:** `alt,class,generic_images,id,is_main,local_path,parent_class,parent_id,parent_tag,selling_points,spec_images,src,use_cases`

**結構類型 2** (用於 `product_956` 等 2 個產品):
  - **包含:** `alt,class,id,is_main,local_path,parent_class,parent_id,parent_tag,src`
  - **缺少:** `generic_images,selling_points,spec_images,use_cases`