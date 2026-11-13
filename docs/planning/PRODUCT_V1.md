# 有伴產品規格 v1.0.0

確認日期：2026-11-14（Asia/Taipei）。使用者授權：全台、活動／支持團體／課程／講座、搜尋品質優先、自動更新為主且接受偶爾人工維護。

## 使用者任務
精神疾病患者之家屬／手足／伴侶／實際照顧者，找出近期自己能參加的活動。地域涵蓋全台與線上；全台搜尋能力不代表全台活動完整收錄。

## 範圍
延續有伴 v0.1 視覺。提供關鍵字、22縣市、線上／實體／混合、活動類型、日期與報名狀態篩選；台臺、全半形、疾病常見別名正規化；空結果提供清除條件與可查來源，不能塞無關活動或捏造。
不收個人病史及報名資料、不做診斷、不擴充成常設服務大全。本次把既有常設支持資料保留為次要入口。

## 資料合約（沿用既有欄位並加值）
`data/events.json` 為建置輸出；`templates/index.html` 的 `__DATA_JSON__` 由 `src/build.py` 內嵌。舊的 `data/manual_records.json` 保留。新增人工核對之全台活動放 `data/national_records.json`（結構 events/sources）；新增來源名錄放 `data/source_registry.json`（sources 陣列）。
活動沿用 id/source_id/title/organizer/source_url/start/end/city/mode/category/eligibility/caregiver_eligible/fee_amount/registration_status/event_status/checked_at/check_method/evidence/notes。city 採台北市等22縣市名稱，線上活動 city 可用「全台」但 mode 必須「線上」；混合為「混合」。不得根據舉辦地推定外縣市不符資格。
新增欄位可選：tags（文字陣列）、date_precision（date/time）、registration_url。不明費用為 null；不明名額為 unknown；不能把「額滿為止」當剩餘名額證據。
來源名錄至少 id/name/city/url/status/note；status 為 directory/discovery/manual/adapter/blocked 等可說明狀態。名錄不是活動，不能混入活動搜尋卡片。

## Agent 分工與檔案所有權
- 來源 Agent：data/national_records.json、data/source_registry.json、docs/research/NATIONAL_COVERAGE.md。以公開第一方證據為準；若無適合近期活動，保留缺口而非補假資料。
- 資料 Agent：src/build.py、tests/test_pipeline.py、新增資料測試。整合 national_records/source_registry；validate、去重、來源失敗保留舊資料、待審報告；新增發現不可信任自動發布。
- 搜尋前端 Agent：templates/index.html、src/search.cjs、tests/test_search.cjs。保留現有設計與互動，實現搜尋合約；不要寫 dist 或資料檔。
- 整合者：README、產品與交接文件、dist、GitHub、私人預覽與最終驗收。
- QA Agent：完成整合後獨立讀取及驗證，先提交 findings，修正由整合者協調。

## 驗收與限制
搜尋測試涵蓋台臺、躁鬱／雙相別名、多詞 AND、縣市和線上分離、日期、未知報名、取消與過期。資料測試涵蓋證據缺漏、日期不合法、重複、來源失敗。手機320/390px無橫向溢出；實測搜尋、篩選、詳細、空結果。
持續更新需另行建立及驗證運行環境；未實際啟用排程不得宣稱全天候自動更新。本次無付費服務與對外聯絡。

版本差異：由雙北研究原型調整為全台活動搜尋，加入來源覆蓋說明、搜尋別名與資料品質驗收。
