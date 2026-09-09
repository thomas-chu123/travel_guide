export type Locale = "zh-TW" | "ja" | "en";

export const localeOptions: { value: Locale; label: string }[] = [
  { value: "zh-TW", label: "中文" },
  { value: "ja", label: "日本語" },
  { value: "en", label: "English" },
];

export const messages = {
  "zh-TW": {
    explore: "探索東京", title: "目前地圖中的景點", mapTitle: "東京景點地圖", openMenu: "開啟景點選單", closeMenu: "關閉選單", language: "顯示語言",
    categories: { art: "美術館/展覽館", park: "公園", temple_shrine: "寺廟/神社", all: "全部景點" }, filters: { current: "現有展覽", future: "未來展覽", all: "所有展覽" },
    dateFilter: "展覽日期篩選", categoryFilter: "景點類別篩選", records: "筆", url: "URL", officialSite: "官方網站", price: "金額", period: "展期", hours: "營業時間", reviews: "評論", mapsReviews: "在 Google Maps 查看評論 ↗",
    noPrice: "金額未提供", noPeriod: "展期未提供", noHours: "營業時間未提供", noDescription: "暫無景點說明。", emptyPrefix: "目前地圖範圍內沒有", emptySuffix: "，請移動地圖或切換篩選條件。",
    place: "景點", location: "地點", description: "說明", exhibitions: "展覽資訊", exhibitionSite: "展覽網站 ↗", venue: "展覽場館", loading: "載入東京景點中…", apiUnavailable: "景點 API 尚未連線。請確認 backend 與 Supabase 設定。", mapLoadFailed: "底圖載入失敗", layerFailed: "景點圖層初始化失敗", clickHint: "個東京景點 · 點擊圖示查看資訊",
  },
  ja: {
    explore: "東京を探索", title: "現在の地図内のスポット", mapTitle: "東京スポットマップ", openMenu: "スポットメニューを開く", closeMenu: "メニューを閉じる", language: "表示言語",
    categories: { art: "美術館・展示施設", park: "公園", temple_shrine: "寺院・神社", all: "すべてのスポット" }, filters: { current: "開催中", future: "今後の展示", all: "すべての展示" },
    dateFilter: "展示期間フィルター", categoryFilter: "スポットカテゴリーフィルター", records: "件", url: "URL", officialSite: "公式サイト", price: "料金", period: "会期", hours: "営業時間", reviews: "口コミ", mapsReviews: "Google Mapsで口コミを見る ↗",
    noPrice: "料金情報なし", noPeriod: "会期情報なし", noHours: "営業時間情報なし", noDescription: "スポットの説明はありません。", emptyPrefix: "現在の地図範囲に", emptySuffix: "はありません。地図を移動するか、フィルターを変更してください。",
    place: "スポット", location: "場所", description: "説明", exhibitions: "展示情報", exhibitionSite: "展示公式サイト ↗", venue: "展示会場", loading: "東京のスポットを読み込み中…", apiUnavailable: "スポットAPIに接続できません。backendとSupabaseの設定を確認してください。", mapLoadFailed: "ベースマップの読み込みに失敗しました", layerFailed: "スポットレイヤーの初期化に失敗しました", clickHint: "件の東京スポット · アイコンをクリックして詳細を表示",
  },
  en: {
    explore: "EXPLORE TOKYO", title: "Places in the current map", mapTitle: "Tokyo Places Map", openMenu: "Open places menu", closeMenu: "Close menu", language: "Display language",
    categories: { art: "Museums / Exhibitions", park: "Parks", temple_shrine: "Temples / Shrines", all: "All places" }, filters: { current: "Now showing", future: "Upcoming", all: "All exhibitions" },
    dateFilter: "Exhibition date filter", categoryFilter: "Place category filter", records: "items", url: "URL", officialSite: "Official website", price: "Price", period: "Dates", hours: "Hours", reviews: "Reviews", mapsReviews: "View reviews on Google Maps ↗",
    noPrice: "Price unavailable", noPeriod: "Dates unavailable", noHours: "Hours unavailable", noDescription: "No description available.", emptyPrefix: "There are no ", emptySuffix: " in the current map area. Move the map or change the filters.",
    place: "Place", location: "Location", description: "Description", exhibitions: "Exhibitions", exhibitionSite: "Exhibition website ↗", venue: "Exhibition venue", loading: "Loading Tokyo places…", apiUnavailable: "The places API is unavailable. Check the backend and Supabase configuration.", mapLoadFailed: "Basemap failed to load", layerFailed: "Place layers failed to initialize", clickHint: "Tokyo places · click an icon for details",
  },
} as const;

export function languageTag(locale: Locale) { return locale === "zh-TW" ? "zh-TW" : locale === "ja" ? "ja-JP" : "en-US"; }
