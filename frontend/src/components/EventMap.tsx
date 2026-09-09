import { useEffect, useRef, useState } from "react";
import type { Feature, FeatureCollection, Point } from "geojson";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";
import museumIconUrl from "../assets/museum-icon.png";

type Props = { id: string; name_ja: string; name_en: string | null; category: string; area: string | null; location_text: string | null; official_url: string | null; price_min_jpy: number | null; price_max_jpy: number | null; price_note: string | null; exhibition_starts_on: string | null; exhibition_ends_on: string | null; exhibition_period_note: string | null; opening_hours?: string | null; description_ja: string | null; description_en: string | null };
export type LocationFeature = Feature<Point, Props>;
type Collection = FeatureCollection<Point, Props> & { returned: number };
const api = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const configuredStyleUrl = import.meta.env.VITE_MAP_STYLE_URL;
const styleUrl = configuredStyleUrl || (import.meta.env.DEV ? "https://gsi-cyberjapan.github.io/optimal_bvmap/style/std.json" : undefined);
const blankStyle: StyleSpecification = { version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: { "background-color": "#e5edf2" } }] };
let registered = false;
const categoryLabel: Record<string, string> = { park: "公園", temple_shrine: "寺社", museum: "美術館・博物館", art_museum: "美術館", gallery: "畫廊", exhibition_space: "展覽空間", exhibition: "展覽", convention_center: "會展中心", zoo_aquarium: "動物園・水族館", food_shopping: "餐飲・購物", point_of_interest: "景點" };

function line(root: HTMLElement, label: string, value: string | null, className?: string) { if (value) { const p = document.createElement("p"), b = document.createElement("strong"); if (className) p.className = className; b.textContent = `${label}　`; p.append(b, value); root.append(p); } }
function popup(p: Props) { const root = document.createElement("article"); root.className = "location-popup"; const h = document.createElement("h2"); h.textContent = p.name_ja; root.append(h); if (p.name_en) { const en = document.createElement("p"); en.className = "location-popup-en"; en.textContent = p.name_en; root.append(en); } const meta = document.createElement("p"); meta.className = "location-popup-meta"; meta.textContent = `${categoryLabel[p.category] ?? "景點"}${p.area ? ` · ${p.area}` : ""}`; root.append(meta); line(root, "地點", p.location_text); line(root, "說明", p.description_ja || p.description_en, "popup-description"); const price = p.price_note || (p.price_min_jpy !== null ? `¥${p.price_min_jpy.toLocaleString("ja-JP")}${p.price_max_jpy !== null && p.price_max_jpy !== p.price_min_jpy ? `–¥${p.price_max_jpy.toLocaleString("ja-JP")}` : ""}` : null); line(root, "價格", price); line(root, "展期", p.exhibition_period_note || (p.exhibition_starts_on ? `${p.exhibition_starts_on}${p.exhibition_ends_on ? ` ～ ${p.exhibition_ends_on}` : ""}` : null)); if (p.official_url) { const a = document.createElement("a"); a.href = p.official_url; a.target = "_blank"; a.rel = "noreferrer"; a.textContent = "展覽網站 ↗"; root.append(a); } return root; }
function coordinateKey(coordinates: number[]) { return coordinates.map((value) => value.toFixed(6)).join(","); }
function venuePopup(items: LocationFeature[]) { const venue = items.find((item) => item.properties.category !== "exhibition"); const exhibitions = items.filter((item) => item.properties.category === "exhibition").sort((a, b) => (a.properties.exhibition_starts_on ?? "").localeCompare(b.properties.exhibition_starts_on ?? "")); const root = document.createElement("article"); root.className = "location-popup venue-popup"; if (venue) root.append(popup(venue.properties)); else if (exhibitions[0]) { const h = document.createElement("h2"); h.textContent = exhibitions[0].properties.location_text || "展覽場館"; root.append(h); } if (exhibitions.length) { const title = document.createElement("h3"); title.textContent = `展覽資訊（${exhibitions.length}）`; root.append(title); const list = document.createElement("div"); list.className = "exhibition-list"; for (const exhibition of exhibitions) list.append(popup(exhibition.properties)); root.append(list); } return root; }

export function EventMap({ onLocationsChange }: { onLocationsChange: (items: LocationFeature[]) => void }) {
  const element = useRef<HTMLDivElement>(null), mapRef = useRef<MapLibreMap | null>(null);
  const [status, setStatus] = useState("載入東京景點中…"), [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const logPrefix = "[EventMap]";
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
    const handledClicks = new WeakSet<Event>();
    const updateVisibleExhibitions = () => {
      const bounds = map.getBounds();
      const visible = allFeatures.filter((feature) => feature.properties.category === "exhibition" && bounds.contains(feature.geometry.coordinates as [number, number]));
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
      const message = event.error?.message ?? "未知錯誤";
      console.error(`${logPrefix} event: error`, { elapsed: elapsed(), message, error: event.error, event });
      setError(`底圖載入失敗：${message}`);
    });

    map.on("load", async () => {
      console.info(`${logPrefix} configuring location layers`, { elapsed: elapsed() });
      try {
        map.addSource("locations", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
        map.addLayer({ id: "location-points", type: "circle", source: "locations", filter: ["all", ["!=", "category", "museum"], ["!=", "category", "art_museum"]], paint: { "circle-color": ["match", ["get", "category"], "park", "#159e84", "temple_shrine", "#8b5aa3", "exhibition", "#2563eb", "food_shopping", "#e95d75", "#2563eb"], "circle-radius": 6, "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } });
        const museumFilter: maplibregl.FilterSpecification = ["any", ["==", "category", "museum"], ["==", "category", "art_museum"]];
        map.addLayer({ id: "museum-hit-areas", type: "circle", source: "locations", filter: museumFilter, paint: { "circle-radius": 28, "circle-color": "rgba(0,0,0,0.01)", "circle-stroke-width": 0 } });

        console.info(`${logPrefix} loading museum icon`, { elapsed: elapsed(), museumIconUrl });
        const museumImage = await map.loadImage(museumIconUrl);
        console.info(`${logPrefix} museum icon loaded`, { elapsed: elapsed(), width: museumImage.data.width, height: museumImage.data.height });
        map.addImage("museum-icon", museumImage.data);
        map.addLayer({ id: "museum-points", type: "symbol", source: "locations", filter: museumFilter, layout: { "icon-image": "museum-icon", "icon-size": 0.15, "icon-allow-overlap": true, "icon-ignore-placement": true } });

        const interactiveLayers = ["location-points", "museum-hit-areas", "museum-points"];
        const openPopup = (event: maplibregl.MapLayerMouseEvent) => {
          if (handledClicks.has(event.originalEvent)) return;
          handledClicks.add(event.originalEvent);
          const feature = event.features?.[0] as LocationFeature | undefined;
          if (!feature) return;
          const coordinates = feature.geometry.coordinates as [number, number];
          const items = grouped.get(coordinateKey(coordinates)) ?? [feature];
          console.debug(`${logPrefix} location clicked`, { id: feature.id, coordinates, groupedItems: items.length });
          new maplibregl.Popup({ closeButton: true, maxWidth: "420px", offset: 22 }).setLngLat(coordinates).setDOMContent(venuePopup(items)).addTo(map);
        };
        for (const layer of interactiveLayers) {
          map.on("mouseenter", layer, () => { map.getCanvas().style.cursor = "pointer"; });
          map.on("mouseleave", layer, () => { map.getCanvas().style.cursor = ""; });
          map.on("click", layer, openPopup);
        }
        map.on("moveend", updateVisibleExhibitions);
        console.info(`${logPrefix} location layers configured`, { elapsed: elapsed(), interactiveLayers });
      } catch (layerError) {
        console.error(`${logPrefix} failed to configure location layers`, { elapsed: elapsed(), error: layerError });
        setError(`景點圖層初始化失敗：${layerError instanceof Error ? layerError.message : String(layerError)}`);
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
        console.info(`${logPrefix} locations decoded`, { elapsed: elapsed(), returned: data.returned, features: data.features.length });
        for (const feature of data.features) {
          const key = coordinateKey(feature.geometry.coordinates);
          grouped.set(key, [...(grouped.get(key) ?? []), feature]);
        }
        const source = map.getSource("locations") as GeoJSONSource | undefined;
        if (!source) throw new Error("locations GeoJSON source is unavailable");
        source.setData(data);
        console.info(`${logPrefix} locations applied to map`, { elapsed: elapsed(), coordinateGroups: grouped.size });
        updateVisibleExhibitions();
        setStatus(`${data.returned.toLocaleString("ja-JP")} 個東京景點 · 點擊圖示查看資訊`);
      } catch (requestError) {
        console.error(`${logPrefix} locations request failed`, { elapsed: elapsed(), url: locationsUrl, error: requestError });
        setStatus("景點 API 尚未連線。請確認 backend 與 Supabase 設定。");
      }
    });

    return () => {
      console.info(`${logPrefix} cleanup`, { elapsed: elapsed() });
      map.remove();
      mapRef.current = null;
    };
  }, [onLocationsChange]);
  return <div className="map-panel"><div ref={element} className="map-canvas" /><p className="map-status">{status}</p>{error && <p className="map-hint">{error}</p>}</div>;
}
