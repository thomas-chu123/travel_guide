# 東京活動地圖導覽

## 狀態與技術結論

- App 可行，最大風險是活動資料授權、去重與維護，不是地圖技術。
- 建議採用 `MapLibre GL JS + PMTiles + Valhalla`，優於 `Leaflet + 公開 OSM Tiles + 公開 Nominatim + OSRM` 的組合。
- 開源軟體本身可為 $0，但主機、儲存、CDN、資料更新和維運不會真正是零成本。

## 建議技術框架

| 能力 | 建議選擇 | 原因 |
|---|---|---|
| 前端 | React + TypeScript + Vite | 適合純 Web 地圖 App，建置簡單 |
| 地圖渲染 | MapLibre GL JS | WebGL、向量圖、平滑縮放、cluster 和大量互動圖層較適合本產品 |
| 地圖底圖 | 東京／日本 PMTiles，放置於 S3/R2 類物件儲存並經 CDN 提供 | 成本可預測、沒有公共 tile server 的流量限制 |
| 地圖資料 | OpenStreetMap | 可自由建立自有底圖，但必須保留 OSM attribution |
| 地理資料庫 | 本機 SQLite + SQLAlchemy | 開發期零外部依賴；以 repository 隔離資料庫差異，未來可切換 PostgreSQL/PostGIS |
| 路線引擎 | Valhalla | 支援 car、bike、foot、matrix、isochrone，未來可加入 GTFS transit |
| 地址搜尋 | MVP 不直接依賴公共 Nominatim | 改用站名／行政區／本站場館搜尋、瀏覽器定位與地圖選點 |
| 後端 | FastAPI + Pydantic + SQLAlchemy + Alembic | API、資料驗證、遷移及 provider proxy |
| 同步工作 | 獨立 Python worker + Supabase durable job table | 避免長時間抓取工作阻塞 Web API |
| 搜尋發現 | 自架 SearXNG | 只用於發現候選來源，不直接發布內容 |
| AI | 可選 Ollama | 只做欄位抽取、分類與重複建議 |
| 多語 UI | i18next JSON | `zh-TW` 預設，支援 `zh-CN`、`ja`、`en` |
| 管理後台 | React 同一專案的 `/admin` + Supabase Auth | 候選審核、編輯、合併與發布 |

### 為何選 MapLibre 而不是 Leaflet

Leaflet 適合簡單 raster 地圖和少量 marker，但本 App 需要大量活動點、cluster、動態樣式、縮放層級和多圖層互動。MapLibre 的 WebGL 向量渲染更適合，也較接近 Google Maps 的操作感。Protomaps 也建議需要完整互動向量圖層的新專案使用 MapLibre；其 Leaflet 向量方案已屬維護模式。[Protomaps 說明](https://docs.protomaps.com/pmtiles/leaflet)

仍建立 `MapProvider` abstraction，但只實作 MapLibre；不要同時維護 Leaflet，以免為尚未發生的切換增加成本。

### 為何使用 PMTiles

- 將東京或日本底圖打包為單一向量 tile archive。
- 瀏覽器以 HTTP Range Request 按需讀取。
- 可放置於物件儲存，不必維護傳統 tile server。
- MapLibre 可直接整合，適合低流量到中型公開服務。[PMTiles 文件](https://docs.protomaps.com/pmtiles/)
- 每月更新一次底圖即可；活動資料仍每晚更新。

不得把 `tile.openstreetmap.org` 當正式環境免費 CDN。OSM 公開 tile 服務沒有 SLA，禁止批次預取，過量使用可能被封鎖。[OSM Tile Policy](https://operations.osmfoundation.org/policies/tiles/)

### 為何建議 Valhalla 取代 OSRM

OSRM 對純道路路線與 matrix 很快，但原生只有 car、bike、foot。Valhalla 同樣支援這些模式，另有 matrix、isochrone 及以 OSM + GTFS 建立 multimodal transit 的能力，更符合未來加入東京大眾運輸的方向。[Valhalla API](https://valhalla.github.io/valhalla/api/)

MVP：

- 支援 walking、cycling、driving。
- 使用 matrix 批次判斷活動是否在 15／30／60 分鐘內。
- 正式環境自架東京／關東 routing graph。
- 路由資料每週重建。

第二階段：

- 取得授權清楚且涵蓋東京的 GTFS feeds。
- 驗證資料完整度後啟用 transit。
- 若東京 GTFS 不足，再評估日本商業交通 API。

路線功能仍透過 `RoutingProvider` 介面呼叫，以便必要時改回 OSRM 或接商業服務。

### 地理編碼策略

公共 Nominatim 不適合作為 App 的一般搜尋後端：最多每秒一次、禁止 client-side autocomplete，也限制定期批次查詢。[Nominatim Policy](https://operations.osmfoundation.org/policies/nominatim/)

MVP 不提供任意地址 autocomplete，改為：

- 搜尋本站已有的活動、場館和車站。
- 以東京 23 區、鄰近車站和地圖 viewport 篩選。
- 起點可用瀏覽器定位、車站選擇或地圖點選。
- 管理員可直接在地圖修正場館位置。
- 少量缺失座標可透過受控 batch geocoder 補齊並人工確認。

未來若確定需要任意地址搜尋，再選擇自架 Nominatim/Pelias 或商業 geocoding provider。

## 系統設計

```text
React Web / Admin
        │
        ▼
     FastAPI
   ┌────┼───────────────┐
   ▼    ▼               ▼
Local SQLite         Valhalla       Google Places
   ▲                                    │
   │                                    └─ 評論按需取得，不落地保存
Ingestion Worker
   ├─ 官方來源 adapters
   ├─ 自架 SearXNG
   └─ 可選 Ollama
```

- FastAPI 是唯一公開資料 API；前端不直接連接資料庫。
- 開發期以 SQLite 的經緯度 bounding-box 查詢活動；切換 PostgreSQL/PostGIS 時由 spatial repository 接手空間索引。
- Google Places、routing 和來源抓取均封裝為 provider adapter。
- 爬取與同步由 worker 執行，不在 FastAPI request lifecycle 中執行。
- MVP 由本機或部署平台排程器每晚 02:00 JST 啟動 worker；worker 以 job table 保存 retry、錯誤和執行紀錄。切換 PostgreSQL 後可採用 `FOR UPDATE SKIP LOCKED`。
- worker 暫時離線時工作不遺失，恢復後繼續處理。

## 資料模型與 API

核心資料表：

- `venues`：場館、自有名稱、地址、座標、行政區、最近車站、Google Place ID。
- `events`：分類、來源語言、原始內容、費用狀態及發布狀態。
- `event_occurrences`：開始／結束時間及多場次。
- `sources`、`source_records`、`sync_jobs`、`sync_runs`：來源、原始記錄、排程及同步結果。
- `offers`：供應商、價格、幣別和購票 URL；MVP 只支援人工連結。
- `audit_logs`：人工修改、合併、發布和拒絕紀錄。

公開 API：

- `GET /v1/events?bbox&from&to&categories&wards&fee&origin&travel_mode&max_minutes`
- `GET /v1/events/{id}`
- `GET /v1/venues/{id}`
- `GET /v1/venues/{id}/google-reviews`
- `GET /v1/routes?origin&destination&profile`
- `GET /v1/search?q&type&locale`

管理 API：

- 候選事件查詢、編輯、發布、拒絕及合併。
- 場館對應、座標修正和 Google Place ID 綁定。
- 資料來源與同步健康度查詢。
- 人工鎖定欄位不得被下次同步覆寫。

## 功能行為

- 日期提供今日、本週、本月與自訂範圍；全部以 `Asia/Tokyo` 解讀。
- 分類第一版固定為展覽、景點、活動。
- 費用區分免費、付費、未知，付費可保存最低／最高 JPY。
- 地圖低縮放使用 cluster；高縮放顯示 marker。
- 桌面 hover 顯示摘要，click 顯示完整詳情；行動版以 tap 操作。
- 「全部顯示活動卡片」只在 viewport 數量低於門檻時啟用。
- 路線服務失敗時仍顯示活動，只停用交通時間篩選。
- 活動內容保留來源語言；只有 UI 使用四語 JSON。
- UI 缺少翻譯 key 時回退繁體中文並記錄錯誤。

## 資料來源與 AI 邊界

- 首批選擇 5–10 個有穩定官方頁面、RSS、JSON、CSV 或開放資料的來源。
- 每個來源記錄授權、robots 規則、抓取頻率和 parser 版本。
- SearXNG 只找候選頁面，不代表取得重製或抓取授權。[SearXNG API](https://docs.searxng.org/dev/search_api)
- Ollama 輸出必須符合 Pydantic JSON Schema，且只能寫入 `candidate`。
- 日期、價格、場館等 AI 抽取結果必須附來源證據並由人工核准。
- 同步採 idempotent upsert；來源消失先標記 stale，不直接刪除。
- 去重 key 以來源 ID 優先，否則使用標準化場館、標題與日期 fingerprint。
- Klook／KKday 自動同步延至第二階段；MVP 不爬取平台頁面。

## Google 評論限制

- 只保存 Google Place ID，不保存評論正文、評分快照或作者資料。
- 開啟場館詳情時才透過 Places API 取得最多 5 則評論。
- 顯示作者、Google Maps 來源連結、必要 attribution 和評論排序說明。
- Google 內容在視覺上與本站活動內容分隔。
- 設定 API key restriction、每日 quota 和預算告警。
- Places API 內容有快取限制，評論也可能觸發較高費率 SKU。[Google Places 政策](https://developers.google.com/maps/documentation/places/web-service/policies)、[Google Maps 計價](https://developers.google.com/maps/billing-and-pricing/pricing)

## 五個工作階段

### 1. 架構設置（已完成）

- 建立 React + TypeScript + Vite、FastAPI、獨立 Python worker 與本機 SQLite 的 repository 骨架。
- 建立 `.env.example`、Dockerfile、Compose 設定、健康檢查、測試與本機啟動文件。
- 固定前端相依版本，保留 SQLite、PMTiles、Valhalla、SearXNG、Ollama 與 Google Places 的安全設定入口。

### 2. 初期架構開發（進行中）

- 兩週 proof of concept：MapLibre + 東京 PMTiles、5 個來源、Valhalla matrix、Google 評論。
- 建立 SQLite schema、migration、FastAPI 公開 API 與 provider interfaces；保留 PostgreSQL/PostGIS 升級路徑。
- 實作空資料的地圖畫面、API contract、地圖 marker 與 viewport 查詢。
- 已完成 SQLite 初始 migration、`GET /api/v1/events` GeoJSON contract 與 MapLibre 初始 viewport loading；下一步為 seed data、資料來源 provider interface 與活動詳情 API。

### 3. 項目開發

- 建立 ingestion worker、來源 adapters、同步紀錄和管理後台。
- 完成地圖、cluster、活動卡片及日期／類別／區域／費用篩選。
- 完成 walking／cycling／driving 交通時間篩選、四語 UI 與響應式介面。

### 4. 驗證

- 資料正確率、去重、時間邊界、Google attribution、RLS 與 secret 管理驗證。
- 自動測試、地圖查詢效能、同步失敗重試及負載測試。
- 封閉測試，目標為每日一千名使用者內的穩定運作。

### 5. 部署

- 部署 Web、API、worker、SQLite 備份策略與 PMTiles/CDN；資料量成長時執行 PostgreSQL/PostGIS migration。
- 設定夜間排程、監控、告警、備份、成本與 API quota。
- 公開發布後，第二階段評估 GTFS transit 和 Klook／KKday 正式合作 feed。

若 POC 找不到至少 5 個可合法且穩定同步的東京來源，暫停完整自動化，先以人工選輯活動驗證產品需求。

## 驗收條件

- 1,000 個 viewport 活動點仍可順暢縮放、cluster 與點選。
- 一般地圖查詢 p95 低於 500 ms。
- 今日／本週／本月、跨日、多場次和東京時區結果正確。
- 路由 matrix 可依 15／30／60 分鐘篩選，故障不影響基本地圖。
- 同步重跑不產生重複資料；人工鎖定內容不被覆寫。
- 抽樣發布資料正確率至少 95%，重複率低於 2%。
- SearXNG／Ollama 候選未經核准不出現在公開 API。
- Google 評論沒有落地保存，且 attribution 完整。
- 四種 locale 的 JSON key 完全一致。
- 管理 API、同步 endpoint、local database 權限邊界和 secrets 通過測試。

## 已確定的 MVP 邊界

- 範圍：東京 23 區。
- 規模：每日一千名使用者內。
- 地圖：MapLibre，保留 provider adapter。
- 底圖：OSM-derived PMTiles + object storage/CDN。
- 路線：Valhalla walking／cycling／driving；transit 第二階段。
- 資料：官方來源優先，所有候選人工審核。
- 多語：UI 四語，活動內容不翻譯。
- 後台：提供簡易管理介面。
- 票券平台：Klook／KKday 第二階段。
- Google 評論：按需取得、合規顯示、不保存。
