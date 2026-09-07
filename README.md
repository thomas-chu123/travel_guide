# Tokyo Event Map

東京 23 區的展覽、景點與活動地圖導覽服務。技術方向及產品邊界記錄於 [PLAN.MD](./PLAN.MD)。

## 第一階段：架構設置

目前建立的骨架包含：

- `frontend/`：React + TypeScript + Vite 的使用者介面與未來 `/admin` 共用入口。
- `backend/app/`：FastAPI 公開 API 骨架、版本化 router、health check 與設定管理。
- `backend/worker/`：獨立同步 worker 的程序入口；來源抓取工作會在第三階段加入。
- `compose.yaml`：本機容器開發環境。資料庫預設為本機 SQLite；Valhalla、SearXNG 與 Ollama 均透過環境變數接入，不在本專案內自動啟動。

## 本機啟動

1. 複製設定檔：`cp .env.example .env`
2. 後端：`cd backend && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/uvicorn app.main:app --reload`
3. 前端：`cd frontend && npm install && npm run dev`
4. 開啟 `http://localhost:5173`，API health check 為 `http://localhost:8000/api/v1/health`。

Docker 可用時，改以 `docker compose up --build` 啟動。

### 一鍵開發部署測試

在專案根目錄執行：

```bash
./scripts/dev-deploy.sh
```

腳本會建立缺少的 `.env` 與 Python virtual environment、安裝相依、執行 SQLite migration、寫入可重複執行的東京示範活動，然後在 localhost 啟動 API 與前端。按 `Ctrl+C` 會停止兩個程序。若不想建立示範資料，使用 `./scripts/dev-deploy.sh --no-seed`。

開發模式未設定 `VITE_MAP_STYLE_URL` 時，前端會使用國土地理院最適化 vector tiles 的標準樣式。該樣式以 PMTiles 提供，前端已註冊 PMTiles protocol，且 MapLibre 會顯示其必要 attribution。正式環境應評估流量與利用規約後，改用受管理或自有的 PMTiles/CDN style URL。

## 設定原則

- `.env` 只存在本機或部署平台，絕不提交。
- 預設 `DATABASE_URL=sqlite:///./data/tokyo_event_map.db`。未來改用 PostgreSQL/PostGIS 時，只更換連線字串與 spatial repository 實作。
- Google Places 內容將在下一階段以按需 proxy 方式取得，不落地保存。
- 正式底圖使用自管或商用的 PMTiles/CDN；不要使用公開 OSM tile server 作為正式服務底圖。

### Supabase REST 管理 API

後端可透過 Supabase REST API 操作指定資料表，前端不會接觸 Supabase secret key。設定
`SUPABASE_ADMIN_TOKEN` 與 `SUPABASE_ALLOWED_TABLES` 後，使用
`X-Supabase-Admin-Token` 呼叫 `/api/v1/supabase`：

- `GET /health`：驗證 REST API 連線。
- `GET /{table}`：讀取資料，可使用 PostgREST 篩選參數，例如 `?id=eq.1`。
- `POST /{table}`：新增一筆或多筆資料。
- `PATCH /{table}?id=eq.1`：更新符合篩選條件的資料。
- `DELETE /{table}?id=eq.1`：刪除符合篩選條件的資料。

更新與刪除沒有篩選條件時會被拒絕；未列入 `SUPABASE_ALLOWED_TABLES` 的表也無法操作。
