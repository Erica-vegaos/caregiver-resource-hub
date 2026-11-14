# 聽見你 Logo 素材 v1.0.0

日期：2026-11-14。依 Erica 核定 B2「雙向傾聽・溫柔接住」品牌板製作。

## 給 Claude 的接入說明

這次僅交付美術素材，未修改 templates、src、dist、資料、建置與部署設定。請由正在修改網站的工作分支決定接入時機。不要直接整份覆蓋網站，也不要以本分支的網站檔案覆寫目前修改。

所有新檔都位於 `assets/brand/hear-you-v1.0/`。可以只取此資料夾，或 cherry-pick 本次美術提交。尚未複製到 dist；網站建置流程若不會複製品牌目錄，接入時需增加相應複製規則。

| 檔案 | 用途 |
| --- | --- |
| hear-you-mark-v1.0.svg | 首選彩色獨立圖標，透明背景，真正向量路徑 |
| hear-you-horizontal-v1.0.svg | 圖標＋聽見你橫式組合，文字已轉路徑，無字型依賴 |
| hear-you-monochrome-v1.0.svg | 深綠單色；負空間分隔兩側形體 |
| hear-you-reversed-v1.0.svg | 白色反白，搭配深色底使用 |
| hear-you-app-icon-v1.0.svg | 米白圓角底應用圖示 |
| hear-you-mark-1160-v1.0.png | 透明 PNG 圖標，1160 × 1020 |
| hear-you-horizontal-1320-v1.0.png | 透明 PNG 橫式組合，1320 × 510 |
| hear-you-icon-{32,180,192,512}-v1.0.png | favicon、Apple touch、應用圖示尺寸 |
| hear-you-favicon-v1.0.ico | 16 / 32 px ICO |
| hear-you-preview-v1.0.{svg,png} | 彩色、橫式、單色、反白預覽；不是網站 Logo 檔 |

## 製作與使用

保留上方柔橙弧線、左右不對稱綠色承接造形與中央留白。正式 SVG 是依定案圖重新描繪的平面向量，不是原始設計檔的無損轉換；去除品牌板中的紙張紋理與漸層。PNG 全部從正式 SVG 輸出，確保尺寸間一致。

主色 `#1F5B3B`、鼠尾草綠 `#A8C09A`、柔橙 `#F5C58A`；交疊色 `#CBD9B7`、圖示底 `#FBF7F2`。橫式字標使用 Noto Serif CJK TC Bold 的字形輪廓；屬向量排版重建。Noto 字型採 SIL Open Font License 1.1，未附帶字型檔。

網頁顯示請維持原始長寬比，`height: auto`，不可拉伸、旋轉或任意改色。16–32 px 請用獨立圖示，避免三字橫式縮到無法閱讀。資訊性圖片使用 `alt="聽見你"`；若旁邊已有同樣名稱，裝飾性圖示使用空 alt。

## 版本差異與檢查

v1.0.0：首次交付核定 B2 美術素材。未改既有檔案，未將 Logo 接入正式站，未執行部署。

已以 Inkscape 實際輸出 SVG、檢查預覽與 PNG 尺寸、透明通道、SVG 可解析性；字標不含外部字型或連結。未跑網站功能測試，因本次只有新增獨立素材。

AI 重繪提示摘要：依核定 B2 大圖重繪單一透明底標誌，維持深綠左形、鼠尾草綠右形與底部交疊、分離的柔橙上弧；無文字、無品牌板、無陰影。使用內建 image generation；參考板與 AI 過程稿未提交。
