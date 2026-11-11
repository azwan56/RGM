import SwiftUI
import MapKit
import Charts

struct GpsTrackSheet: View {
    let activity: ActivityItem
    @Environment(\.presentationMode) var presentationMode
    
    @State private var trackResponse: ActivityTrackResponse?
    @State private var isLoading: Bool = true
    @State private var errorMessage: String?
    @State private var selectedTab: Int = 0 // 0: Route Map, 1: Elevation Profile
    @State private var isSatellite: Bool = false
    @State private var resetMapTrigger: UUID = UUID()
    
    // Elevation Scrubbing State
    @State private var scrubPoint: ElevationProfilePoint?
    
    var body: some View {
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()
                
                if isLoading {
                    VStack(spacing: 14) {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: Theme.primaryOrange))
                            .scaleEffect(1.3)
                        Text("正在拉取 GPS 轨迹并完成坐标纠偏...")
                            .font(.system(size: 13))
                            .foregroundColor(Theme.textMuted)
                    }
                } else if let err = errorMessage, trackResponse?.track?.points?.isEmpty != false {
                    VStack(spacing: 12) {
                        Text("⚠️")
                            .font(.system(size: 36))
                        Text(err)
                            .font(.system(size: 14))
                            .foregroundColor(Theme.textSecondary)
                        Text("该运动记录可能在室内进行，或手表未开启高精度 GPS 记录。")
                            .font(.system(size: 12))
                            .foregroundColor(Theme.textMuted)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 30)
                    }
                } else {
                    ScrollView {
                        VStack(spacing: 16) {
                            // 1. Hero Stats Row (Distance, Pace, HR, Elev)
                            heroStatsRow
                            
                            // 2. Tab Switcher (路线地图 vs 海拔剖面)
                            tabSwitcher
                            
                            // 3. Stage Content
                            if selectedTab == 0 {
                                routeMapStage
                            } else {
                                elevationChartStage
                            }
                            
                            // 4. Canova AI Coach Critique Card
                            if let critique = trackResponse?.activity?.ai_journal ?? activity.ai_journal, !critique.isEmpty {
                                coachCritiqueCard(critique: critique)
                            }
                            
                            // 5. Workout Key Metrics Detail Grid
                            workoutDetailsGrid
                        }
                        .padding(16)
                    }
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    VStack(spacing: 2) {
                        Text("🗺️ GPS 路线与高程")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(Theme.primaryOrange)
                        Text(activity.name)
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(Theme.textPrimary)
                            .lineLimit(1)
                    }
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        presentationMode.wrappedValue.dismiss()
                    }) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 20))
                            .foregroundColor(Theme.textMuted)
                    }
                }
            }
        }
        .task {
            await loadTrack()
        }
    }
    
    // MARK: - Load Track Data
    private func loadTrack() async {
        isLoading = true
        errorMessage = nil
        do {
            let res = try await APIService.shared.fetchActivityTrack(actId: activity.id)
            self.trackResponse = res
            if res.track?.points?.isEmpty != false && res.map_image_url == nil {
                self.errorMessage = "该运动未记录 GPS 轨迹"
            }
        } catch {
            self.errorMessage = "轨迹加载失败: \(error.localizedDescription)"
        }
        isLoading = false
    }
    
    // MARK: - Hero Stats Row
    private var heroStatsRow: some View {
        HStack {
            statItem(
                val: String(format: "%.2f", activity.distanceKm),
                unit: "km",
                lbl: "总距离",
                color: Theme.primaryOrange
            )
            Divider().frame(height: 28).background(Theme.border)
            statItem(
                val: activity.avg_pace_str ?? "--:--",
                unit: "",
                lbl: "平均配速",
                color: Theme.textPrimary
            )
            Divider().frame(height: 28).background(Theme.border)
            statItem(
                val: activity.average_heartrate != nil ? "\(activity.average_heartrate!)" : "--",
                unit: "bpm",
                lbl: "心率",
                color: Color(hex: "F43F5E")
            )
            Divider().frame(height: 28).background(Theme.border)
            let elevGain = activity.elevation_gain_meters ?? 0
            statItem(
                val: "+\(Int(elevGain))",
                unit: "m",
                lbl: "累计爬升",
                color: Theme.accentGreen
            )
        }
        .padding(.vertical, 12)
        .padding(.horizontal, 10)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private func statItem(val: String, unit: String, lbl: String, color: Color) -> some View {
        VStack(spacing: 2) {
            HStack(alignment: .lastTextBaseline, spacing: 1) {
                Text(val)
                    .font(.system(size: 18, weight: .bold, design: .rounded))
                    .foregroundColor(color)
                if !unit.isEmpty {
                    Text(unit)
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
            }
            Text(lbl)
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
        }
        .frame(maxWidth: .infinity)
    }
    
    // MARK: - Tab Switcher
    private var tabSwitcher: some View {
        HStack(spacing: 8) {
            tabButton(title: "🗺️ 轨迹路线", index: 0)
            
            let hasElev = trackResponse?.track?.elevation_profile?.isEmpty == false
            if hasElev {
                tabButton(title: "📈 海拔剖面", index: 1)
            }
            
            Spacer()
        }
    }
    
    private func tabButton(title: String, index: Int) -> some View {
        Button(action: {
            withAnimation(.easeInOut(duration: 0.2)) {
                selectedTab = index
            }
        }) {
            Text(title)
                .font(.system(size: 13, weight: selectedTab == index ? .bold : .medium))
                .foregroundColor(selectedTab == index ? Theme.onBrand : Theme.textMuted)
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(selectedTab == index ? Theme.brandFill : Theme.surfaceSecondary)
                .cornerRadius(20)
        }
    }
    
    // MARK: - Route Map Stage
    private var routeMapStage: some View {
        VStack(spacing: 8) {
            if let points = trackResponse?.track?.points, !points.isEmpty {
                ZStack(alignment: .topTrailing) {
                    NativeMapView(
                        points: points,
                        bounds: trackResponse?.track?.bounds,
                        isSatellite: isSatellite,
                        resetTrigger: resetMapTrigger
                    )
                    .frame(height: 320)
                    .cornerRadius(16)
                    
                    // Floating Map Controls
                    VStack(spacing: 8) {
                        // Fit Route
                        Button(action: {
                            resetMapTrigger = UUID()
                        }) {
                            VStack(spacing: 1) {
                                Text("🎯").font(.system(size: 14))
                                Text("全貌").font(.system(size: 9, weight: .bold)).foregroundColor(.white)
                            }
                            .frame(width: 44, height: 44)
                            .background(Color.black.opacity(0.75))
                            .clipShape(Circle())
                            .overlay(Circle().stroke(Color.white.opacity(0.2), lineWidth: 1))
                        }
                        
                        // Satellite Toggle
                        Button(action: {
                            isSatellite.toggle()
                        }) {
                            VStack(spacing: 1) {
                                Text(isSatellite ? "🛰️" : "🗺️").font(.system(size: 14))
                                Text(isSatellite ? "卫星" : "标准").font(.system(size: 9, weight: .bold)).foregroundColor(.white)
                            }
                            .frame(width: 44, height: 44)
                            .background(Color.black.opacity(0.75))
                            .clipShape(Circle())
                            .overlay(Circle().stroke(Color.white.opacity(0.2), lineWidth: 1))
                        }
                    }
                    .padding(12)
                }
                
                HStack {
                    Circle().fill(Theme.accentGreen).frame(width: 6, height: 6)
                    Text("GCJ-02 纠偏高精度轨迹 · 支持双指缩放、旋转与漫游")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                    Spacer()
                    if let count = trackResponse?.track?.total_points {
                        Text("\(count) 坐标点")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundColor(Theme.textMuted)
                    }
                }
                .padding(.horizontal, 4)
            } else if let imgUrl = trackResponse?.map_image_url, let url = URL(string: imgUrl) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let img):
                        img.resizable()
                            .aspectRatio(contentMode: .fit)
                            .frame(height: 280)
                            .cornerRadius(16)
                    default:
                        ProgressView()
                            .frame(height: 280)
                    }
                }
            } else {
                Text("暂无有效 GPS 轨迹数据")
                    .font(.system(size: 13))
                    .foregroundColor(Theme.textMuted)
                    .frame(height: 200)
            }
        }
    }
    
    // MARK: - Elevation Chart Stage
    private var elevationChartStage: some View {
        let elevPoints = trackResponse?.track?.elevation_profile ?? []
        let elevations = elevPoints.map { $0.elevation_m }
        let maxElev = elevations.max() ?? 0
        let minElev = elevations.min() ?? 0
        let elevGain = activity.elevation_gain_meters ?? 0
        
        return VStack(alignment: .leading, spacing: 12) {
            // Stat Header
            HStack(spacing: 12) {
                elevMetricPill(title: "最高海拔", val: "\(Int(maxElev)) m", color: Theme.primaryOrange)
                elevMetricPill(title: "最低海拔", val: "\(Int(minElev)) m", color: Theme.accentBlue)
                elevMetricPill(title: "累计爬升", val: "+\(Int(elevGain)) m", color: Theme.accentGreen)
            }
            
            // Scrubbing Reading Tip
            HStack {
                if let pt = scrubPoint {
                    Text("📍 里程: \(String(format: "%.2f", pt.dist_km)) km")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                    Text("⛰️ 海拔: \(Int(pt.elevation_m)) m")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    if let hr = pt.hr {
                        Text("❤️ \(hr) bpm")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundColor(Theme.accentRose)
                    }
                } else {
                    Text("👆 在图表上滑动可交互查看沿途里程与海拔")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                }
                Spacer()
            }
            .padding(.horizontal, 4)
            
            // Elevation Profile Chart
            if #available(iOS 16.0, *), !elevPoints.isEmpty {
                Chart {
                    ForEach(elevPoints) { pt in
                        AreaMark(
                            x: .value("距离 (km)", pt.dist_km),
                            yStart: .value("基准", max(0, minElev - 5)),
                            yEnd: .value("海拔 (m)", pt.elevation_m)
                        )
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Theme.primaryOrange.opacity(0.4), Theme.primaryOrange.opacity(0.05)],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                        
                        LineMark(
                            x: .value("距离 (km)", pt.dist_km),
                            y: .value("海拔 (m)", pt.elevation_m)
                        )
                        .foregroundStyle(Theme.primaryOrange)
                        .lineStyle(StrokeStyle(lineWidth: 2))
                    }
                    
                    if let scrub = scrubPoint {
                        RuleMark(x: .value("Scrub Distance", scrub.dist_km))
                            .foregroundStyle(Theme.textMuted.opacity(0.6))
                            .lineStyle(StrokeStyle(lineWidth: 1.5, dash: [4, 4]))
                        
                        PointMark(
                            x: .value("Scrub Distance", scrub.dist_km),
                            y: .value("Scrub Elev", scrub.elevation_m)
                        )
                        .foregroundStyle(Theme.textPrimary)
                        .symbolSize(40)
                    }
                }
                .chartXAxis {
                    AxisMarks(position: .bottom) { val in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [2, 2])).foregroundStyle(Theme.border)
                        AxisValueLabel() {
                            if let km = val.as(Double.self) {
                                Text("\(String(format: "%.1f", km))k")
                                    .font(.system(size: 10))
                                    .foregroundColor(Theme.textMuted)
                            }
                        }
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading) { val in
                        AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [2, 2])).foregroundStyle(Theme.border)
                        AxisValueLabel() {
                            if let m = val.as(Double.self) {
                                Text("\(Int(m))m")
                                    .font(.system(size: 10))
                                    .foregroundColor(Theme.textMuted)
                            }
                        }
                    }
                }
                .chartOverlay { proxy in
                    GeometryReader { geo in
                        Rectangle()
                            .fill(Color.clear)
                            .contentShape(Rectangle())
                            .gesture(
                                DragGesture(minimumDistance: 0)
                                    .onChanged { value in
                                        let currentX = value.location.x
                                        guard let dist: Double = proxy.value(atX: currentX) else { return }
                                        if let closest = elevPoints.min(by: { abs($0.dist_km - dist) < abs($1.dist_km - dist) }) {
                                            self.scrubPoint = closest
                                        }
                                    }
                                    .onEnded { _ in
                                        self.scrubPoint = nil
                                    }
                            )
                    }
                }
                .frame(height: 200)
                .padding(12)
                .background(Theme.surface)
                .cornerRadius(14)
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
            } else {
                Text("海拔数据载入中...")
                    .frame(height: 150)
            }
        }
    }
    
    private func elevMetricPill(title: String, val: String, color: Color) -> some View {
        VStack(spacing: 2) {
            Text(title)
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
            Text(val)
                .font(.system(size: 14, weight: .bold, design: .rounded))
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(Theme.surface)
        .cornerRadius(10)
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.border, lineWidth: 1))
    }
    
    // MARK: - Canova Coach Critique Card
    private func coachCritiqueCard(critique: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                Text("🤖").font(.system(size: 16))
                Text("Canova 教练专属复盘")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.primaryOrange)
            }
            Text(critique)
                .font(.system(size: 13))
                .foregroundColor(Theme.textSecondary)
                .lineSpacing(4)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(14)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    // MARK: - Workout Details Grid
    private var workoutDetailsGrid: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("📊 训练核心数据汇总")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(Theme.textPrimary)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                detailCell(lbl: "运动类型", val: activity.sport_type == "running" ? "户外跑步" : (activity.sport_type ?? "跑步"))
                detailCell(lbl: "打卡时间", val: formatDateTime(activity.start_time))
                detailCell(lbl: "运动耗时", val: activity.durationString)
                if let hr = activity.average_heartrate {
                    detailCell(lbl: "平均心率", val: "\(hr) bpm")
                }
                if let trimp = activity.trimp {
                    detailCell(lbl: "TRIMP 负荷", val: String(format: "%.1f", trimp))
                }
                if let pts = trackResponse?.track?.total_points {
                    detailCell(lbl: "GPS 记录点", val: "\(pts) 点")
                }
            }
        }
        .padding(14)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private func detailCell(lbl: String, val: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(lbl)
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
            Text(val)
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(Theme.textPrimary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(8)
        .background(Theme.surfaceSecondary)
        .cornerRadius(8)
    }
    
    private func formatDateTime(_ str: String?) -> String {
        guard let str = str, str.count >= 16 else { return str ?? "--" }
        let idx = str.index(str.startIndex, offsetBy: 16)
        return String(str[..<idx]).replacingOccurrences(of: "T", with: " ")
    }
}

// MARK: - Native MKMapView Wrapper (Robust, High Performance, iOS 16+)

struct NativeMapView: UIViewRepresentable {
    let points: [GpsTrackPoint]
    let bounds: TrackBounds?
    let isSatellite: Bool
    let resetTrigger: UUID
    
    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator
        mapView.isRotateEnabled = true
        mapView.isPitchEnabled = true
        mapView.showsCompass = true
        mapView.showsScale = true
        mapView.overrideUserInterfaceStyle = Theme.isLight ? .light : .dark
        
        setupRoute(on: mapView)
        return mapView
    }
    
    func updateUIView(_ uiView: MKMapView, context: Context) {
        uiView.overrideUserInterfaceStyle = Theme.isLight ? .light : .dark
        uiView.mapType = isSatellite ? .hybridFlyover : .standard
        
        if context.coordinator.lastResetTrigger != resetTrigger {
            context.coordinator.lastResetTrigger = resetTrigger
            zoomToFit(mapView: uiView, animated: true)
        }
    }
    
    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }
    
    private func setupRoute(on mapView: MKMapView) {
        guard !points.isEmpty else { return }
        
        // Remove existing overlays and annotations
        mapView.removeOverlays(mapView.overlays)
        mapView.removeAnnotations(mapView.annotations)
        
        var coords = points.map { CLLocationCoordinate2D(latitude: $0.latitude, longitude: $0.longitude) }
        let polyline = MKPolyline(coordinates: &coords, count: coords.count)
        mapView.addOverlay(polyline)
        
        // Start Annotation
        if let start = coords.first {
            let startAnn = RoutePointAnnotation(coordinate: start, title: "🟢 起点", isStart: true)
            mapView.addAnnotation(startAnn)
        }
        
        // End Annotation
        if let end = coords.last, coords.count > 1 {
            let endAnn = RoutePointAnnotation(coordinate: end, title: "🏁 终点", isStart: false)
            mapView.addAnnotation(endAnn)
        }
        
        zoomToFit(mapView: mapView, animated: false)
    }
    
    private func zoomToFit(mapView: MKMapView, animated: Bool) {
        guard !points.isEmpty else { return }
        
        if let b = bounds,
           let minLat = b.min_lat, let maxLat = b.max_lat,
           let minLon = b.min_lon, let maxLon = b.max_lon {
            let center = CLLocationCoordinate2D(latitude: (minLat + maxLat) / 2.0, longitude: (minLon + maxLon) / 2.0)
            let span = MKCoordinateSpan(latitudeDelta: max(abs(maxLat - minLat) * 1.35, 0.005),
                                        longitudeDelta: max(abs(maxLon - minLon) * 1.35, 0.005))
            let region = MKCoordinateRegion(center: center, span: span)
            mapView.setRegion(region, animated: animated)
        } else {
            // Fallback to overlay bounding map rect
            if let polyline = mapView.overlays.first as? MKPolyline {
                let rect = polyline.boundingMapRect
                mapView.setVisibleMapRect(rect, edgePadding: UIEdgeInsets(top: 40, left: 40, bottom: 40, right: 40), animated: animated)
            }
        }
    }
    
    class Coordinator: NSObject, MKMapViewDelegate {
        var parent: NativeMapView
        var lastResetTrigger: UUID
        
        init(_ parent: NativeMapView) {
            self.parent = parent
            self.lastResetTrigger = parent.resetTrigger
        }
        
        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let polyline = overlay as? MKPolyline {
                let renderer = MKPolylineRenderer(polyline: polyline)
                renderer.strokeColor = UIColor(red: 252/255, green: 76/255, blue: 2/255, alpha: 0.95) // Neon Strava/RGM Orange
                renderer.lineWidth = 4.5
                renderer.lineJoin = .round
                renderer.lineCap = .round
                return renderer
            }
            return MKOverlayRenderer(overlay: overlay)
        }
        
        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            guard let routeAnn = annotation as? RoutePointAnnotation else { return nil }
            let id = "RoutePointMarker"
            var view = mapView.dequeueReusableAnnotationView(withIdentifier: id)
            if view == nil {
                view = MKAnnotationView(annotation: routeAnn, reuseIdentifier: id)
                view?.canShowCallout = true
            } else {
                view?.annotation = routeAnn
            }
            
            // Custom pin rendering
            let label = UILabel()
            label.text = routeAnn.isStart ? "🟢" : "🏁"
            label.font = UIFont.systemFont(ofSize: 22)
            label.sizeToFit()
            view?.addSubview(label)
            view?.frame = label.frame
            
            return view
        }
    }
}

class RoutePointAnnotation: NSObject, MKAnnotation {
    let coordinate: CLLocationCoordinate2D
    let title: String?
    let isStart: Bool
    
    init(coordinate: CLLocationCoordinate2D, title: String?, isStart: Bool) {
        self.coordinate = coordinate
        self.title = title
        self.isStart = isStart
    }
}
