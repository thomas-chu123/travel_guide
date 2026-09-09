import { useMemo, useState } from "react";
import { EventMap, googleMapsReviewsUrl, type LocationFeature } from "./components/EventMap";

type ExhibitionFilter = "current" | "future" | "all";
export type PlaceCategory = "art" | "park" | "temple_shrine" | "all";
const filterLabels: Record<ExhibitionFilter, string> = { current: "現有展覽", future: "未來展覽", all: "所有展覽" };
const categoryLabels: Record<PlaceCategory, string> = { art: "美術館/展覽館", park: "公園", temple_shrine: "寺廟/神社", all: "全部景點" };
const artCategories = new Set(["museum", "art_museum", "gallery", "exhibition_space", "convention_center", "exhibition"]);
const venueCollator = new Intl.Collator("ja", { sensitivity: "base", numeric: true });

function tokyoToday() {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date());
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}
function matchesFilter(item: LocationFeature, filter: ExhibitionFilter, today: string) {
  if (item.properties.category !== "exhibition") return true;
  const { exhibition_starts_on: starts, exhibition_ends_on: ends } = item.properties;
  if (filter === "all") return true;
  if (filter === "future") return Boolean(starts && starts > today);
  return (!starts || starts <= today) && (!ends || ends >= today);
}
function price(item: LocationFeature) { const p = item.properties, minPrice = p.price_min_jpy, maxPrice = p.price_max_jpy; return p.price_note || (typeof minPrice === "number" ? `¥${minPrice.toLocaleString("ja-JP")}${typeof maxPrice === "number" && maxPrice !== minPrice ? `–¥${maxPrice.toLocaleString("ja-JP")}` : ""}` : "金額未提供"); }
function period(item: LocationFeature) { const p = item.properties; return p.exhibition_period_note || (p.exhibition_starts_on ? `${p.exhibition_starts_on}${p.exhibition_ends_on ? ` ～ ${p.exhibition_ends_on}` : ""}` : "展期未提供"); }
function openingHours(item: LocationFeature) {
  if (item.properties.opening_hours) return item.properties.opening_hours;
  if (["park", "temple_shrine"].includes(item.properties.category)) return "9:00–17:00";
  return "營業時間未提供";
}

export function App() {
  const [items, setItems] = useState<LocationFeature[]>([]), [open, setOpen] = useState(false), [filter, setFilter] = useState<ExhibitionFilter>("current"), [category, setCategory] = useState<PlaceCategory>("all");
  const today = tokyoToday();
  const visibleItems = useMemo(() => items
    .filter((item) => category === "all" || (category === "art" ? artCategories.has(item.properties.category) : item.properties.category === category))
    .filter((item) => matchesFilter(item, filter, today))
    .sort((a, b) => {
      const venueOrder = venueCollator.compare(a.properties.location_text ?? "", b.properties.location_text ?? "");
      if (venueOrder !== 0) return venueOrder;
      const dateOrder = (a.properties.exhibition_starts_on ?? "").localeCompare(b.properties.exhibition_starts_on ?? "");
      return dateOrder || venueCollator.compare(a.properties.name_ja, b.properties.name_ja);
    }), [category, filter, items, today]);
  return <main className="map-shell">
    <section className="map-area"><EventMap category={category} onLocationsChange={setItems} /></section>
    <header className="map-header">
      <button className="menu-button" aria-label="開啟景點選單" aria-expanded={open} onClick={() => setOpen(!open)}>☰</button>
      <div><p>TOKYO WALKING MAP</p><strong>東京景點地圖</strong></div>
    </header>
    <aside className={open ? "drawer open" : "drawer"} aria-hidden={!open}>
      <div className="drawer-title">
        <div><p>探索東京</p><h1>目前地圖中的景點</h1></div>
        <button className="close-button" onClick={() => setOpen(false)} aria-label="關閉選單">×</button>
      </div>
      <section className="event-list">
        <div className="category-filters" role="group" aria-label="景點類別篩選">
          {(Object.keys(categoryLabels) as PlaceCategory[]).map((value) => <button key={value} className={category === value ? "selected" : ""} aria-pressed={category === value} onClick={() => setCategory(value)}>{categoryLabels[value]}</button>)}
        </div>
        {(category === "all" || category === "art") && <div className="exhibition-filters" role="group" aria-label="展覽日期篩選">
          {(Object.keys(filterLabels) as ExhibitionFilter[]).map((value) => <button key={value} className={filter === value ? "selected" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>{filterLabels[value]}</button>)}
        </div>}
        <div className="list-title"><h2>{categoryLabels[category]}</h2><span>{visibleItems.length.toLocaleString("ja-JP")} 筆</span></div>
        {visibleItems.length ? visibleItems.map((item) => <article className="exhibition-card" key={item.properties.id}>
          <h3>{item.properties.name_ja}</h3>
          <p className="exhibition-card-venue">{item.properties.location_text || item.properties.area || categoryLabels[category]}</p>
          <dl>
            {item.properties.official_url && <div><dt>URL</dt><dd><a href={item.properties.official_url} target="_blank" rel="noreferrer">官方網站</a></dd></div>}
            {item.properties.category === "exhibition" && <><div><dt>金額</dt><dd>{price(item)}</dd></div><div><dt>展期</dt><dd>{period(item)}</dd></div></>}
            <div><dt>營業時間</dt><dd>{openingHours(item)}</dd></div>
            <div><dt>評論</dt><dd><a href={googleMapsReviewsUrl(item.properties)} target="_blank" rel="noopener noreferrer">在 Google Maps 查看評論 ↗</a></dd></div>
          </dl>
          <p className="exhibition-card-description">{item.properties.description_ja || item.properties.description_en || "暫無景點說明。"}</p>
        </article>) : <p className="empty">目前地圖範圍內沒有{categoryLabels[category]}，請移動地圖或切換篩選條件。</p>}
      </section>
    </aside>
    {open && <button className="drawer-backdrop" aria-label="關閉選單" onClick={() => setOpen(false)} />}
  </main>;
}
