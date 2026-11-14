# 聽見你｜NT$300 API 試跑 v0.1.0

2026-11-14。Erica 已授權先以每月 NT$300 試用 API。此版是一個獨立的活動文字抽取試跑模組，沒有改動網站、現有資料、分類、投稿入口或發布規則。Grok 保留為未來比較選項，這次不購買另一份訂閱。

## 依賴及範圍

- 新增 `src/ai_trial.py`：重用 build.fetch 的 HTTPS 來源白名單及大小／轉址限制、build.validate_eligibility、現有三個種子公告。
- 新增 `config/ai_trial.json`、`tests/test_ai_trial.py`、`.github/workflows/ai-trial.yml`。
- 持久狀態：獨立 `ai-trial-state` 分支的 `state.json`；只記請求 hash、預留費用、usage、模型、時間、狀態，不記金鑰或公告全文。不要刪除、回滾或重建這個分支，否則會破壞預算歷史。
- 暫無圖片 API／OCR、工具搜尋、任意投稿網址、每日排程、自動上架。先取得真實 API 測量結果後，再將通過驗證的抽取接上正規化及發布流程；不增加逐件人工核准。

## 預算如何停止

使用固定模型 `gpt-5.4-mini-2026-03-17`，標準文字輸入／輸出價格基準為每百萬 token US$0.75／US$4.50。2026-11-14 查官方文件；價格有效設定到 2026-12-14，過期先停用，不自行換模型。

官方文件：
- https://developers.openai.com/api/docs/models/gpt-5.4-mini
- https://developers.openai.com/api/reference/resources/responses/methods/create

每次最多 24,000 UTF-8 bytes 的來源文字、3,000 輸出 token；不偷偷截斷長頁面。將完整 JSON 請求 bytes 加 4,096 framing token 當保守輸入上界，加上最大輸出價格，按 **NT$45／US$1 的預算換算係數**向上取到分。這個係數含匯率／稅費緩衝，不是宣稱實際匯率。

每月按台灣時間累積預留額，下一筆會超過 NT$300 就不送。每次送 API **之前**，必須先成功 commit 並 push 預留額到持久狀態分支；推送失敗就不呼叫。並行 workflow 共用 concurrency group，git push 不 force、不自動重試，競爭者不能覆蓋別人的預扣紀錄。狀態遺失／格式錯誤立即停止，不從零開始。

成功、拒答、逾時、斷線都不退還預留額；實際 usage／美元估算另外記錄。工作取消或 crash 仍保留預扣，避免不確定是否已收費時重送。相同 URL＋文字 hash＋模型＋程式版本不再付費；來源變更才產生新請求。單次最多3筆，整個試跑最多20次付費請求；任何模型／API錯誤先停該批，不燒錢連續重試。

這是**本程式的保守成本控制**，不代表支付卡台幣帳單的絕對保證，也不涵蓋同一金鑰在其他程式的使用或 GitHub／Cloudflare 額外費用。請使用本專案專用 API project/key，避免混用。供應商若改價，需要重新核對並修正價格表。

## Erica 需要設定的唯一秘密

1. 在 OpenAI API Platform 啟用 API 計費，建立本專案專用 project/key。ChatGPT 訂閱不能當成這個 key。不要為本次試跑升級聊天訂閱；儲值最低額、稅費及是否需先購點以帳號當下畫面為準，不為湊最低額自動提高 NT$300 的授權。
2. GitHub → Erica-vegaos/caregiver-resource-hub → Settings → Secrets and variables → Actions → New repository secret。Name：`OPENAI_API_KEY`；Secret：貼入金鑰。
3. 完成後告知「金鑰已設定」即可；**不要把金鑰貼到聊天、Issue、程式碼或截圖**。GitHub connector 不具 secrets 寫入能力，這一步由帳號持有人設定。

https://platform.openai.com/api-keys
https://github.com/Erica-vegaos/caregiver-resource-hub/settings/secrets/actions

## 怎麼跑、怎麼判斷值不值得

GitHub Actions → **AI trial (NT$300 budget)** → Run workflow → main。預設勾選 dry_run，只檢查三個公開種子公告，無需 key、沒有模型費用。取消 dry_run 才真的送 API；成功持久預扣前不會送出。

結果下載 `hearyou-ai-trial-report`。每一欄是來源短引文，程式檢查引文確實存在，缺費用／名額保留 null。這只能驗證「引用存在」，不能證明語意完全正確，更不能當成自動上架驗收。輸出不寫入 `data/events.json`／`dist`。

第一批檢查：日期／年份、家屬與工作人員區別、多場次拆分、未知費用、引文是否指向正確場次；記錄每頁實際 token、費用、錯誤及未擷取原因。來源阻擋和解析故障與模型誤判分開記錄，不因抓不到頁就判定模型差。三個種子公告只驗證連線與初步可用性，不能宣稱全台／至少20個真實獨立案例已達95%正確率。

若結果差，先判斷瓶頸是來源、提示、正規化還是模型，再用同一組樣本比較其他 API。買 Grok 聊天訂閱是否能接入網站須另查產品能力；不能把換訂閱當成已修好自動更新。

## 版本差異及目前證據

v0.1.0：新增獨立 API 試跑、預留式預算、持久狀態、內容快取、短引文驗證、手動 workflow、失敗停批；現有正式站維持 v1.1.2。

自動測試使用合成文字與 mock API，不花 API 費用。未設定金鑰前不能宣稱已成功連線、已付費、已測得真實成本或抽取正確率。
