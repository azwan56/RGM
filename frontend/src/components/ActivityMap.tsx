"use client";

import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";

// Decode Google's encoded polyline format
function decodePolyline(encoded: string): [number, number][] {
  const coords: [number, number][] = [];
  let idx = 0, lat = 0, lng = 0;
  while (idx < encoded.length) {
    let b, shift = 0, result = 0;
    do { b = encoded.charCodeAt(idx++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
    lat += result & 1 ? ~(result >> 1) : result >> 1;
    shift = result = 0;
    do { b = encoded.charCodeAt(idx++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 0x20);
    lng += result & 1 ? ~(result >> 1) : result >> 1;
    coords.push([lat / 1e5, lng / 1e5]);
  }
  return coords;
}

interface ActivityMapProps {
  polyline: string;
  height?: string;
}

export default function ActivityMap({ polyline, height = "350px" }: ActivityMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current || !polyline) return;
    let cancelled = false;

    import("leaflet").then((L) => {
      if (cancelled || !containerRef.current) return;

      // Clean up any previous instance first
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }

      // Guard against double-init (React StrictMode)
      const container = containerRef.current as any;
      if (container._leaflet_id) return;

      // Fix default marker icons
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "/leaflet/marker-icon-2x.png",
        iconUrl: "/leaflet/marker-icon.png",
        shadowUrl: "/leaflet/marker-shadow.png",
      });

      const coords = decodePolyline(polyline);
      if (coords.length === 0) return;

      const map = L.map(containerRef.current!, { zoomControl: true, attributionControl: false });
      mapRef.current = map;

      L.tileLayer("https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}", {
        maxZoom: 18,
        subdomains: ["1", "2", "3", "4"],
        attribution: "&copy; 高德地图",
      }).addTo(map);

      const line = L.polyline(coords, {
        color: "#FC4C02",
        weight: 4,
        opacity: 0.9,
        lineJoin: "round",
        lineCap: "round",
      }).addTo(map);

      L.circleMarker(coords[0], {
        radius: 8, fillColor: "#22c55e", color: "#fff", weight: 2, fillOpacity: 1,
      }).bindTooltip("Start", { permanent: false }).addTo(map);

      L.circleMarker(coords[coords.length - 1], {
        radius: 8, fillColor: "#ef4444", color: "#fff", weight: 2, fillOpacity: 1,
      }).bindTooltip("Finish", { permanent: false }).addTo(map);

      map.fitBounds(line.getBounds(), { padding: [24, 24] });
    });

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [polyline]);

  if (!polyline) {
    return (
      <div
        className="w-full rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-zinc-500 text-sm"
        style={{ height }}
      >
        No route data available
      </div>
    );
  }

  return (
    <>
      {/* Leaflet CSS */}
      <style>{`
        .leaflet-container { border-radius: 1rem; }
        .leaflet-control-zoom a { background: #1a1a1a !important; color: #fff !important; border-color: #333 !important; }
        .leaflet-control-zoom a:hover { background: #FC4C02 !important; }
      `}</style>
      <div ref={containerRef} style={{ height, width: "100%" }} className="rounded-2xl overflow-hidden border border-white/10" />
    </>
  );
}
