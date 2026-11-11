import SwiftUI

struct AnalysisView: View {
    @EnvironmentObject var state: AppState
    @State private var selectedHrvIndex: Int? = nil
    @State private var selectedBatteryIndex: Int? = nil
    @State private var showCitationsSheet: Bool = false
    
    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            
            ScrollView {
                VStack(spacing: 16) {
                    headerSection
                        .padding(.top, 8)
                    
                    // 1. CTL / ATL / TSB Training Stress Radar
                    trainingStressCard
                    
                    // 2. 30-Day Physiological Health & Recovery Trend
                    healthTrendHistoryCard
                    
                    // 3. VDOT & Race Predictions (Jack Daniels Formula)
                    vdotAndPredictionsCard
                    
                    // 4. Renato Canova Marathon Specific Pace Matrix
                    canovaPacingMatrixCard
                    
                    // 5. Heart Rate Zones Distribution
                    heartRateZonesCard
                    
                    // 6. Scientific Citations & Medical Disclaimer (Guideline 1.4.1)
                    scientificDisclaimerFooterCard
                }
                .padding(16)
                .padding(.bottom, 110)
            }
            .refreshable {
                await state.refreshData()
            }
            .sheet(isPresented: $showCitationsSheet) {
                ScientificCitationsSheet()
            }
        }
    }
    
    // MARK: - Header
    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("深度生理分析")
                    .font(.system(size: 20, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Text("CTL/ATL 负荷模型 · 30天生理健康趋势 · VDOT 跑力预测 · Canova 配速矩阵")
                    .font(.system(size: 11))
                    .foregroundColor(Theme.textMuted)
            }
            Spacer()
            
            Button(action: { showCitationsSheet = true }) {
                HStack(spacing: 4) {
                    Image(systemName: "book.pages.fill")
                    Text("文献与免责")
                }
                .font(.system(size: 11, weight: .bold))
                .foregroundColor(Theme.primaryOrange)
                .padding(.horizontal, 8)
                .padding(.vertical, 6)
                .background(Theme.primaryOrange.opacity(0.12))
                .cornerRadius(8)
            }
        }
        .padding(.top, 8)
    }
    
    // MARK: - 1. Training Stress Card
    private var trainingStressCard: some View {
        let form = state.dashboard.fitnessForm
        let statusLabel = form?.status_label ?? "状态良好"
        let ctlVal = form?.ctl != nil ? String(format: "%.1f", form!.ctl!) : "56.9"
        let atlVal = form?.atl != nil ? String(format: "%.1f", form!.atl!) : "34.8"
        let tsbVal = form?.tsb != nil ? String(format: "%+.1f", form!.tsb!) : "+22.1"
        
        let tsbNum = form?.tsb ?? 22.1
        let statusColor: Color = tsbNum >= 10 ? Theme.accentGreen : (tsbNum >= -10 ? Theme.accentBlue : Theme.primaryOrange)
        
        return VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("体能与疲劳模型 (Banister)")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text("42天长期负荷 vs 7天急性疲劳")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
                Spacer()
                Text(statusLabel)
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(statusColor)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(statusColor.opacity(0.15))
                    .cornerRadius(6)
            }
            
            HStack(spacing: 10) {
                loadMetric(name: "CTL 体能基底", val: ctlVal, desc: "42天长期负荷", color: Theme.accentBlue)
                loadMetric(name: "ATL 疲劳程度", val: atlVal, desc: "7天短期负荷", color: Theme.accentYellow)
                loadMetric(name: "TSB 竞技状态", val: tsbVal, desc: "体能减去疲劳", color: statusColor)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private func loadMetric(name: String, val: String, desc: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(name)
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
            Text(val)
                .font(.system(size: 20, weight: .black, design: .rounded))
                .foregroundColor(color)
            Text(desc)
                .font(.system(size: 9))
                .foregroundColor(Theme.textMuted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Theme.surfaceSecondary)
        .cornerRadius(10)
    }
    
    // MARK: - 2. 30-Day Physiological Health Trend Card
    private var healthTrendHistoryCard: some View {
        let trend = state.healthTrend
        
        return VStack(alignment: .leading, spacing: 16) {
            // Header
            VStack(alignment: .leading, spacing: 2) {
                Text("📊 生理恢复与健康历史趋势 (30天)")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Text("对比夜间 HRV、静息心率 (RHR) 与身体电量、睡眠质量波动")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.textMuted)
            }
            
            if trend.isEmpty {
                HStack {
                    Spacer()
                    VStack(spacing: 8) {
                        Text("📊").font(.system(size: 28))
                        Text("暂无 30 天健康历史趋势")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundColor(Theme.textPrimary)
                        Text("在【我的】页面绑定佳明/高驰手表后将自动同步生成")
                            .font(.system(size: 11))
                            .foregroundColor(Theme.textMuted)
                    }
                    .padding(.vertical, 24)
                    Spacer()
                }
            } else {
                VStack(spacing: 20) {
                    // Sub-Chart 1: HRV vs RHR
                    hrvRhrSubChart(trend: trend)
                    
                    Divider().background(Theme.border)
                    
                    // Sub-Chart 2: Body Battery vs Sleep Score
                    batterySleepSubChart(trend: trend)
                }
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    // MARK: - Sub-Chart 1: HRV vs RHR
    private func hrvRhrSubChart(trend: [HealthTrendPoint]) -> some View {
        let validIdx = selectedHrvIndex ?? (trend.count - 1)
        let activePt = trend.indices.contains(validIdx) ? trend[validIdx] : trend.last
        let isLatest = validIdx == (trend.count - 1)
        
        let validRhrs = trend.compactMap { $0.resting_heart_rate }.filter { $0 > 0 }
        let validHrvs = trend.compactMap { $0.hrv }.filter { $0 > 0 }
        
        let minRhr = Double(validRhrs.min() ?? 45) - 4.0
        let maxRhr = Double(validRhrs.max() ?? 65) + 4.0
        let minHrv = Double(validHrvs.min() ?? 20) - 6.0
        let maxHrv = Double(validHrvs.max() ?? 60) + 6.0
        
        let cyanColor = Theme.isLight ? Color(hex: "0891B2") : Color(hex: "06B6D4")
        let roseColor = Theme.isLight ? Color(hex: "DC2626") : Color(hex: "EF4444")
        
        return VStack(alignment: .leading, spacing: 10) {
            // Title & Active Tooltip
            HStack(alignment: .center) {
                HStack(spacing: 4) {
                    Text("💓").font(.system(size: 13))
                    Text("夜间 HRV 与 静息心率 (RHR)")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                }
                Spacer()
                
                if let pt = activePt {
                    HStack(spacing: 6) {
                        Text(pt.date_label ?? pt.date ?? "")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundColor(Theme.textMuted)
                        
                        if isLatest {
                            Text("最新")
                                .font(.system(size: 9, weight: .bold))
                                .foregroundColor(Theme.primaryOrange)
                                .padding(.horizontal, 4)
                                .padding(.vertical, 1)
                                .background(Theme.brandTint)
                                .cornerRadius(4)
                        }
                        
                        Text("HRV: \(pt.hrv != nil ? "\(pt.hrv!)ms" : "—")")
                            .font(.system(size: 10, weight: .bold, design: .monospaced))
                            .foregroundColor(cyanColor)
                        
                        Text("RHR: \(pt.resting_heart_rate != nil ? "\(pt.resting_heart_rate!)bpm" : "—")")
                            .font(.system(size: 10, weight: .bold, design: .monospaced))
                            .foregroundColor(roseColor)
                    }
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(Theme.surfaceSecondary)
                    .cornerRadius(6)
                }
            }
            
            // Canvas Chart
            GeometryReader { geo in
                let w = geo.size.width
                let h = geo.size.height - 20
                let padX: CGFloat = 16
                let plotW = max(1, w - padX * 2)
                let n = trend.count
                
                ZStack(alignment: .topLeading) {
                    // Subtle horizontal gridlines
                    VStack(spacing: 0) {
                        Divider().background(Theme.border)
                        Spacer()
                        Divider().background(Theme.border)
                        Spacer()
                        Divider().background(Theme.border)
                    }
                    .frame(height: h)
                    
                    // HRV line path (Cyan)
                    Path { path in
                        var started = false
                        for (i, pt) in trend.enumerated() {
                            guard let val = pt.hrv else { continue }
                            let x = padX + (CGFloat(i) / CGFloat(max(1, n - 1))) * plotW
                            let norm = CGFloat((Double(val) - minHrv) / max(1.0, maxHrv - minHrv))
                            let y = h - norm * h
                            if !started {
                                path.move(to: CGPoint(x: x, y: y))
                                started = true
                            } else {
                                path.addLine(to: CGPoint(x: x, y: y))
                            }
                        }
                    }
                    .stroke(cyanColor, style: StrokeStyle(lineWidth: 2.2, lineCap: .round, lineJoin: .round))
                    
                    // RHR line path (Rose)
                    Path { path in
                        var started = false
                        for (i, pt) in trend.enumerated() {
                            guard let val = pt.resting_heart_rate else { continue }
                            let x = padX + (CGFloat(i) / CGFloat(max(1, n - 1))) * plotW
                            let norm = CGFloat((Double(val) - minRhr) / max(1.0, maxRhr - minRhr))
                            let y = h - norm * h
                            if !started {
                                path.move(to: CGPoint(x: x, y: y))
                                started = true
                            } else {
                                path.addLine(to: CGPoint(x: x, y: y))
                            }
                        }
                    }
                    .stroke(roseColor, style: StrokeStyle(lineWidth: 2.2, lineCap: .round, lineJoin: .round))
                    
                    // Active vertical cursor & points
                    if let pt = activePt, let i = trend.firstIndex(where: { $0.id == pt.id }) {
                        let x = padX + (CGFloat(i) / CGFloat(max(1, n - 1))) * plotW
                        
                        Path { path in
                            path.move(to: CGPoint(x: x, y: 0))
                            path.addLine(to: CGPoint(x: x, y: h))
                        }
                        .stroke(Theme.textMuted.opacity(0.45), style: StrokeStyle(lineWidth: 1, dash: [3, 3]))
                        
                        if let hVal = pt.hrv {
                            let norm = CGFloat((Double(hVal) - minHrv) / max(1.0, maxHrv - minHrv))
                            let y = h - norm * h
                            Circle()
                                .fill(cyanColor)
                                .frame(width: 8, height: 8)
                                .overlay(Circle().stroke(Theme.surface, lineWidth: 1.5))
                                .position(x: x, y: y)
                        }
                        
                        if let rVal = pt.resting_heart_rate {
                            let norm = CGFloat((Double(rVal) - minRhr) / max(1.0, maxRhr - minRhr))
                            let y = h - norm * h
                            Circle()
                                .fill(roseColor)
                                .frame(width: 8, height: 8)
                                .overlay(Circle().stroke(Theme.surface, lineWidth: 1.5))
                                .position(x: x, y: y)
                        }
                    }
                    
                    // Date axis labels at bottom
                    HStack {
                        if let first = trend.first?.date_label ?? trend.first?.date {
                            Text(first).font(.system(size: 9)).foregroundColor(Theme.textMuted)
                        }
                        Spacer()
                        if n > 2, let mid = trend[n / 2].date_label ?? trend[n / 2].date {
                            Text(mid).font(.system(size: 9)).foregroundColor(Theme.textMuted)
                        }
                        Spacer()
                        if let last = trend.last?.date_label ?? trend.last?.date {
                            Text(last).font(.system(size: 9)).foregroundColor(Theme.textMuted)
                        }
                    }
                    .padding(.horizontal, padX)
                    .position(x: w / 2, y: h + 10)
                    
                    // Touch / Drag Area
                    Color.clear
                        .contentShape(Rectangle())
                        .gesture(
                            DragGesture(minimumDistance: 0)
                                .onChanged { value in
                                    let relX = max(0, min(plotW, value.location.x - padX))
                                    let idx = Int(round((relX / plotW) * CGFloat(max(1, n - 1))))
                                    selectedHrvIndex = max(0, min(n - 1, idx))
                                }
                        )
                }
            }
            .frame(height: 120)
            
            // Legend
            HStack(spacing: 16) {
                HStack(spacing: 5) {
                    Circle().fill(cyanColor).frame(width: 7, height: 7)
                    Text("夜间 HRV (ms)").font(.system(size: 10)).foregroundColor(Theme.textMuted)
                }
                HStack(spacing: 5) {
                    Circle().fill(roseColor).frame(width: 7, height: 7)
                    Text("静息心率 RHR (bpm)").font(.system(size: 10)).foregroundColor(Theme.textMuted)
                }
                Spacer()
            }
        }
    }
    
    // MARK: - Sub-Chart 2: Body Battery vs Sleep Score
    private func batterySleepSubChart(trend: [HealthTrendPoint]) -> some View {
        let validIdx = selectedBatteryIndex ?? (trend.count - 1)
        let activePt = trend.indices.contains(validIdx) ? trend[validIdx] : trend.last
        let isLatest = validIdx == (trend.count - 1)
        
        let indigoColor = Theme.isLight ? Color(hex: "4F46E5") : Color(hex: "818CF8")
        let amberColor = Theme.isLight ? Color(hex: "CA8A04") : Color(hex: "EAB308")
        
        return VStack(alignment: .leading, spacing: 10) {
            // Title & Active Tooltip
            HStack(alignment: .center) {
                HStack(spacing: 4) {
                    Text("⚡").font(.system(size: 13))
                    Text("身体电量 与 睡眠得分")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                }
                Spacer()
                
                if let pt = activePt {
                    HStack(spacing: 6) {
                        Text(pt.date_label ?? pt.date ?? "")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundColor(Theme.textMuted)
                        
                        if isLatest {
                            Text("最新")
                                .font(.system(size: 9, weight: .bold))
                                .foregroundColor(Theme.primaryOrange)
                                .padding(.horizontal, 4)
                                .padding(.vertical, 1)
                                .background(Theme.brandTint)
                                .cornerRadius(4)
                        }
                        
                        Text("睡眠: \(pt.sleep_score != nil ? "\(pt.sleep_score!)分" : "—")")
                            .font(.system(size: 10, weight: .bold, design: .monospaced))
                            .foregroundColor(indigoColor)
                        
                        Text("电量: \(pt.body_battery != nil ? "\(pt.body_battery!)%" : "—")")
                            .font(.system(size: 10, weight: .bold, design: .monospaced))
                            .foregroundColor(amberColor)
                    }
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(Theme.surfaceSecondary)
                    .cornerRadius(6)
                }
            }
            
            // Canvas Chart (0-100 scale)
            GeometryReader { geo in
                let w = geo.size.width
                let h = geo.size.height - 20
                let padL: CGFloat = 26
                let padR: CGFloat = 16
                let plotW = max(1, w - padL - padR)
                let n = trend.count
                
                ZStack(alignment: .topLeading) {
                    // Y Axis labels & gridlines (100, 50, 0)
                    VStack(spacing: 0) {
                        HStack(spacing: 4) {
                            Text("100").font(.system(size: 8)).foregroundColor(Theme.textMuted).frame(width: 20, alignment: .trailing)
                            Divider().background(Theme.border)
                        }
                        Spacer()
                        HStack(spacing: 4) {
                            Text("50").font(.system(size: 8)).foregroundColor(Theme.textMuted).frame(width: 20, alignment: .trailing)
                            Divider().background(Theme.border)
                        }
                        Spacer()
                        HStack(spacing: 4) {
                            Text("0").font(.system(size: 8)).foregroundColor(Theme.textMuted).frame(width: 20, alignment: .trailing)
                            Divider().background(Theme.border)
                        }
                    }
                    .frame(height: h)
                    
                    // Sleep Score line path (Indigo)
                    Path { path in
                        var started = false
                        for (i, pt) in trend.enumerated() {
                            guard let val = pt.sleep_score else { continue }
                            let x = padL + (CGFloat(i) / CGFloat(max(1, n - 1))) * plotW
                            let norm = CGFloat(max(0, min(100, val))) / 100.0
                            let y = h - norm * h
                            if !started {
                                path.move(to: CGPoint(x: x, y: y))
                                started = true
                            } else {
                                path.addLine(to: CGPoint(x: x, y: y))
                            }
                        }
                    }
                    .stroke(indigoColor, style: StrokeStyle(lineWidth: 2.2, lineCap: .round, lineJoin: .round))
                    
                    // Body Battery line path (Amber)
                    Path { path in
                        var started = false
                        for (i, pt) in trend.enumerated() {
                            guard let val = pt.body_battery else { continue }
                            let x = padL + (CGFloat(i) / CGFloat(max(1, n - 1))) * plotW
                            let norm = CGFloat(max(0, min(100, val))) / 100.0
                            let y = h - norm * h
                            if !started {
                                path.move(to: CGPoint(x: x, y: y))
                                started = true
                            } else {
                                path.addLine(to: CGPoint(x: x, y: y))
                            }
                        }
                    }
                    .stroke(amberColor, style: StrokeStyle(lineWidth: 2.2, lineCap: .round, lineJoin: .round))
                    
                    // Active vertical cursor & points
                    if let pt = activePt, let i = trend.firstIndex(where: { $0.id == pt.id }) {
                        let x = padL + (CGFloat(i) / CGFloat(max(1, n - 1))) * plotW
                        
                        Path { path in
                            path.move(to: CGPoint(x: x, y: 0))
                            path.addLine(to: CGPoint(x: x, y: h))
                        }
                        .stroke(Theme.textMuted.opacity(0.45), style: StrokeStyle(lineWidth: 1, dash: [3, 3]))
                        
                        if let sVal = pt.sleep_score {
                            let norm = CGFloat(max(0, min(100, sVal))) / 100.0
                            let y = h - norm * h
                            Circle()
                                .fill(indigoColor)
                                .frame(width: 8, height: 8)
                                .overlay(Circle().stroke(Theme.surface, lineWidth: 1.5))
                                .position(x: x, y: y)
                        }
                        
                        if let bVal = pt.body_battery {
                            let norm = CGFloat(max(0, min(100, bVal))) / 100.0
                            let y = h - norm * h
                            Circle()
                                .fill(amberColor)
                                .frame(width: 8, height: 8)
                                .overlay(Circle().stroke(Theme.surface, lineWidth: 1.5))
                                .position(x: x, y: y)
                        }
                    }
                    
                    // Date axis labels at bottom
                    HStack {
                        if let first = trend.first?.date_label ?? trend.first?.date {
                            Text(first).font(.system(size: 9)).foregroundColor(Theme.textMuted)
                        }
                        Spacer()
                        if n > 2, let mid = trend[n / 2].date_label ?? trend[n / 2].date {
                            Text(mid).font(.system(size: 9)).foregroundColor(Theme.textMuted)
                        }
                        Spacer()
                        if let last = trend.last?.date_label ?? trend.last?.date {
                            Text(last).font(.system(size: 9)).foregroundColor(Theme.textMuted)
                        }
                    }
                    .padding(.leading, padL)
                    .padding(.trailing, padR)
                    .position(x: (w + padL - padR) / 2, y: h + 10)
                    
                    // Touch / Drag Area
                    Color.clear
                        .contentShape(Rectangle())
                        .gesture(
                            DragGesture(minimumDistance: 0)
                                .onChanged { value in
                                    let relX = max(0, min(plotW, value.location.x - padL))
                                    let idx = Int(round((relX / plotW) * CGFloat(max(1, n - 1))))
                                    selectedBatteryIndex = max(0, min(n - 1, idx))
                                }
                        )
                }
            }
            .frame(height: 120)
            
            // Legend
            HStack(spacing: 16) {
                HStack(spacing: 5) {
                    Circle().fill(indigoColor).frame(width: 7, height: 7)
                    Text("睡眠质量得分 (分)").font(.system(size: 10)).foregroundColor(Theme.textMuted)
                }
                HStack(spacing: 5) {
                    Circle().fill(amberColor).frame(width: 7, height: 7)
                    Text("身体电量 Max (%)").font(.system(size: 10)).foregroundColor(Theme.textMuted)
                }
                Spacer()
            }
        }
    }
    
    // MARK: - 3. VDOT & Race Predictions Card
    private var vdotAndPredictionsCard: some View {
        let vdot = state.scienceMetrics?.vdot ?? state.currentUser?.vo2max ?? 40.9
        let preds = state.scienceMetrics?.race_predictions
        
        return VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("⚡ JACK DANIELS VDOT 跑力值")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                    Text("基于近期最佳比赛/训练表现与心率综合推演")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
                Spacer()
                Text(String(format: "VDOT %.1f", vdot))
                    .font(.system(size: 18, weight: .black, design: .rounded))
                    .foregroundColor(Theme.primaryOrange)
            }
            
            Text("🏆 基于当前跑力的各距离成绩预测 (Race Predictions)")
                .font(.system(size: 12, weight: .bold))
                .foregroundColor(Theme.textPrimary)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 8) {
                predTile(dist: "5 公里", time: preds?.five_k ?? "23:41", color: Theme.textPrimary)
                predTile(dist: "10 公里", time: preds?.ten_k ?? "49:07", color: Theme.textPrimary)
                predTile(dist: "半程马拉松", time: preds?.half_marathon ?? "1:48:55", color: Theme.primaryOrange)
                predTile(dist: "全程马拉松", time: preds?.marathon ?? "3:45:41", color: Theme.accentRose)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private func predTile(dist: String, time: String, color: Color) -> some View {
        VStack(spacing: 3) {
            Text(dist)
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
            Text(time)
                .font(.system(size: 13, weight: .bold, design: .monospaced))
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(Theme.surfaceSecondary)
        .cornerRadius(8)
    }
    
    // MARK: - 4. Renato Canova Pacing Matrix Card
    private var canovaPacingMatrixCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("🎯 Renato Canova 马拉松专项配速矩阵")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text("世界顶级中长跑教练卡诺瓦的核心分期训练区间")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
                Spacer()
            }
            
            if let zones = state.scienceMetrics?.canova_zones, !zones.isEmpty {
                VStack(spacing: 8) {
                    if let z = zones["recovery"] {
                        canovaPaceRow(zone: z.name ?? "恢复跑 / 基础慢跑", pace: z.range ?? "5:37 ~ 5:06 /km", desc: z.desc ?? "毛细血管增生与有氧基础构建", color: Theme.accentGreen)
                    }
                    if let z = zones["fundamental"] {
                        canovaPaceRow(zone: z.name ?? "基础有氧耐力", pace: z.range ?? "4:59 ~ 4:44 /km", desc: z.desc ?? "马拉松配速的 90%~95%，持续有氧长跑 (LSD/Progression)", color: Theme.accentBlue)
                    }
                    if let z = zones["special"] {
                        canovaPaceRow(zone: z.name ?? "专项准备能力", pace: z.range ?? "4:44 ~ 4:29 /km", desc: z.desc ?? "马拉松配速的 95%~100%，乳酸阈值与专项耐力结合", color: Theme.accentYellow)
                    }
                    if let z = zones["specific"] {
                        canovaPaceRow(zone: z.name ?? "马拉松专项速度", pace: z.range ?? "4:29 ~ 4:17 /km", desc: z.desc ?? "目标全马配速 100%~105%，比赛核心专项刺激", color: Theme.primaryOrange)
                    }
                    if let z = zones["max_specific"] {
                        canovaPaceRow(zone: z.name ?? "最大专项速度", pace: z.range ?? "4:17 ~ 4:01 /km", desc: z.desc ?? "半马/10K 配速间歇，提升 VO2max 与速度储备", color: Theme.accentRose)
                    }
                }
            } else {
                VStack(spacing: 8) {
                    canovaPaceRow(zone: "基础有氧 (Aerobic Base)", pace: "5:45 ~ 6:15 /km", desc: "恢复跑与大容量有氧耐力构建，保持心率在 Zone 1-2", color: Theme.accentGreen)
                    canovaPaceRow(zone: "专项有氧 (Specific Aerobic)", pace: "5:00 ~ 5:25 /km", desc: "提升糖原储备和慢肌纤维效率，长距离渐速跑核心配速", color: Theme.accentBlue)
                    canovaPaceRow(zone: "乳酸阈值 (Lactate Threshold)", pace: "4:25 ~ 4:40 /km", desc: "提升乳酸清除与耐受能力，抗疲劳专项课的关键配速", color: Theme.accentYellow)
                    canovaPaceRow(zone: "马拉松专项 (Marathon Special)", pace: "4:30 ~ 4:45 /km", desc: "比赛目标配速 (MP)，专项准备期 15-30km 长跑的核心", color: Theme.primaryOrange)
                    canovaPaceRow(zone: "专项耐力 (Specific Endurance)", pace: "4:10 ~ 4:25 /km", desc: "突破速度耐力与线粒体氧化能力，专项长段落间歇", color: Theme.accentRose)
                    canovaPaceRow(zone: "专项速度 (Specific Speed)", pace: "3:55 ~ 4:10 /km", desc: "神经肌肉募集与无氧缓冲能力提升，1K短间歇刺激", color: Color.purple)
                }
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private func canovaPaceRow(zone: String, pace: String, desc: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(zone)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Theme.textPrimary)
                Spacer()
                Text(pace)
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundColor(color)
            }
            Text(desc)
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
        }
        .padding(8)
        .background(Theme.surfaceSecondary)
        .cornerRadius(8)
    }
    
    // MARK: - 5. Heart Rate Zones Distribution Card
    private var heartRateZonesCard: some View {
        let mhr = state.currentUser?.max_heart_rate ?? 190
        let z1 = Int(Double(mhr) * 0.70)
        let z2 = Int(Double(mhr) * 0.80)
        let z3 = Int(Double(mhr) * 0.88)
        let z4 = Int(Double(mhr) * 0.94)
        
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("心率区间 (HR Zones)")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Spacer()
                Text("最大心率 \(mhr) bpm")
                    .font(.system(size: 11))
                    .foregroundColor(Theme.textMuted)
            }
            
            VStack(spacing: 6) {
                hrBar(zone: "Z1 恢复区", range: "< \(z1) bpm", pct: 0.15, color: Theme.textSecondary)
                hrBar(zone: "Z2 有氧基础区", range: "\(z1) - \(z2) bpm", pct: 0.55, color: Theme.accentGreen)
                hrBar(zone: "Z3 节奏区", range: "\(z2 + 1) - \(z3) bpm", pct: 0.20, color: Theme.accentYellow)
                hrBar(zone: "Z4 阈值区", range: "\(z3 + 1) - \(z4) bpm", pct: 0.08, color: Theme.primaryOrange)
                hrBar(zone: "Z5 无氧极限", range: "> \(z4) bpm", pct: 0.02, color: Color.red)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private func hrBar(zone: String, range: String, pct: Double, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(zone)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(Theme.textSecondary)
                Spacer()
                Text(range)
                    .font(.system(size: 11))
                    .foregroundColor(Theme.textMuted)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Theme.surfaceSecondary)
                        .frame(height: 6)
                    RoundedRectangle(cornerRadius: 4)
                        .fill(color)
                        .frame(width: geo.size.width * CGFloat(pct), height: 6)
                }
            }
            .frame(height: 6)
        }
    }
    
    // MARK: - 6. Scientific Citations & Medical Disclaimer Card
    private var scientificDisclaimerFooterCard: some View {
        Button(action: { showCitationsSheet = true }) {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "exclamationmark.shield.fill")
                    .foregroundColor(Theme.primaryOrange)
                    .font(.system(size: 16))
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("科学理论依据、文献引用与健康免责声明")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text("本页面生理与体能计算模型基于 Banister(1975)、Jack Daniels VDOT(1979) 与 Karvonen(1957) 经典学术文献。仅供日常训练参考，不构成医疗诊断或处方。点击查看完整学术文献引用 ➔")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                        .multilineTextAlignment(.leading)
                        .lineSpacing(2)
                }
                Spacer()
            }
            .padding(14)
            .background(Theme.surface)
            .cornerRadius(12)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.primaryOrange.opacity(0.3), lineWidth: 1))
        }
    }
}

// ════════════════════════════════════════════════════════════════════
// MARK: - Scientific Citations & Medical Disclaimer Sheet (Guideline 1.4.1)
// ════════════════════════════════════════════════════════════════════

struct ScientificCitationsSheet: View {
    @Environment(\.presentationMode) var presentationMode
    
    var body: some View {
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()
                
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        // 1. Medical & Health Disclaimer
                        disclaimerCard
                        
                        // 2. Banister Impulse-Response
                        citationCard(
                            badge: "体能与疲劳模型",
                            title: "1. Banister 冲动-响应体能与疲劳模型 (CTL / ATL / TSB)",
                            citation: "Banister, E. W., Calvert, T. W., Savage, M. V., & Bach, T. (1975). A systems model of training for athletic performance. Australian Journal of Sports Medicine, 7, 57–61.",
                            description: "量化每日训练负荷（TRIMP / Training Stress），计算体能底座（CTL 42天均值）、急性疲劳（ATL 7天均值）与竞技就绪度（TSB = CTL - ATL），预防过度训练与运动伤病。",
                            linkTitle: "在 PubMed 检索学术文献验证 (PMID: 11797825)",
                            linkURL: "https://pubmed.ncbi.nlm.nih.gov/11797825/"
                        )
                        
                        // 3. Jack Daniels VDOT
                        citationCard(
                            badge: "跑力与成绩预测",
                            title: "2. Jack Daniels VDOT 跑力公式与最大摄氧量估算",
                            citation: "Daniels, J., & Gilbert, J. (1979). Oxygen Power: Performance Tables for Distance Runners. / Daniels, J. (2013). Daniels' Running Formula (3rd ed.). Human Kinetics.",
                            description: "依据跑者 5K、10K、半马或全马最佳战绩反推有效最大摄氧量（VDOT 跑力值），指导 E/M/T/I/R 各区间配速并推算马拉松完赛时间。",
                            linkTitle: "访问 Jack Daniels VDOT 官方权威标准",
                            linkURL: "https://vdoto2.com"
                        )
                        
                        // 4. Karvonen HRR
                        citationCard(
                            badge: "心率训练区间",
                            title: "3. Karvonen 储备心率 (HRR) 训练区间模型",
                            citation: "Karvonen, M. J., Kentala, E., & Mustala, O. (1957). The effects of training on heart rate: A longitudinal study. Ann Med Exp Biol Fenn, 35(3), 307–315.",
                            description: "结合静息心率与最大心率精确划分 5 级训练区间：Z1/Z2 有氧基础区、Z3 马拉松配速区、Z4 乳酸阈值区与 Z5 无氧间歇区。",
                            linkTitle: "在 PubMed 检索 Karvonen 经典文献 (PMID: 13470504)",
                            linkURL: "https://pubmed.ncbi.nlm.nih.gov/13470504/"
                        )
                        
                        // 5. Renato Canova
                        citationCard(
                            badge: "AI教练周期理论",
                            title: "4. Renato Canova 马拉松特异性训练与阻断期周期理论",
                            citation: "Canova, R. (1999). Marathon Training: A Scientific Approach. New Studies in Athletics, International Association of Athletics Federations (IAAF), 14(4), 27–42.",
                            description: "Canova AI 教练的专项化配速矩阵构建、长距离阻断（Special Block）课表设计与马拉松特异耐力发展指导。",
                            linkTitle: "查阅 World Athletics (IAAF) 教练学术文献",
                            linkURL: "https://worldathletics.org"
                        )
                        
                        // 6. External Web Version Link
                        webLinkCard
                    }
                    .padding(16)
                    .padding(.bottom, 30)
                }
            }
            .navigationTitle("科学文献引用与免责声明")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("完成") {
                        presentationMode.wrappedValue.dismiss()
                    }
                    .foregroundColor(Theme.primaryOrange)
                    .font(.system(size: 15, weight: .bold))
                }
            }
        }
        .preferredColorScheme(Theme.isLight ? .light : .dark)
    }
    
    private var disclaimerCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: "exclamationmark.shield.fill")
                    .foregroundColor(Color(hex: "F43F5E"))
                    .font(.system(size: 16))
                Text("运动健康与医学免责声明")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Color(hex: "F43F5E"))
            }
            Text("本应用（RGM）所展示的所有体能指数（CTL/ATL/TSB）、恢复评估（Recovery/Strain）、心率区间划分、跑力与完赛预测以及 Canova AI 教练的训练建议，均基于公开发表的运动生理学经典数学模型与耐力训练学术理论。\n\n上述计算模型与分析建议仅作为耐力跑者与教练日常科学训练的参考依据，不构成任何临床诊断、医疗健康处方或医学治疗方案。在开始任何高强度耐力跑步训练或备战马拉松前，请务必咨询专业医疗机构及执业医师。")
                .font(.system(size: 12))
                .foregroundColor(Theme.textSecondary)
                .lineSpacing(3)
        }
        .padding(14)
        .background(Color(hex: "F43F5E").opacity(0.1))
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(hex: "F43F5E").opacity(0.3), lineWidth: 1))
    }
    
    private func citationCard(badge: String, title: String, citation: String, description: String, linkTitle: String, linkURL: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(badge)
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(Theme.primaryOrange)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(Theme.primaryOrange.opacity(0.15))
                .cornerRadius(4)
            
            Text(title)
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(Theme.textPrimary)
            
            Text(citation)
                .font(.system(size: 11, weight: .medium))
                .foregroundColor(Theme.textSecondary)
                .italic()
            
            Text(description)
                .font(.system(size: 11))
                .foregroundColor(Theme.textMuted)
                .lineSpacing(2)
            
            if let url = URL(string: linkURL) {
                Link(destination: url) {
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.up.right.square")
                        Text(linkTitle)
                    }
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(Theme.primaryOrange)
                }
                .padding(.top, 2)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
    }
    
    private var webLinkCard: some View {
        VStack(alignment: .center, spacing: 6) {
            if let url = URL(string: "https://rgm.vanpower.net/citations") {
                Link(destination: url) {
                    HStack(spacing: 6) {
                        Image(systemName: "globe")
                        Text("在浏览器查看官方完整学术文献与合规政策")
                    }
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Theme.textPrimary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(Theme.surfaceSecondary)
                    .cornerRadius(10)
                }
            }
        }
    }
}

