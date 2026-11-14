# 聽見你｜精神疾病家屬的資源與心事

版本：v1.1.4（社群活動補充、6 個來源列表探索）｜2026-11-14，Asia/Taipei

為精神疾病患者之家屬、手足、伴侶與實際照顧者整理全台活動、支持團體、課程與講座。免費資訊入口，報名回原單位；不蒐集病史、不代辦報名。

## 目前可以做什麼

- 支援22縣市、線上／實體／混合、活動類型、日期範圍與報名狀態。
- 搜尋支援台／臺、全半形與常見疾病別名，多詞須同時符合；相關度排序優先標題。
- 手機查活動、閱讀資格與原文證據、本機收藏、下載行事曆。
- 各地來源獨立於活動清單；無結果時誠實說明收錄缺口。
- 資料驗證、同場次去重、來源失敗保留最後有效資料、未確認候選隔離與人工待審報告。

目前快照22個場次，未來14場位於台北、新北、台中及線上；含第一筆明示思覺失調／躁鬱／重鬱的家屬課程（已截止報名）。26筆來源／缺口入口涵蓋22縣市，10縣市仍以全國官方名錄作入口。全台可搜尋不代表全台活動已完整收錄；尚無證據完整的近期專門家屬線上場次。費用與名額不明會保留未知，系列費用不當成單場費用。

## 開啟與驗證

直接開啟 `dist/index.html`，頁面內嵌樣式、資料與搜尋程式，可離線使用；原公告連結需網路。正式站：https://caring.ecp0.com （main 自動部署）。

```bash
python -m unittest discover -s tests -v
node --test tests/test_search.cjs
python src/build.py
```

需要更新原始資料時：

```bash
python src/build.py --refresh
```

不加 `--refresh` 只以既有快照重建，不發出網路請求。離線重建不會刷新任何原公告查核日期。自動解析器只支援臺北心衛中心與心生活；另有 `config/discovery_sources.json` 的 6 個協會列表頁，每日只產生待審候選（列在 `data/review.md`），不自動刊登。

## 更新與發布

- **Refresh**：每日 06:17（台北）自動抓取已設定來源、重建、跑測試，結果更新到同一個 PR「每日資料更新」。
- **發布**：合併該 PR 到 main，Cloudflare 自動部署已提交的 `dist/`。合併前看 `data/review.md`。
- **Validate**：每次 push／PR 跑測試並產出預覽。
- 無資料變動時重建不產生 diff（`built_at` 沿用）。

## 文件與檔案

- `docs/planning/PRODUCT_V1.md`：使用者已確認產品範圍、資料合約、Agent分工與驗收。
- `docs/research/NATIONAL_COVERAGE.md`：全台來源、查核證據與缺口。
- `docs/planning/OPERATIONS_V1.md`：偶爾人工維護的操作流程與自動營運剩餘工作。
- `docs/planning/LOW_TOKEN_AUTOMATION_V1.md`：日常0-LLM、分級抓取、到期下架、去重及部署串接方案（規劃，未啟用）。
- `docs/validation/V1_QA.md`：獨立驗收。
- `data/manual_records.json`：既有人工核對資料。
- `data/national_records.json`：全台新增人工核對活動。
- `data/source_registry.json`：來源名錄與缺口入口，不是活動。
- `data/review.md`：待確認項目與來源狀況。
- `CHANGELOG.md`：各版本差異。
- `docs/archive/`：v0.1 時期的規劃與研究，僅供追溯。

研究文件保留當時狀態，不視為本版即時資料。

API 試跑模組（v0.1.0，NT$300／月上限，不寫入公開活動）見 [API_TRIAL_V0_1.md](docs/planning/API_TRIAL_V0_1.md)。
