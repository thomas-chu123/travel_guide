import { useEffect, useRef, useState } from "react";
import type { Feature, FeatureCollection, Point } from "geojson";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";
import museumIconUrl from "../assets/museum-icon.png";
import parkIconUrl from "../assets/park-icon.png";
import templeShrineIconUrl from "../assets/temple-shrine-icon.png";
import type { PlaceCategory } from "../App";
import { languageTag, messages, type Locale } from "../i18n";

type Props = { id: string; venue_id: string; name_ja: string; name_en: string | null; name_zh?: string | null; category: string; area: string | null; address_ja?: string | null; address_en?: string | null; address_zh?: string | null; ward_city?: string | null; location_text: string | null; location_text_en?: string | null; location_text_zh?: string | null; official_url: string | null; price_min_jpy?: number | null; price_max_jpy?: number | null; price_note: string | null; price_note_en?: string | null; price_note_zh?: string | null; exhibition_starts_on: string | null; exhibition_ends_on: string | null; exhibition_period_note: string | null; exhibition_period_note_en?: string | null; exhibition_period_note_zh?: string | null; opening_hours?: string | null; opening_hours_en?: string | null; opening_hours_zh?: string | null; description_ja: string | null; description_en: string | null; description_zh?: string | null };
export type LocationFeature = Feature<Point, Props>;
type Collection = FeatureCollection<Point, Props> & { returned: number };
const api = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const configuredStyleUrl = import.meta.env.VITE_MAP_STYLE_URL;
const styleUrl = configuredStyleUrl || (import.meta.env.DEV ? "https://gsi-cyberjapan.github.io/optimal_bvmap/style/std.json" : undefined);
const blankStyle: StyleSpecification = { version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: { "background-color": "#e5edf2" } }] };
let registered = false;
const categoryLabels: Record<Locale, Record<string, string>> = {
  "zh-TW": { park: "公園", temple_shrine: "寺廟／神社", museum: "美術館／博物館", art_museum: "美術館", gallery: "畫廊", exhibition_space: "展覽空間", exhibition: "展覽", convention_center: "會展中心", zoo_aquarium: "動物園／水族館", food_shopping: "餐飲／購物", point_of_interest: "景點" },
  ja: { park: "公園", temple_shrine: "寺院・神社", museum: "美術館・博物館", art_museum: "美術館", gallery: "ギャラリー", exhibition_space: "展示施設", exhibition: "展示", convention_center: "コンベンションセンター", zoo_aquarium: "動物園・水族館", food_shopping: "飲食・ショッピング", point_of_interest: "スポット" },
  en: { park: "Park", temple_shrine: "Temple / Shrine", museum: "Museum", art_museum: "Art museum", gallery: "Gallery", exhibition_space: "Exhibition space", exhibition: "Exhibition", convention_center: "Convention center", zoo_aquarium: "Zoo / Aquarium", food_shopping: "Food / Shopping", point_of_interest: "Place" },
};
const genericPointFilter: maplibregl.FilterSpecification = ["!", ["in", ["get", "category"], ["literal", ["museum", "art_museum", "park", "temple_shrine"]]]];
const genericArtFilter: maplibregl.FilterSpecification = ["in", ["get", "category"], ["literal", ["gallery", "exhibition_space", "convention_center", "exhibition"]]];
const interactiveLayers = ["location-hit-areas", "museum-hit-areas", "park-hit-areas", "temple-shrine-hit-areas"];
const gsiPoiLayerIds = ["注記シンボル付き重なり", "注記シンボル付きソート順100以上", "注記シンボル付きソート順100未満"];

function hideBasemapPoiSymbols(map: MapLibreMap) {
  const hidden = gsiPoiLayerIds.filter((id) => map.getLayer(id));
  for (const id of hidden) map.setLayoutProperty(id, "visibility", "none");
  return hidden;
}

function applyCategoryVisibility(map: MapLibreMap, category: PlaceCategory) {
  if (!map.getLayer("location-points")) return;
  const artVisible = category === "all" || category === "art";
  const parkVisible = category === "all" || category === "park";
  const templeVisible = category === "all" || category === "temple_shrine";
  map.setFilter("location-points", category === "art" ? genericArtFilter : genericPointFilter);
  map.setFilter("location-hit-areas", category === "art" ? genericArtFilter : genericPointFilter);
  for (const layer of ["location-hit-areas", "location-points"]) map.setLayoutProperty(layer, "visibility", artVisible ? "visible" : "none");
  for (const layer of ["museum-hit-areas", "museum-points"]) map.setLayoutProperty(layer, "visibility", artVisible ? "visible" : "none");
  for (const layer of ["park-hit-areas", "park-points"]) map.setLayoutProperty(layer, "visibility", parkVisible ? "visible" : "none");
  for (const layer of ["temple-shrine-hit-areas", "temple-shrine-points"]) map.setLayoutProperty(layer, "visibility", templeVisible ? "visible" : "none");
}

function line(root: HTMLElement, label: string, value: string | null | undefined, className?: string) { if (value) { const p = document.createElement("p"), b = document.createElement("strong"); if (className) p.className = className; b.textContent = `${label}　`; p.append(b, value); root.append(p); } }
export function localizedName(item: LocationFeature, locale: Locale) { const p = item.properties; return locale === "zh-TW" ? p.name_ja || p.name_zh || p.name_en || "" : locale === "en" ? p.name_en || p.name_ja || p.name_zh || "" : p.name_ja || p.name_en || p.name_zh || ""; }
export function localizedDescription(item: LocationFeature, locale: Locale) { const p = item.properties; return locale === "zh-TW" ? p.description_zh || p.description_ja || p.description_en : locale === "en" ? p.description_en || p.description_ja || p.description_zh : p.description_ja || p.description_en || p.description_zh; }
export function localizedLocation(item: LocationFeature, locale: Locale) { const p = item.properties; if (p.category === "exhibition") return locale === "zh-TW" ? p.location_text || p.location_text_zh || p.location_text_en : locale === "en" ? p.location_text_en || p.location_text || p.location_text_zh : p.location_text || p.location_text_en || p.location_text_zh; return locale === "zh-TW" ? p.address_zh || p.location_text || p.address_ja || p.address_en || p.area : locale === "en" ? p.address_en || p.location_text || p.address_ja || p.address_zh || p.area : p.address_ja || p.location_text || p.address_en || p.address_zh || p.area; }
export function googleMapsReviewsUrl(p: Props) {
  const venueName = p.category === "exhibition" ? p.location_text || p.name_ja : p.name_ja;
  const query = [venueName, p.address_ja || p.ward_city || p.area].filter(Boolean).join(" ");
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`;
}
function googleMapsLink(p: Props, locale: Locale) { const a = document.createElement("a"); a.href = googleMapsReviewsUrl(p); a.target = "_blank"; a.rel = "noopener noreferrer"; a.textContent = messages[locale].mapsReviews; return a; }
function popup(item: LocationFeature, locale: Locale, includeGoogleMaps = false) { const p = item.properties, t = messages[locale], root = document.createElement("article"); root.className = "location-popup"; const h = document.createElement("h2"); h.textContent = localizedName(item, locale); root.append(h); const fallbackName = locale === "ja" ? p.name_en : p.name_ja; if (fallbackName && fallbackName !== h.textContent) { const secondary = document.createElement("p"); secondary.className = "location-popup-en"; secondary.textContent = fallbackName; root.append(secondary); } const meta = document.createElement("p"); meta.className = "location-popup-meta"; meta.textContent = `${categoryLabels[locale][p.category] ?? t.place}${p.area ? ` · ${p.area}` : ""}`; root.append(meta); line(root, t.location, localizedLocation(item, locale)); line(root, t.description, localizedDescription(item, locale), "popup-description"); const tag = languageTag(locale), minPrice = p.price_min_jpy, maxPrice = p.price_max_jpy, localizedPrice = locale === "zh-TW" ? p.price_note_zh : locale === "en" ? p.price_note_en : p.price_note; const price = localizedPrice || p.price_note || (typeof minPrice === "number" ? `¥${minPrice.toLocaleString(tag)}${typeof maxPrice === "number" && maxPrice !== minPrice ? `–¥${maxPrice.toLocaleString(tag)}` : ""}` : null); line(root, t.price, price); const localizedPeriod = locale === "zh-TW" ? p.exhibition_period_note_zh : locale === "en" ? p.exhibition_period_note_en : p.exhibition_period_note; line(root, t.period, localizedPeriod || p.exhibition_period_note || (p.exhibition_starts_on ? `${p.exhibition_starts_on}${p.exhibition_ends_on ? ` ～ ${p.exhibition_ends_on}` : ""}` : null)); if (p.official_url) { const a = document.createElement("a"); a.href = p.official_url; a.target = "_blank"; a.rel = "noreferrer"; a.textContent = t.exhibitionSite; root.append(a); } if (includeGoogleMaps) root.append(googleMapsLink(p, locale)); return root; }
function venueKey(feature: LocationFeature) { return feature.properties.venue_id || feature.properties.id; }
function venuePopup(items: LocationFeature[], locale: Locale) { const t = messages[locale], venue = items.find((item) => item.properties.category !== "exhibition"), exhibitions = items.filter((item) => item.properties.category === "exhibition").sort((a, b) => (a.properties.exhibition_starts_on ?? "").localeCompare(b.properties.exhibition_starts_on ?? "")), root = document.createElement("article"); root.className = "location-popup venue-popup"; if (venue) root.append(popup(venue, locale, true)); else if (exhibitions[0]) { const h = document.createElement("h2"); h.textContent = localizedLocation(exhibitions[0], locale) || t.venue; root.append(h, googleMapsLink(exhibitions[0].properties, locale)); } if (exhibitions.length) { const title = document.createElement("h3"); title.textContent = `${t.exhibitions}（${exhibitions.length.toLocaleString(languageTag(locale))}）`; root.append(title); const list = document.createElement("div"); list.className = "exhibition-list"; for (const exhibition of exhibitions) list.append(popup(exhibition, locale)); root.append(list); } return root; }

export function EventMap({ category, locale, onLocationsChange }: { category: PlaceCategory; locale: Locale; onLocationsChange: (items: LocationFeature[]) => void }) {
  const element = useRef<HTMLDivElement>(null), mapRef = useRef<MapLibreMap | null>(null);
  const featuresRef = useRef<LocationFeature[]>([]);
  const localeRef = useRef(locale), activePopupRef = useRef<maplibregl.Popup | null>(null), activeItemsRef = useRef<LocationFeature[] | null>(null);
  const categoryRef = useRef(category);
  categoryRef.current = category;
  localeRef.current = locale;
  const [status, setStatus] = useState<string>(messages[locale].loading), [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const logPrefix = "[EventMap]";
    const t = messages[localeRef.current];
    const startedAt = performance.now();
    const elapsed = () => `${Math.round(performance.now() - startedAt)}ms`;

    console.groupCollapsed(`${logPrefix} initialization`);
    console.info(`${logPrefix} environment`, {
      mode: import.meta.env.MODE,
      dev: import.meta.env.DEV,
      prod: import.meta.env.PROD,
      api,
      configuredStyleUrl,
      resolvedStyleUrl: styleUrl ?? "blankStyle",
      pageUrl: window.location.href,
      online: navigator.onLine,
      userAgent: navigator.userAgent,
    });
    console.info(`${logPrefix} browser support`, {
      webgl2: Boolean(document.createElement("canvas").getContext("webgl2")),
      devicePixelRatio: window.devicePixelRatio,
    });
    console.groupEnd();

    if (!element.current) {
      console.error(`${logPrefix} map container is unavailable`, { elapsed: elapsed() });
      return;
    }
    if (mapRef.current) {
      console.warn(`${logPrefix} skipped duplicate initialization`, { elapsed: elapsed() });
      return;
    }

    if (!registered) {
      const protocol = new Protocol();
      maplibregl.addProtocol("pmtiles", protocol.tile);
      registered = true;
      console.info(`${logPrefix} PMTiles protocol registered`, { elapsed: elapsed() });
    } else {
      console.info(`${logPrefix} PMTiles protocol was already registered`, { elapsed: elapsed() });
    }

    maplibregl.setWorkerUrl(maplibreWorkerUrl);
    console.info(`${logPrefix} MapLibre worker configured`, { elapsed: elapsed(), maplibreWorkerUrl });

    console.info(`${logPrefix} creating MapLibre map`, { elapsed: elapsed() });
    const map = new maplibregl.Map({
      container: element.current,
      style: styleUrl || blankStyle,
      center: [139.7671, 35.6812],
      zoom: 10,
      attributionControl: styleUrl ? {} : false,
      collectResourceTiming: true,
      transformRequest: (url, resourceType) => {
        console.debug(`${logPrefix} resource request`, {
          elapsed: elapsed(),
          resourceType,
          url,
        });
        return { url };
      },
    });
    const grouped = new Map<string, LocationFeature[]>();
    let allFeatures: LocationFeature[] = [];
    const updateVisibleExhibitions = () => {
      const bounds = map.getBounds();
      const visible = allFeatures.filter((feature) => bounds.contains(feature.geometry.coordinates as [number, number]));
      console.debug(`${logPrefix} visible exhibitions updated`, { elapsed: elapsed(), visible: visible.length, total: allFeatures.length });
      onLocationsChange(visible);
    };

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    map.on("style.load", () => console.info(`${logPrefix} event: style.load`, { elapsed: elapsed(), styleLoaded: map.isStyleLoaded() }));
    map.on("load", () => console.info(`${logPrefix} event: load`, { elapsed: elapsed(), loaded: map.loaded() }));
    map.on("idle", () => console.info(`${logPrefix} event: idle`, { elapsed: elapsed(), loaded: map.loaded() }));
    map.on("sourcedataloading", (event) => console.debug(`${logPrefix} event: sourcedataloading`, { elapsed: elapsed(), sourceId: event.sourceId, sourceDataType: event.sourceDataType }));
    map.on("sourcedata", (event) => console.debug(`${logPrefix} event: sourcedata`, { elapsed: elapsed(), sourceId: event.sourceId, sourceDataType: event.sourceDataType, isSourceLoaded: event.isSourceLoaded, resourceTiming: event.resourceTiming }));
    map.on("error", (event) => {
      const message = event.error?.message ?? "Unknown error";
      console.error(`${logPrefix} event: error`, { elapsed: elapsed(), message, error: event.error, event });
      setError(`${t.mapLoadFailed}: ${message}`);
    });

    map.on("load", async () => {
      console.info(`${logPrefix} configuring location layers`, { elapsed: elapsed() });
      try {
        const hiddenBasemapLayers = hideBasemapPoiSymbols(map);
        console.info(`${logPrefix} basemap POI symbols hidden`, { elapsed: elapsed(), hiddenBasemapLayers });
        map.addSource("locations", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.addLayer({ id: "location-hit-areas", type: "circle", source: "locations", filter: genericPointFilter, paint: { "circle-radius": 28, "circle-color": "rgba(0,0,0,0.001)", "circle-stroke-width": 0 } });
        map.addLayer({ id: "location-points", type: "circle", source: "locations", filter: genericPointFilter, paint: { "circle-color": ["match", ["get", "category"], "exhibition", "#2563eb", "food_shopping", "#e95d75", "#2563eb"], "circle-radius": 6, "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } });
        const museumFilter: maplibregl.FilterSpecification = ["any", ["==", "category", "museum"], ["==", "category", "art_museum"]];
        map.addLayer({ id: "museum-hit-areas", type: "circle", source: "locations", filter: museumFilter, paint: { "circle-radius": 28, "circle-color": "rgba(0,0,0,0.001)", "circle-stroke-width": 0 } });

        console.info(`${logPrefix} loading museum icon`, { elapsed: elapsed(), museumIconUrl });
        const museumImage = await map.loadImage(museumIconUrl);
        console.info(`${logPrefix} museum icon loaded`, { elapsed: elapsed(), width: museumImage.data.width, height: museumImage.data.height });
        map.addImage("museum-icon", museumImage.data);
        map.addLayer({ id: "museum-points", type: "symbol", source: "locations", filter: museumFilter, layout: { "icon-image": "museum-icon", "icon-size": 0.15, "icon-allow-overlap": true, "icon-ignore-placement": true } });

        for (const [name, url, itemCategory] of [["park", parkIconUrl, "park"], ["temple-shrine", templeShrineIconUrl, "temple_shrine"]] as const) {
          const image = await map.loadImage(url);
          map.addImage(`${name}-icon`, image.data);
          map.addLayer({ id: `${name}-hit-areas`, type: "circle", source: "locations", filter: ["==", "category", itemCategory], paint: { "circle-radius": 28, "circle-color": "rgba(0,0,0,0.001)", "circle-stroke-width": 0 } });
          map.addLayer({ id: `${name}-points`, type: "symbol", source: "locations", filter: ["==", "category", itemCategory], layout: { "icon-image": `${name}-icon`, "icon-size": 0.15, "icon-allow-overlap": true, "icon-ignore-placement": true } });
        }
        applyCategoryVisibility(map, categoryRef.current);

        const nearbyFeatures = (point: maplibregl.PointLike) => {
          const pixel = point as maplibregl.Point;
          const radius = 8;
          const rendered = map.queryRenderedFeatures(
            [[pixel.x - radius, pixel.y - radius], [pixel.x + radius, pixel.y + radius]],
            { layers: interactiveLayers },
          );
          const candidates = rendered.flatMap((feature) => (
            feature.geometry.type === "Point" && typeof feature.properties?.id === "string"
              ? [feature as unknown as LocationFeature]
              : []
          ));
          const unique = [...new Map(candidates.map((feature) => [feature.properties.id, feature])).values()];
          return unique.sort((a, b) => {
            const aPoint = map.project(a.geometry.coordinates as [number, number]);
            const bPoint = map.project(b.geometry.coordinates as [number, number]);
            return aPoint.dist(pixel) - bPoint.dist(pixel);
          });
        };
        let activeFeatureId: string | null = null;
        let activePopup: maplibregl.Popup | null = null;
        const showLocation = (feature: LocationFeature) => {
          const featureId = feature.properties.id;
          const groupKey = venueKey(feature);
          if (activeFeatureId === groupKey && activePopup?.isOpen()) return;
          const coordinates = feature.geometry.coordinates as [number, number];
          const items = grouped.get(groupKey) ?? [feature];
          activePopup?.remove();
          activeFeatureId = groupKey;
          activeItemsRef.current = items;
          activePopup = new maplibregl.Popup({ closeButton: true, maxWidth: "420px", offset: 22 })
            .setLngLat(coordinates)
            .setDOMContent(venuePopup(items, localeRef.current))
            .addTo(map);
          activePopupRef.current = activePopup;
          activePopup.on("close", () => {
            activeFeatureId = null;
            activePopup = null;
            activePopupRef.current = null;
            activeItemsRef.current = null;
          });
          console.debug(`${logPrefix} location shown`, { id: featureId, coordinates, groupedItems: items.length });
        };
        map.on("mousemove", (event) => {
          const feature = nearbyFeatures(event.point)[0];
          map.getCanvas().style.cursor = feature ? "pointer" : "";
          if (feature && event.originalEvent.buttons === 0) showLocation(feature);
        });
        map.on("click", (event) => {
          const feature = nearbyFeatures(event.point)[0];
          if (!feature) return;
          showLocation(feature);
        });
        map.on("moveend", updateVisibleExhibitions);
        console.info(`${logPrefix} location layers configured`, { elapsed: elapsed(), interactiveLayers });
      } catch (layerError) {
        console.error(`${logPrefix} failed to configure location layers`, { elapsed: elapsed(), error: layerError });
        setError(`${t.layerFailed}: ${layerError instanceof Error ? layerError.message : String(layerError)}`);
        return;
      }

      const locationsUrl = `${api}/locations`;
      console.info(`${logPrefix} fetching locations`, { elapsed: elapsed(), url: locationsUrl });
      try {
        const response = await fetch(locationsUrl);
        console.info(`${logPrefix} locations response`, {
          elapsed: elapsed(),
          url: response.url,
          status: response.status,
          statusText: response.statusText,
          contentType: response.headers.get("content-type"),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status} ${response.statusText}`);
        const data = await response.json() as Collection;
        if (!Array.isArray(data.features)) throw new Error("API response does not contain a features array");
        allFeatures = data.features;
        featuresRef.current = data.features;
        console.info(`${logPrefix} locations decoded`, { elapsed: elapsed(), returned: data.returned, features: data.features.length });
        for (const feature of data.features) {
          const key = venueKey(feature);
          grouped.set(key, [...(grouped.get(key) ?? []), feature]);
        }
        const source = map.getSource("locations") as GeoJSONSource | undefined;
        if (!source) throw new Error("locations GeoJSON source is unavailable");
        source.setData(data);
        console.info(`${logPrefix} locations applied to map`, { elapsed: elapsed(), coordinateGroups: grouped.size });
        updateVisibleExhibitions();
        setStatus(`${data.returned.toLocaleString(languageTag(localeRef.current))} ${messages[localeRef.current].clickHint}`);
      } catch (requestError) {
        console.error(`${logPrefix} locations request failed`, { elapsed: elapsed(), url: locationsUrl, error: requestError });
        setStatus(messages[localeRef.current].apiUnavailable);
      }
    });

    return () => {
      console.info(`${logPrefix} cleanup`, { elapsed: elapsed() });
      map.remove();
      mapRef.current = null;
      activePopupRef.current = null;
      activeItemsRef.current = null;
    };
  }, [onLocationsChange]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map?.getLayer("location-points")) return;
    applyCategoryVisibility(map, category);
    const bounds = map.getBounds();
    onLocationsChange(featuresRef.current.filter((feature) => bounds.contains(feature.geometry.coordinates as [number, number])));
  }, [category, onLocationsChange]);
  useEffect(() => {
    const t = messages[locale];
    const count = featuresRef.current.length;
    setStatus(count ? `${count.toLocaleString(languageTag(locale))} ${t.clickHint}` : t.loading);
    const popup = activePopupRef.current, items = activeItemsRef.current;
    if (popup?.isOpen() && items) popup.setDOMContent(venuePopup(items, locale));
  }, [locale]);
  return <div className="map-panel"><div ref={element} className="map-canvas" /><p className="map-status">{status}</p>{error && <p className="map-hint">{error}</p>}</div>;
}
