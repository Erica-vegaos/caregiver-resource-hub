# 更新流程 MVP 計畫

版本：v0.1｜研究日期：2026-11-12（Asia/Taipei）

本文件全部是建議規格；本輪未建立程式、資料庫、Actions workflow、排程、網站或部署。來源與實驗事實見 [來源盤點](SOURCE_INVENTORY.md)，決策理由見 [可行性研究](AUTOMATED_UPDATES_FEASIBILITY.md)。

## 最小架構與儲存選擇

未來先用單一 Python 執行入口，手動 dry-run 通過後才評估 GitHub Actions 每日一次。正常 HTTP + HTML parser + schema/date 規則是核心；模型為可關閉的例外輔助。不要預設建立瀏覽器叢集、RAG、向量庫或 Agent 自主外部操作。

| 元件（未建立） | 建議責任 |
| --- | --- |
| 來源登錄檔 | 來源 ID、信任層級、列表/詳頁網址、允許 domain、格式、擷取規則版本、利用條件/robots 查核與日期、優先級、頻率、暫停原因 |
| Python 批次 | 來源檢查、候選發現、正文擷取、驗證、差異、例外清單、執行摘要 |
| 版本化 JSON | 每事件及場次的可讀主資料、來源映射、證據、待審與狀態；只在內容/狀態變動時改事件檔 |
| SQLite（可選） | 從 JSON 重建的查詢/去重索引；單寫入程序、交易提交，不與 JSON 競爭真相來源 |
| 執行健康紀錄 | 獨立簡短的最近成功心跳、失敗計數及例外指標，不拿整個 artifact 當唯一資料庫 |

JSON 優先的理由：少量資料容易 diff、回復與人工審核；SQLite 二進位提交不便審查且易衝突。若後續事件關聯複雜，可改 SQLite 為主並輸出 JSON，但需明確遷移，不雙向隨意寫。Actions runner 的工作目錄不能當永久資料；持久狀態需明確 commit／保存及下次載入，快取只能加速，不能當唯一儲存。

## 流程與失敗隔離

1. **來源登錄**：人工確認範圍、正常存取、利用條件、對象與列表入口。未確認的來源可研究取樣，不直接進正式自動發布白名單。
2. **定期檢查（未啟用）**：每日一次、錯開整點。先查列表，對新連結、變更內容與未來場次詳頁核對；未變列表不能免除既有詳頁取消檢查。遵守網站限制及 `Retry-After`，同站低併發，最多一次有限重試，不對 403/驗證頁反覆嘗試。
3. **擷取**：驗 HTTP、MIME、正文識別、驗證頁與最低內容完整性；比較原始及去噪正文 hash。支持時用 ETag/Last-Modified，但 304 只有在有效前次正文存在才算未變；不能刷新內容語意查核時間。
4. **標準化**：保留 raw 日期、對象、時間與費用，再建立 normalized 值；缺漏 null。只有模糊文字且資料完整到足以判定時才考慮模型候選抽取。
5. **去重**：先來源活動 ID，再 canonical URL／同主辦報名連結／時間場地；模糊相似只提出疑似重複，不能直接合併。
6. **驗證**：schema、日期順序、資格、地區、費用、場次拆分、欄位證據、跨來源矛盾、報名存活。權威原文與最新明確更正優先，仍有衝突就隔離。
7. **發布或待確認**：先寫候選及差異，所有門檻通過才進可顯示資料；未知報名狀態必須顯示未知，不自動變成可報名。
8. **過期與降級**：活動結束按本地時區自動歸檔；截止、取消、額滿分別處理；來源失敗只改健康／新鮮度，不能變取消。
9. **通知及健康檢查**：未來可用 Actions run summary + 一個更新式 issue／既有通知偏好，每來源每日合併一次，恢復後結案；本輪不建立。通知通道未設前不宣稱會收到告警。

單來源失敗不抹掉其他成功結果；新資料寫入採暫存驗證後原子替換，失敗保留最後已知版本。公開 repo 不放 secrets、參加者資料、原始完整 HTML/PDF 或外部頁面要求執行的文字。

**心跳限制**：程式內告警無法發現整個排程根本沒跑。每週人工核對最後成功時間，>48 小時無完整批次成功視為需要處理；若未來要無人發現排程停止，需另外評估獨立 watchdog，首版不擅自建立。也不要為避免停排而產生無意義假更新。

## 最小資料模型

`event` 是系列／活動，`occurrence` 是單一場次，`source_record` 是某來源的公告。所有 timestamp 用 ISO 8601 含時區；活動時區固定 `Asia/Taipei`，沒有時間只有日期時保留 date precision。未知不得寫成 false、0 或現在時間。

| 群組 | 最小欄位及要求 |
| --- | --- |
| 識別 | `schema_version`, `event_id`, `series_id`（可 null）, `occurrence_id`, `source_id`, `source_event_id`（無則 null）, `source_record_key`（無 ID 時 canonical URL 雜湊，標示 synthetic） |
| 來源 | `original_url`, `canonical_url`, `organizer`, `source_role`（original/repost）, `other_source_records[]`, `first_seen_at`, `source_published_at`（可 null）, `source_modified_at`（可 null） |
| 活動 | `title`, `activity_type`（lecture/support_group/activity/service）, `description_short`, `start`, `end`, `timezone`, `date_precision`, `date_raw`, `time_raw`, `session_rules_raw` |
| 地點與方式 | `mode`（onsite/online/hybrid/unknown）, `city`, `venue`, `address`, `online_platform`；線上不儲存非必要入場密碼／個人連結 |
| 資格 | `eligibility_raw`, `audience`（caregiver/public/professional/patient/mixed/unknown）, `caregiver_eligible`（true/false/null）, `geographic_requirement`, `priority_rules`, `screening_required`, `scope_match` 及理由 |
| 費用 | `fee_amount`（可 null）, `currency`（已明確才填）, `fee_raw`；缺費用不能當免費 |
| 報名 | `registration_method`（web/phone/email/walk_in/none/unknown）, `registration_url`, `public_contact`, `registration_open_at`, `registration_deadline`, `registration_status`, `registration_status_raw`, `registration_checked_at`, `link_health` |
| 分離狀態 | `event_status`, `publication_status`, `freshness_status`, `conflict_flags[]`, `review_reason[]`，不能用單一 status 混全部 |
| 擷取時間 | `last_attempt_at`, `last_successful_fetch_at`, `last_content_checked_at`, `last_human_reviewed_at`（可 null）, `last_successful_registration_check_at`（可 null）, `consecutive_failures` |
| 證據與版本 | `content_hash`, `parser_version`, `normalization_version`, `extraction_method`, `field_evidence[]`, `change_history[]`, `review_decision` |

`field_evidence` 最低結構：`field`, `value_raw`, `quote_short`, `source_url`, `locator`（HTML 區塊／PDF 頁碼及區域）, `observed_at`, `content_hash`, `method`。日期、時間、資格、費用、地點及報名狀態皆須對得回證據。**若缺證據則 normalized 值不得填出推測答案**；文字補全、模型自評高分都不能代替證據。

時間語意：成功擷取指已取得預期正文；最後內容查核指實際通過欄位／狀態檢查的時間；人工查核另欄。HTTP 200 挑戰頁不更新成功時間；304 可記檢查未變但不能假裝重新核實報名餘額。證據時間只能從實際執行紀錄產生，不事後捏造精確時分秒。

例：S03 的來源 id 是 205，S08 的來源 id 是 serno=22492。兩個 source_record 可連到同一候選 event，但起始日矛盾須保留，不能因標題同名自動生成已核准紀錄。S03 的 00:00 先保留 raw，服務時段 normalized 未知，不能推成全天服務。

## 日期、去重與變更規則

| 情境 | 規則與驗收結果 |
| --- | --- |
| 同活動跨站轉貼 | 建立來源映射；主辦、場次時間及報名入口等一致才精確合併。URL 去除追蹤參數，但保留 `id`、`ss`、`serno` 等語意參數；`reset` 是否可移除需逐站驗證 |
| 同名不同場次／跨年 | key 不只用標題；系列 + 年度 + 起始日時間 + 場地辨場次。2025/2026 不合併，無年日期不能套現在年 |
| 多場連續團體 | 同系列下多 occurrence；同一報名限制、是否可單場及是否須面談分開保留。不把剩一場等同接受中途加入 |
| 民國日期／跨年度 | 明確民國年加 1911；保留原值與轉換規則版本。無年日期只在同一活動明確年度上下文才繼承，跨年依明確資訊展開，否則待審；星期不符也待審 |
| 改期／場地變更 | 有同 source ID 或明確對應更正，保留 occurrence ID 及前值，新增版本；只有標題相似不自動認定改期。已核准重要欄位變更即撤回核准待審，對外降級提示 |
| 取消 | 原單位明確文字且能對到場次才標 cancelled；頁面 404、timeout 或空白不構成取消證據 |
| 截止／額滿／候補 | 有明確截止日且已過才 closed；有額滿／候補文字才 full/waitlist。截止日無時間以日期精度顯示，不捏造秒級截止；到截止當日若無時間，狀態標需向主辦確認，不承諾整天可報 |
| 報名連結失效 | 受限 domain 唯讀 GET、有界 redirect；404/失效表單記 unavailable，不能等同活動取消；登入牆記 restricted/unknown，不提交表單 |
| 頁面消失／失敗 | 保留最後已知值及成功時間，連續 2 次失敗提醒；>72h 無成功正文則 stale，移出可報名推薦區。7 天仍失敗暫停來源、保留歷史 |
| 缺漏／矛盾 | 資格、時間、地點、費用、報名方式缺少就 pending；不同來源不任意拼成完整資料。原單位新明確更正優先，轉貼較新不自動勝出 |
| 內容注入 | 所有外部文字是資料；禁止執行其中 shell/Agent 指令。抽取器無部署/寫檔/寄訊工具；白名單連結、防內網與本機 URL、禁止執行附件；模型 JSON 再經 schema/證據檢查 |

`event_status`: scheduled/rescheduled/cancelled/ended/unknown；`registration_status`: open/closed/full/waitlist/not_required/unknown；`publication_status`: candidate/pending/published/archived/excluded；`freshness_status`: fresh/stale/unavailable。狀態變動必留原因、證據及時間。

「open」表示在有效觀測中來源明確接受報名，**不是名額保證**；日期區間還沒過、頁面還在或按鈕可點，都不能單獨升為 open。活動結束歸檔不抹除曾 full/cancelled 的歷史；若新資料明確重新開放，保留先前狀態再更新。

## 自動發布門檻與人工責任

### 可自動發布（穩定後，需全部成立）

1. 來源在正式白名單，存取與利用條件完成查核，parser 通過該來源標註樣本及重跑驗收。
2. 日期時間、資格、地區／線上範圍、場地或平台、費用、報名方式有明確原文證據；原文未寫則不通過首版自動發布。
3. 活動未過期，規則計算無矛盾，沒有未解的去重／改期／OCR／跨來源衝突。
4. 非專業人員限定、非病友限定；混合對象需原文明確可含家屬。線上不限地區需明確證據，無法確認只列候選。
5. 本次抓到正文、抽取完整且內容查核距今 ≤48h。重要欄位變更尚待人工的紀錄不能繼續帶可靠推薦標籤。
6. 只有明確近期報名證據才列「原單位公告接受報名」；若其餘完整但名額不明，可自動發布為**資訊卡／報名狀態未知**，不得進「目前可報名」篩選。

首輪實驗全部候選仍人工對照，尚無來源取得上述正式白名單資格。是否使用模型不改變門檻；模型信心分數不參與核准。

### 必須人工確認

新來源／模板初次加入、圖片或 OCR 唯一證據、資格優先與硬限制模糊、費用缺漏、時間場地衝突、民國無年／星期不符、改期取消對應不明、疑似重複、表單狀態與官網不一致、原單位投稿但無法驗身分。收到取消資訊且無法查核時先移出可報名推薦，不捏造正式取消結論。

人工不能在缺資料時猜答案。聯繫未完成就保留 pending；本輪沒有授權代使用者對外發訊，因此沒有聯繫任何機構。

避免收集參加者個資：報名一律導回原單位，不保存姓名、病歷、家屬關係、身分證、出席名單或表單回覆。公開聯絡方式只保留報名所必要者；不複製私人手機、會議密碼與敏感留言。未來「回報錯誤」也只需活動連結與問題類型，不要求病況。

## 成本、限制與假設

查核日期均為 2026-11-12。以下官方價格為美元，不含稅與匯率；工時是研究估計，未實測。未採購、未申請付費服務。

| 項目 | 官方查證／設計判斷 |
| --- | --- |
| GitHub 標準 runner | [計費文件](https://docs.github.com/en/billing/concepts/product-billing/github-actions)：public repo 的 standard hosted runner 免費，larger runner 另計；目前本 repo GitHub 回報 public。若改 private，Free 包含 compute US$12/月，帳號其他工作共用，不能假設全額留給此專案 |
| 用量費率 | [runner 費率](https://docs.github.com/en/billing/reference/actions-runner-pricing)：Linux 2-core x64 US$0.006/分鐘，每 job 不足一分鐘向上取整。不能沿用未查證的舊分鐘價 |
| artifacts/cache | 同計費文件：Free artifact allowance 500MB、cache 每 repo 10GB；artifact 超額 US$0.25/GB/月、cache US$0.07/GB/月；artifact 與 Packages 共用。首版不依賴長期 artifact／cache 保存核心資料 |
| 排程 | [官方 schedule 說明](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)：可能延遲或丟棄，預設分支執行；public repo 60 天無活動會停用排程。預設 UTC，可選時區；本計畫日期以 Asia/Taipei，未建立 cron |
| Python/SQLite | [Python sqlite3](https://docs.python.org/3/library/sqlite3.html) 不需獨立資料庫 server；本地執行不需雲端 DB 訂閱；函式庫與主機仍須維護 |
| OCR | [Tesseract 官方](https://github.com/tesseract-ocr/tesseract) 為 Apache-2.0，本機無逐張 API 費；本輪繁中語言包缺失。雲端 OCR／商業瀏覽器／社群 API 沒選用，費率與可用性未確認，不編入免費方案 |
| 可選模型 | [GPT-5.4 mini 官方](https://developers.openai.com/api/docs/models/gpt-5.4-mini)：標準文字輸入 US$0.75/百萬 token、輸出 US$4.50/百萬 token，支持 structured outputs。僅作費用基準，未測本案抽取品質／帳號可用配額；不用搜尋工具或圖像輸入，不估其額外費 |

### 約 10 個來源、每日一次：月執行量

假設 30 天，每來源每天列表 1 次 + 最多 5 個未來詳頁核對，約 1,800 HTTP requests/月；每次批次含啟動 2–5 分鐘，共 60–150 runner 分鐘。這是估算，實際頁數、速度、內容變更率、timeout 與重試尚缺觀測。只抓 300 個列表頁不能代表 10 來源完整監控；所有未來詳頁太多時須調整成本或明列縮減覆蓋。

- 現 public 標準 runner：預估 compute **US$0/月**；不含超額儲存或額外服務。
- 若 private 且 included compute 已被其他工作用完：60–150 × 0.006 = **US$0.36–0.90/月**；未用完則可能落在額度內。不可只憑此 repo 使用量宣稱帳號帳單為零。
- JSON 假設 300 筆 × 平均 8KB ≈ 2.4MB 主資料；不長期存全文、海報與 PDF。Git 歷史增長和 logs 尚待量測；避免每日無變化全文快照。
- 無模型路徑：**US$0 模型費**。例外模型路徑假設每月 30–150 次，單次 4,000 輸入 + 800 計費輸出 token（關閉額外推理），每次 0.003 + 0.0036 = US$0.0066；合計 **US$0.198–0.99/月**。全量 1,800 次都呼叫則 US$11.88，且沒有必要。輸出增長、重試、隱含計費 token 或圖片會改變結果；只能以實際 usage 核帳。
- 建議未來設定程式硬上限：每月最多 150 次模型呼叫、超過即全送待確認，帳戶費用警示不是硬停付保證。本輪未設定任何預算或 key。

### 人工與建置工時（估計，不是承諾）

| 階段 | 工時假設 | 包含／不含 |
| --- | --- | --- |
| 2來源手動離線實驗 | 8–16 小時，1–2 個週末 | 標註、解析、差異、反例測試；不含網站、付費服務與正式排程 |
| 10來源穩定試營運準備 | 總計 30–60 小時 | 擴來源、失敗隔離、狀態與證據、存儲、品質驗收；反自動化來源若無替代則排除；不含等待機構回覆時間 |
| 初期每週人工 | 60–120 分鐘 | 新模板、新資格、矛盾、漏收與失敗排查；待 14 天實測 |
| 穩定且限來源 | 20–30 分鐘/週的目標 | 僅 2–4 穩定來源、每週 ≤4 例外及少量抽查，非 10 來源全涵蓋保證 |
| 一般 HTML 改版 | 每次額外 1–3 小時 | 修規則、核對回歸樣本；不包含在 30 分鐘預算 |
| 存取政策改變／複雜 PDF | 每次額外 2–8 小時，或停止支援 | 不能保證有解，優先切替代來源而非解驗證 |

每週 30 分鐘前提及放棄項目見 [可行性研究](AUTOMATED_UPDATES_FEASIBILITY.md)。若堅持 10 來源、每日完整、圖片／社群也收、可報名狀態即時可靠，**目前證據不支持此維護目標**。

替代方案：本機手動執行省去排程設定，但依賴經營者開機；單位提交資料可減解析成本，仍需驗證及更新責任；自架 n8n/VM 增常駐維護，託管 no-code 的價格與限制本輪未查證，沒有證據比單一批次更適合。除非量測證明 Actions 延遲或資料保存不合需求，不先換平台。

## 1–2 個週末的最小實驗與停止條件

### 週末一：2來源離線候選整理（8小時左右）

先取 S01、S05 正常公開正文及列表；補利用條件查核，仍有疑慮就只留研究結果、不公開發布。建立人工標註至少 20 筆事件／場次；不夠則記樣本不足，不能用重複抓同頁充數。含不同年份、連續場次、病友限定、專業限定、缺費用、改期、缺報名狀態等反例；人工合成反例須另標 synthetic，與真實來源指標分開。

產出未來可執行的 dry-run JSON 候選與差異報告，先不用模型、不建網站、不開排程。評估來源列表是否能發現新場次，及詳頁變更是否能被偵測；只抓固定樣本不是更新能力驗證。

**繼續條件**：真實樣本重要欄位完全正確的紀錄比例 ≥95%；核准候選 0 筆無證據補猜、0 筆將不適用資格誤放行；過期／缺費用／未知報名狀態均正確隔離。若少於 20 筆，只可判斷初步技術可行，不足以自動發布。

**停止／縮減**：來源要求禁止、需要繞存取限制、任一重要欄位出現無證據填值，立即停該來源自動核准；修正後用同組樣本再驗證。不是整個公益計畫失敗，可以轉低頻人工目錄。

### 週末二 + 14天觀察：差分與維護時間（額外4–8小時）

加入 S02 或 S08 的乾淨公開表格候選；尚未證明可取就先測，失敗保留失敗。S03/S08 日期衝突、S10 無文字 PDF、S07 200 驗證頁作隔離案例，不花時間解限制。兩週每日手動 dry-run，週末集中計時；重抓成功率以「正文及欄位有效」計，不能只計 200。

追蹤：有效來源日數／總來源日數、人工對照發現的合資格活動數、候選召回率、重要欄位正確率、無證據填值數、自動核准占比、每週例外件數、每件處理時間、整週總維護分鐘、每個來源修復工時。無新活動時召回率記 N/A，不能寫 100%。

**繼續條件（暫定產品門檻，非統計保證）**：連續 14 天有效抓取 ≥95%；人工可見範圍候選召回 ≥90%；已核准重要欄位錯誤 0；兩週各維護 ≤30 分鐘；至少找到 3 個實際未來且符合家屬資格的獨立場次。數量不足時先延長觀察或縮為服務資源目錄，不投入網站擴張。樣本小，95% 成功不等同長期 SLA。

**停止／調整**：兩週任一週超時先排除高例外來源；如果排除後剩餘活動無法帶來實際價值，就暫緩開發。若錯誤來自原單位缺欄位而非模型能力，增加模型不能解決，改提交／人工確認或不發布。只有達標後，下一輪才評估正式排程與入口呈現，本輪不啟用。

版本差異：v0.1 首次提出 schema、流程、狀態、安全邊界、成本與驗收計畫；全部為待實作規格。
