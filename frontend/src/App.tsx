import { useMemo, useState } from "react";
import { EventMap, googleMapsReviewsUrl, localizedDescription, localizedLocation, localizedName, type LocationFeature } from "./components/EventMap";
import { languageTag, localeOptions, messages, type Locale } from "./i18n";

type ExhibitionFilter = "current" | "future" | "all";
export type PlaceCategory = "art" | "park" | "temple_shrine" | "all";
const artCategories = new Set(["museum", "art_museum", "gallery", "exhibition_space", "convention_center", "exhibition"]);

function initialLocale(): Locale {
  const saved = localStorage.getItem("tokyo-map-locale");
  return saved === "ja" || saved === "en" || saved === "zh-TW" ? saved : "ja";
}
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
function localizedField(p: LocationFeature["properties"], base: "opening_hours" | "price_note" | "exhibition_period_note", locale: Locale) {
  const suffix = locale === "zh-TW" ? "zh" : locale === "en" ? "en" : "";
  const localized = suffix ? p[`${base}_${suffix}` as keyof typeof p] : p[base];
  return (localized as string | null) || p[base];
}

export function App() {
  const [items, setItems] = useState<LocationFeature[]>([]), [open, setOpen] = useState(false), [filter, setFilter] = useState<ExhibitionFilter>("current"), [category, setCategory] = useState<PlaceCategory>("all"), [locale, setLocale] = useState<Locale>(initialLocale);
  const t = messages[locale], tag = languageTag(locale), today = tokyoToday();
  const categoryLabels = t.categories, filterLabels = t.filters;
  const selectLocale = (value: Locale) => { setLocale(value); localStorage.setItem("tokyo-map-locale", value); };
  const visibleItems = useMemo(() => {
    const collator = new Intl.Collator(tag, { sensitivity: "base", numeric: true });
    return items.filter((item) => category === "all" || (category === "art" ? artCategories.has(item.properties.category) : item.properties.category === category))
      .filter((item) => matchesFilter(item, filter, today))
      .sort((a, b) => collator.compare(localizedLocation(a, locale) ?? "", localizedLocation(b, locale) ?? "") || (a.properties.exhibition_starts_on ?? "").localeCompare(b.properties.exhibition_starts_on ?? "") || collator.compare(localizedName(a, locale), localizedName(b, locale)));
  }, [category, filter, items, locale, tag, today]);
  const price = (item: LocationFeature) => localizedField(item.properties, "price_note", locale) || (typeof item.properties.price_min_jpy === "number" ? `¥${item.properties.price_min_jpy.toLocaleString(tag)}${typeof item.properties.price_max_jpy === "number" && item.properties.price_max_jpy !== item.properties.price_min_jpy ? `–¥${item.properties.price_max_jpy.toLocaleString(tag)}` : ""}` : t.noPrice);
  const period = (item: LocationFeature) => localizedField(item.properties, "exhibition_period_note", locale) || (item.properties.exhibition_starts_on ? `${item.properties.exhibition_starts_on}${item.properties.exhibition_ends_on ? ` ～ ${item.properties.exhibition_ends_on}` : ""}` : t.noPeriod);
  const hours = (item: LocationFeature) => localizedField(item.properties, "opening_hours", locale) || (["park", "temple_shrine"].includes(item.properties.category) ? "9:00–17:00" : t.noHours);

  return <main className="map-shell" lang={locale}>
    <section className="map-area"><EventMap category={category} locale={locale} onLocationsChange={setItems} /></section>
    <header className="map-header"><button className="menu-button" aria-label={t.openMenu} aria-expanded={open} onClick={() => setOpen(!open)}>☰</button><div><p>TOKYO WALKING MAP</p><strong>{t.mapTitle}</strong></div></header>
    <aside className={open ? "drawer open" : "drawer"} aria-hidden={!open}>
      <div className="drawer-title"><div><div className="drawer-eyebrow"><p>{t.explore}</p><div className="language-switcher" role="group" aria-label={t.language}>{localeOptions.map((option) => <button key={option.value} className={locale === option.value ? "selected" : ""} aria-pressed={locale === option.value} onClick={() => selectLocale(option.value)}>{option.label}</button>)}</div></div><h1>{t.title}</h1></div><button className="close-button" onClick={() => setOpen(false)} aria-label={t.closeMenu}>×</button></div>
      <section className="event-list">
        <div className="category-filters" role="group" aria-label={t.categoryFilter}>{(Object.keys(categoryLabels) as PlaceCategory[]).map((value) => <button key={value} className={category === value ? "selected" : ""} aria-pressed={category === value} onClick={() => setCategory(value)}>{categoryLabels[value]}</button>)}</div>
        {(category === "all" || category === "art") && <div className="exhibition-filters" role="group" aria-label={t.dateFilter}>{(Object.keys(filterLabels) as ExhibitionFilter[]).map((value) => <button key={value} className={filter === value ? "selected" : ""} aria-pressed={filter === value} onClick={() => setFilter(value)}>{filterLabels[value]}</button>)}</div>}
        <div className="list-title"><h2>{categoryLabels[category]}</h2><span>{visibleItems.length.toLocaleString(tag)} {t.records}</span></div>
        {visibleItems.length ? visibleItems.map((item) => <article className="exhibition-card" key={item.properties.id}><h3>{localizedName(item, locale)}</h3><p className="exhibition-card-venue">{localizedLocation(item, locale) || categoryLabels[category]}</p><dl>{item.properties.official_url && <div><dt>{t.url}</dt><dd><a href={item.properties.official_url} target="_blank" rel="noreferrer">{t.officialSite}</a></dd></div>}{item.properties.category === "exhibition" && <><div><dt>{t.price}</dt><dd>{price(item)}</dd></div><div><dt>{t.period}</dt><dd>{period(item)}</dd></div></>}<div><dt>{t.hours}</dt><dd>{hours(item)}</dd></div><div><dt>{t.reviews}</dt><dd><a href={googleMapsReviewsUrl(item.properties)} target="_blank" rel="noopener noreferrer">{t.mapsReviews}</a></dd></div></dl><p className="exhibition-card-description">{localizedDescription(item, locale) || t.noDescription}</p></article>) : <p className="empty">{t.emptyPrefix}{categoryLabels[category]}{t.emptySuffix}</p>}
      </section>
    </aside>
    {open && <button className="drawer-backdrop" aria-label={t.closeMenu} onClick={() => setOpen(false)} />}
  </main>;
}
