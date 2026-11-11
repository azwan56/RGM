import SwiftUI

struct DashboardView: View {
    @EnvironmentObject var state: AppState
    
    // Tab switcher: "week" vs "month"
    @State private var activeGoalTab: String = "week"
    // Selected month in 12-month bar chart
    @State private var selectedMonthIndex: Int = 10 // Default to October
    
    var body: some View {
        let snap = state.whoopSnapshot
        ZStack {
            Theme.background.ignoresSafeArea()
            
            ScrollView {
                VStack(spacing: 16) {
                    // 1. Runner Greeting & Watch Sync Status
                    greetingHeader
                        .padding(.top, 8)
                    
                    // 2. Canova AI Daily Coach Tip
                    if let tip = state.dashboard.aiCoachTip, !tip.isEmpty {
                        aiCoachTipCard(tip: tip)
                    }
                    
                    // 2b. WHOOP Three Core Rings (实时恢复 · 全天负荷 · 睡眠)
                    whoopThreeRingsCard(snap)
                    
                    // 3. Goal Progress Hero Card (Dual View: Week vs Month)
                    goalHeroProgressCard
                    
                    // 3b. Recovery Assessment Card (恢复评估 Recovery - 位于本周进度与体能状况指数之间)
                    whoopRecoveryAssessmentCard(snap)
                    
                    // 4. Fitness & Form (Banister CTL / ATL / TSB Radar & Chart)
                    fitnessAndFormCard
                    
                    // 5. Physiological Recovery 4-Grid Card (Sleep, RHR, Body Battery, HRV)
                    healthRecoveryGridCard
                    
                    // 6. Yearly Mileage & 12-Month Bar Chart
                    if let yearly = state.dashboard.yearlyStats {
                        yearlyMileageCard(yearly: yearly)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 110)
            }
            .refreshable {
                await state.refreshData()
            }
        }
    }
    
    // MARK: - 1. Greeting Header
    private var greetingHeader: some View {
        HStack {
            // User Avatar
            if let avatar = state.currentUser?.avatar_url, let url = URL(string: avatar) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let img):
                        img.resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(width: 44, height: 44)
                            .clipShape(Circle())
                    default:
                        defaultAvatarHeader
                    }
                }
            } else {
                defaultAvatarHeader
            }
            
            VStack(alignment: .leading, spacing: 2) {
                Text("欢迎回来，")
                    .font(.system(size: 11))
                    .foregroundColor(Theme.textMuted)
                Text(state.currentUser?.displayName ?? "跑者")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
            }
            
            Spacer()
            
            // Quick Theme Toggle Pill (Volt / Dark)
            Button(action: {
                let nextMode: ThemeMode = (state.themeMode == .volt) ? .dark : .volt
                state.setTheme(nextMode)
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }) {
                HStack(spacing: 4) {
                    Text(state.themeMode == .volt ? "⚡" : "🌑")
                        .font(.system(size: 11))
                    Text(state.themeMode == .volt ? "经典竞技" : "经典暗黑")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.textPrimary)
                }
                .padding(.horizontal, 9)
                .padding(.vertical, 6)
                .background(Theme.surface)
                .cornerRadius(20)
                .overlay(RoundedRectangle(cornerRadius: 20).stroke(Theme.border, lineWidth: 1))
            }
            .buttonStyle(PlainButtonStyle())
            
            // Data Source Live Tag (tappable -> jumps to Profile watch binding)
            Button(action: { state.selectedTab = 3 }) {
                let garminOn = state.fullProfile?.garmin_connected ?? state.currentUser?.garmin_connected ?? false
                let corosOn = state.fullProfile?.coros_connected ?? state.currentUser?.coros_connected ?? false
                let awOn = state.fullProfile?.apple_watch_connected ?? state.currentUser?.apple_watch_connected ?? false
                let anyWatch = garminOn || corosOn || awOn
                HStack(spacing: 5) {
                    Image(systemName: anyWatch ? "applewatch.radiowaves.left.and.right" : "heart.text.square.fill")
                        .foregroundColor(anyWatch ? Theme.accentGreen : Theme.primaryOrange)
                        .font(.system(size: 12))
                    Text(anyWatch ? "手表已连接" : "连接手表 ›")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(Theme.textSecondary)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Theme.surface)
                .cornerRadius(20)
                .overlay(RoundedRectangle(cornerRadius: 20).stroke(Theme.border, lineWidth: 1))
            }
            .buttonStyle(PlainButtonStyle())
        }
        .padding(.top, 8)
    }
    
    private var defaultAvatarHeader: some View {
        ZStack {
            Circle()
                .fill(Theme.surfaceSecondary)
                .frame(width: 44, height: 44)
            Text("🏃")
                .font(.system(size: 20))
        }
    }
    
    // MARK: - 2. AI Coach Daily Tip
    private func aiCoachTipCard(tip: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text("💡")
                .font(.system(size: 15))
            VStack(alignment: .leading, spacing: 3) {
                Text("Canova 每日箴言")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(Theme.primaryOrange)
                Text(tip)
                    .font(.system(size: 12))
                    .foregroundColor(Theme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer()
        }
        .padding(12)
        .background(Theme.surface)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.primaryOrange.opacity(0.35), lineWidth: 1))
    }
    
    // MARK: - 3. Dual Goal Progress Hero Card
    private var goalHeroProgressCard: some View {
        let garminOn = state.fullProfile?.garmin_connected ?? state.currentUser?.garmin_connected ?? false
        let corosOn = state.fullProfile?.coros_connected ?? state.currentUser?.coros_connected ?? false
        let awOn = state.fullProfile?.apple_watch_connected ?? state.currentUser?.apple_watch_connected ?? false
        let hasCloudWatch = garminOn || corosOn
        
        return VStack(spacing: 14) {
            // Segmented Switcher
            HStack(spacing: 8) {
                Button(action: { activeGoalTab = "week" }) {
                    HStack(spacing: 4) {
                        Text("🏃")
                        Text("本周跑量")
                            .font(.system(size: 13, weight: activeGoalTab == "week" ? .bold : .medium))
                    }
                    .foregroundColor(activeGoalTab == "week" ? Theme.onBrand : Theme.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(activeGoalTab == "week" ? Theme.brandFill : Color.clear)
                    .cornerRadius(8)
                }
                
                Button(action: { activeGoalTab = "month" }) {
                    HStack(spacing: 4) {
                        Text("📅")
                        Text("当月跑量")
                            .font(.system(size: 13, weight: activeGoalTab == "month" ? .bold : .medium))
                    }
                    .foregroundColor(activeGoalTab == "month" ? Theme.onBrand : Theme.textMuted)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(activeGoalTab == "month" ? Theme.brandFill : Color.clear)
                    .cornerRadius(8)
                }
            }
            .padding(4)
            .background(Theme.surfaceSecondary)
            .cornerRadius(10)
            
            if activeGoalTab == "week" {
                weeklyGoalView
            } else {
                monthlyGoalView
            }
            
            // Unified Brand-Neutral Watch & Health Sync Button
            Button(action: {
                Task {
                    if hasCloudWatch {
                        await state.syncWatches()
                    } else if awOn {
                        _ = await state.syncHealthKit(watchBrand: "apple_watch")
                    } else {
                        _ = await state.syncHealthKit(watchBrand: nil)
                    }
                }
            }) {
                HStack(spacing: 8) {
                    if state.isSyncing {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: Theme.onBrand))
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "arrow.triangle.2.circlepath.icloud.fill")
                            .font(.system(size: 13, weight: .bold))
                    }
                    Text(state.isSyncing ? "正在同步最新跑步记录..." : "同步最新跑步记录")
                        .font(.system(size: 13, weight: .bold))
                }
                .foregroundColor(Theme.onBrand)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 11)
                .background(
                    LinearGradient(
                        colors: [Theme.brandFill, Theme.brandGradientEnd],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .cornerRadius(10)
            }
            .disabled(state.isSyncing)
            
            if let notice = state.syncNotice, !notice.isEmpty {
                Text(notice)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(Theme.textSecondary)
            }
            
            // Physiological Analysis Quick Link
            Button(action: { state.selectedTab = 2 }) {
                HStack(spacing: 6) {
                    Text("📈")
                        .font(.system(size: 13))
                    Text("深度生理分析 · 疲劳诊断与跑力预测")
                        .font(.system(size: 11, weight: .semibold))
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.system(size: 10, weight: .semibold))
                }
                .foregroundColor(Theme.textSecondary)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(Theme.surfaceSecondary)
                .cornerRadius(8)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.border, lineWidth: 1))
    }
    
    // Weekly Progress Content
    private var weeklyGoalView: some View {
        let wp = state.effectiveWeeklyProgress
        let currentKm = wp.current_week_km ?? 0.0
        let targetKm = wp.target_week_km ?? 50.0
        let pct = wp.progress_pct ?? (targetKm > 0 ? (currentKm / targetKm * 100) : 0)
        let remainKm = wp.remaining_km ?? max(0, targetKm - currentKm)
        let dailyReq = wp.daily_required_km ?? (remainKm / 7.0)
        
        return VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("本周跑量进度")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text(wp.week_label ?? "当前周计划")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                }
                Spacer()
                Text(String(format: "%.1f%%", pct))
                    .font(.system(size: 20, weight: .black, design: .rounded))
                    .foregroundColor(Theme.accentGreen)
            }
            
            // Progress Track
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Theme.surfaceSecondary)
                        .frame(height: 8)
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Theme.accentGreen)
                        .frame(width: min(geo.size.width * CGFloat(pct / 100.0), geo.size.width), height: 8)
                }
            }
            .frame(height: 8)
            
            // 4 Stats Grid
            HStack {
                statColumn(val: String(format: "%.1f", currentKm), label: "已跑 (km)", color: Theme.accentGreen)
                Divider().frame(height: 24).background(Theme.border)
                statColumn(val: "\(Int(targetKm))", label: "目标 (km)", color: Theme.textPrimary)
                Divider().frame(height: 24).background(Theme.border)
                statColumn(val: String(format: "%.1f", remainKm), label: "剩余 (km)", color: Theme.textPrimary)
                Divider().frame(height: 24).background(Theme.border)
                statColumn(val: String(format: "%.1f", dailyReq), label: "日均需跑", color: Theme.primaryOrange)
            }
            .padding(.vertical, 6)
            
            // 7-Day Mon-Sun Weekday Strip
            if let days = wp.daily_breakdown, !days.isEmpty {
                HStack(spacing: 6) {
                    ForEach(days) { day in
                        VStack(spacing: 4) {
                            Text(day.short_day ?? day.day_name ?? "")
                                .font(.system(size: 10, weight: day.is_today ? .bold : .regular))
                                .foregroundColor(day.is_today ? Theme.primaryOrange : Theme.textMuted)
                            
                            ZStack {
                                RoundedRectangle(cornerRadius: 6)
                                    .fill(day.distance_km > 0 ? Theme.accentGreen.opacity(0.2) : Theme.surfaceSecondary)
                                    .frame(height: 28)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 6)
                                            .stroke(day.is_today ? Theme.primaryOrange : Color.clear, lineWidth: 1.5)
                                    )
                                
                                if day.distance_km > 0 {
                                    Text(String(format: "%.1f", day.distance_km))
                                        .font(.system(size: 10, weight: .bold))
                                        .foregroundColor(Theme.accentGreen)
                                } else {
                                    Text(day.is_past ? "—" : "0")
                                        .font(.system(size: 10))
                                        .foregroundColor(Theme.textMuted)
                                }
                            }
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
            }
            
            // Today's Scheduled Workout (if any)
            if let tw = state.effectiveTodayWorkout {
                todayWorkoutSnippet(tw: tw)
            }
        }
    }
    
    // Monthly Progress Content
    private var monthlyGoalView: some View {
        let p = state.dashboard
        let currentKm = p.monthMileage
        let targetKm = p.monthTarget
        let pct = p.progressPercent > 0 ? p.progressPercent : (targetKm > 0 ? (currentKm / targetKm * 100) : 0)
        let remainKm = max(0, targetKm - currentKm)
        let dailyReq = remainKm / 31.0
        
        return VStack(spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("当月跑量目标")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text("本月进度 · 剩 31 天")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                }
                Spacer()
                Text(String(format: "%.1f%%", pct))
                    .font(.system(size: 20, weight: .black, design: .rounded))
                    .foregroundColor(Theme.primaryOrange)
            }
            
            // Progress Track
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Theme.surfaceSecondary)
                        .frame(height: 8)
                    RoundedRectangle(cornerRadius: 6)
                        .fill(
                            LinearGradient(
                                colors: [Theme.brandFill, Theme.brandGradientEnd],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .frame(width: min(geo.size.width * CGFloat(pct / 100.0), geo.size.width), height: 8)
                }
            }
            .frame(height: 8)
            
            // 4 Stats Grid
            HStack {
                statColumn(val: String(format: "%.1f", currentKm), label: "已跑 (km)", color: Theme.primaryOrange)
                Divider().frame(height: 24).background(Theme.border)
                statColumn(val: "\(Int(targetKm))", label: "目标 (km)", color: Theme.textPrimary)
                Divider().frame(height: 24).background(Theme.border)
                statColumn(val: String(format: "%.1f", remainKm), label: "剩余 (km)", color: Theme.textPrimary)
                Divider().frame(height: 24).background(Theme.border)
                statColumn(val: String(format: "%.1f", dailyReq), label: "日均需跑", color: Theme.primaryOrange)
            }
            .padding(.vertical, 6)
        }
    }
    
    private func statColumn(val: String, label: String, color: Color) -> some View {
        VStack(spacing: 2) {
            Text(val)
                .font(.system(size: 16, weight: .bold, design: .rounded))
                .foregroundColor(color)
            Text(label)
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
        }
        .frame(maxWidth: .infinity)
    }
    
    private func todayWorkoutSnippet(tw: TodayWorkoutData) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("📅 今日训练课目")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                
                if let type = tw.workout_type {
                    Text(type == "rest" ? "休息恢复" : (type == "special" ? "专项课" : "有氧耐力"))
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Theme.brandTint)
                        .cornerRadius(4)
                }
                Spacer()
                if let dist = tw.distance_km, dist > 0 {
                    Text(String(format: "%.1f km", dist))
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                }
            }
            
            Text(tw.title ?? "稳态有氧慢跑课")
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(Theme.textPrimary)
            
            if let desc = tw.description {
                Text(desc)
                    .font(.system(size: 11))
                    .foregroundColor(Theme.textSecondary)
                    .lineLimit(2)
            }
            
            if let notes = tw.coach_notes {
                HStack(alignment: .top, spacing: 4) {
                    Text("👨‍🏫")
                        .font(.system(size: 11))
                    Text(notes)
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                        .lineLimit(2)
                }
            }
        }
        .padding(10)
        .background(Theme.surfaceSecondary)
        .overlay(alignment: .leading) {
            if Theme.isLight {
                Rectangle()
                    .fill(Theme.brandFill)
                    .frame(width: 4)
            }
        }
        .cornerRadius(10)
    }
    
    // MARK: - 4. Fitness & Form (Banister CTL / ATL / TSB)
    private var fitnessAndFormCard: some View {
        let form = state.dashboard.fitnessForm
        let ctl = form?.ctl ?? 0.0
        let atl = form?.atl ?? 0.0
        let tsb = form?.tsb ?? 0.0
        let statusLabel = form?.status_label ?? "暂无数据"
        let statusColor: Color = tsb >= 5 ? Theme.accentGreen : (tsb >= -30 ? Theme.accentBlue : (tsb >= -50 ? Theme.accentYellow : Color.red))
        
        return VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("⚡ 体能与状况指数 (Fitness & Form)")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text("基于标准 Banister TRIMP 与 EWMA 模型算法")
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
            
            // 3 Metric Pills
            HStack(spacing: 10) {
                metricPill(title: "CTL 体能", val: String(format: "%.1f", ctl), sub: "42天长期负荷", color: Theme.accentBlue)
                metricPill(title: "ATL 疲劳", val: String(format: "%.1f", atl), sub: "7天近期负荷", color: Theme.accentRose)
                metricPill(title: "TSB 状况", val: String(format: "%+.1f", tsb), sub: "体能减去疲劳", color: statusColor)
            }
            
            // History Trend Chart Preview (Past 30 days)
            if let hist = form?.history, !hist.isEmpty {
                fitnessMiniChart(history: hist)
            }
            
            // Legend
            HStack(spacing: 12) {
                legendItem(color: Theme.accentBlue, label: "CTL (体能)")
                legendItem(color: Theme.accentRose, label: "ATL (疲劳)")
                legendItem(color: Theme.accentGreen, label: "+5 巅峰")
                legendItem(color: Theme.accentYellow, label: "-30 疲劳")
            }
            .font(.system(size: 10))
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.border, lineWidth: 1))
    }
    
    private func metricPill(title: String, val: String, sub: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title)
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
            Text(val)
                .font(.system(size: 18, weight: .black, design: .rounded))
                .foregroundColor(color)
            Text(sub)
                .font(.system(size: 9))
                .foregroundColor(Theme.textMuted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Theme.surfaceSecondary)
        .cornerRadius(10)
    }
    
    private func fitnessMiniChart(history: [FitnessHistoryItem]) -> some View {
        let maxVal = max(history.map { max($0.ctl ?? 0, $0.atl ?? 0) }.max() ?? 100, 100)
        
        return VStack(spacing: 4) {
            HStack(alignment: .bottom, spacing: 3) {
                ForEach(history.suffix(28), id: \.date) { pt in
                    let ctlH = CGFloat((pt.ctl ?? 0) / maxVal) * 50
                    let atlH = CGFloat((pt.atl ?? 0) / maxVal) * 50
                    
                    VStack(alignment: .center, spacing: 2) {
                        ZStack(alignment: .bottom) {
                            RoundedRectangle(cornerRadius: 1)
                                .fill(Theme.accentRose.opacity(0.6))
                                .frame(width: 4, height: max(atlH, 2))
                            RoundedRectangle(cornerRadius: 1)
                                .fill(Theme.accentBlue)
                                .frame(width: 4, height: max(ctlH, 2))
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .frame(height: 54)
            .padding(.vertical, 4)
            .background(Theme.surfaceSecondary.opacity(0.5))
            .cornerRadius(8)
        }
    }
    
    private func legendItem(color: Color, label: String) -> some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 6, height: 6)
            Text(label).foregroundColor(Theme.textMuted)
        }
    }
    
    // MARK: - 5. Health & Recovery 4-Grid Card
    private var healthRecoveryGridCard: some View {
        let h = state.dashboard.todayHealth
        // Never show made-up numbers: missing metrics render as "--".
        let rhrText = (h?.resting_heart_rate ?? state.currentUser?.resting_heart_rate).map { "\($0)" } ?? "--"
        let sleepDur = h?.sleep_duration_text ?? "--"
        let hrvText = h?.hrv_ms.map { "\($0)" } ?? "--"
        let hrvAvgText = h?.hrv_weekly_avg.map { "\($0) ms" } ?? "--"
        let sourceLabel: String = {
            switch h?.device_brand {
            case "garmin": return "Garmin"
            case "coros": return "COROS"
            default: return "Apple 健康"
            }
        }()
        
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("🫀 生理与健康基线 (\(sourceLabel))")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Spacer()
                Text("更新于: \(h?.date ?? "今日")")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.textMuted)
            }
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                // 1. Sleep
                if let score = h?.sleep_score {
                    healthTile(icon: "🛏️", name: "睡眠恢复", val: "\(score)", unit: "分", sub: "时长 \(sleepDur)", color: Theme.accentBlue)
                } else {
                    healthTile(icon: "🛏️", name: "昨晚睡眠", val: sleepDur, unit: "", sub: "睡眠时长", color: Theme.accentBlue)
                }
                
                // 2. Resting Heart Rate
                healthTile(icon: "💓", name: "静息心率 (RHR)", val: rhrText, unit: "bpm", sub: "清晨生理基线", color: Theme.accentRose)
                
                // 3. Body Battery
                if let battery = h?.body_battery_max {
                    healthTile(icon: "⚡", name: "身体电量", val: "\(battery)%", unit: "", sub: "日间电量储备", color: Theme.accentYellow)
                } else {
                    healthTile(icon: "🫁", name: "最大摄氧量", val: h?.vo2_max.map { String(format: "%.1f", $0) } ?? "--", unit: "ml/kg/min", sub: "VO₂max", color: Theme.accentYellow)
                }
                
                // 4. Night HRV
                healthTile(icon: "🫀", name: "夜间 HRV", val: hrvText, unit: "ms", sub: "周均: \(hrvAvgText)", color: Theme.accentGreen)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.border, lineWidth: 1))
    }
    
    private func healthTile(icon: String, name: String, val: String, unit: String, sub: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 4) {
                Text(icon).font(.system(size: 12))
                Text(name).font(.system(size: 11, weight: .medium)).foregroundColor(Theme.textMuted)
            }
            HStack(alignment: .lastTextBaseline, spacing: 2) {
                Text(val)
                    .font(.system(size: 20, weight: .black, design: .rounded))
                    .foregroundColor(color)
                if !unit.isEmpty {
                    Text(unit)
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
            }
            Text(sub)
                .font(.system(size: 9))
                .foregroundColor(Theme.textMuted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Theme.surfaceSecondary)
        .cornerRadius(10)
    }
    
    // MARK: - 6. Yearly Mileage & 12-Month Bar Chart
    private func yearlyMileageCard(yearly: YearlyStatsData) -> some View {
        let totalKm = yearly.total_km ?? 0.0
        let targetKm = yearly.target_year_km ?? 2400.0
        let pct = min(100.0, yearly.progress_pct ?? 0.0)
        let remain = max(0, targetKm - totalKm)
        
        let months = yearly.monthly_breakdown ?? []
        let selectedMonth = months.first(where: { $0.month == selectedMonthIndex })
        
        return VStack(alignment: .leading, spacing: 14) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("🏆 \(String(yearly.year ?? Calendar.current.component(.year, from: Date()))) 年度跑量统计")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text("年度目标 \(Int(targetKm)) km · 月均目标 \(Int(yearly.monthly_target_km ?? targetKm / 12)) km")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
                Spacer()
                Text(String(format: "%.1f%%", pct))
                    .font(.system(size: 18, weight: .black, design: .rounded))
                    .foregroundColor(Theme.primaryOrange)
            }
            
            // Year Progress Bar
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text("已累计 \(String(format: "%.1f", totalKm)) km")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                    Spacer()
                    Text("剩余 \(String(format: "%.1f", remain)) km")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                }
                
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Theme.surfaceSecondary)
                            .frame(height: 6)
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Theme.brandFill)
                            .frame(width: geo.size.width * CGFloat(pct / 100.0), height: 6)
                    }
                }
                .frame(height: 6)
            }
            
            // Month Tip
            if let sm = selectedMonth {
                HStack(spacing: 4) {
                    Text("📍")
                    Text("\(sm.month)月：跑量 ")
                        .foregroundColor(Theme.textMuted)
                    Text("\(String(format: "%.1f", sm.distance_km)) km")
                        .fontWeight(.bold)
                        .foregroundColor(Theme.primaryOrange)
                    Text(" · \(sm.runs_count) 次跑步")
                        .foregroundColor(Theme.textMuted)
                    if sm.is_current {
                        Text("(当前月)")
                            .foregroundColor(Theme.accentGreen)
                    }
                }
                .font(.system(size: 11))
                .padding(.vertical, 4)
            }
            
            // 12-Month Bar Chart
            let maxM = max(months.map { $0.distance_km }.max() ?? 400.0, 400.0)
            HStack(alignment: .bottom, spacing: 4) {
                ForEach(months) { m in
                    let isCurrent = m.is_current
                    let isSelected = m.month == selectedMonthIndex
                    let barH = CGFloat(m.distance_km / maxM) * 70
                    
                    Button(action: {
                        selectedMonthIndex = m.month
                    }) {
                        VStack(spacing: 4) {
                            if m.distance_km >= 1 {
                                Text("\(Int(m.distance_km))")
                                    .font(.system(size: 8, weight: .bold))
                                    .foregroundColor(isCurrent ? Theme.primaryOrange : Theme.textMuted)
                            } else {
                                Text(" ")
                                    .font(.system(size: 8))
                            }
                            
                            RoundedRectangle(cornerRadius: 3)
                                .fill(isCurrent ? Theme.brandFill : (isSelected ? Theme.textPrimary : (m.distance_km > 0 ? Theme.textMuted.opacity(0.45) : Theme.surfaceSecondary)))
                                .frame(height: max(barH, 3))
                            
                            Text("\(m.month)月")
                                .font(.system(size: 9, weight: isCurrent ? .bold : .regular))
                                .foregroundColor(isCurrent ? Theme.primaryOrange : Theme.textMuted)
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .frame(height: 100)
            
            // 3-Metric Tiles
            HStack(spacing: 8) {
                yearMetricTile(icon: "🏃", label: "总跑次", val: "\(yearly.total_runs ?? 0) 次")
                yearMetricTile(icon: "📅", label: "月均跑量", val: String(format: "%.1f km", yearly.avg_monthly_km ?? 0))
                yearMetricTile(icon: "🎯", label: "年终推算", val: String(format: "%.0f km", yearly.projected_year_km ?? 0))
            }
            
            // Best Month Banner
            if let bm = yearly.best_month, (bm.distance_km ?? 0) > 0 {
                HStack(spacing: 6) {
                    Text("🏅 年度最佳月份:")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                    Text("\(bm.name ?? "--") · \(String(format: "%.1f", bm.distance_km ?? 0)) km")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.textPrimary)
                    if let pace = bm.avg_pace {
                        Text("（均速 \(pace)）")
                            .font(.system(size: 10))
                            .foregroundColor(Theme.textMuted)
                    }
                }
                .padding(8)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Theme.surfaceSecondary)
                .cornerRadius(8)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.border, lineWidth: 1))
    }
    
    private func yearMetricTile(icon: String, label: String, val: String) -> some View {
        VStack(spacing: 2) {
            HStack(spacing: 2) {
                Text(icon).font(.system(size: 10))
                Text(label).font(.system(size: 10)).foregroundColor(Theme.textMuted)
            }
            Text(val)
                .font(.system(size: 13, weight: .bold, design: .rounded))
                .foregroundColor(Theme.textPrimary)
        }
        .frame(maxWidth: .infinity)
        .padding(8)
        .background(Theme.surfaceSecondary)
        .cornerRadius(8)
    }
    
    // MARK: - 7. WHOOP Three Core Rings & Recovery Assessment
    private func whoopThreeRingsCard(_ snap: WhoopSnapshot) -> some View {
        let zoneColor = Color(hex: snap.recoveryZone.hexColor)
        return HStack(spacing: 0) {
            dashboardMetricRing(
                progress: Double(snap.recoveryScore) / 100.0,
                color: zoneColor,
                value: "\(snap.recoveryScore)%",
                title: "实时恢复",
                subtitle: "晨起 \(snap.morningRecoveryScore)%"
            )
            .frame(maxWidth: .infinity)
            
            dashboardMetricRing(
                progress: snap.dayStrain / 21.0,
                color: Color(hex: "0EA5E9"),
                value: String(format: "%.1f", snap.dayStrain),
                title: "全天负荷",
                subtitle: "/ 21"
            )
            .frame(maxWidth: .infinity)
            
            dashboardMetricRing(
                progress: Double(snap.sleepPerformancePct) / 100.0,
                color: Color(hex: "8B5CF6"),
                value: "\(snap.sleepPerformancePct)%",
                title: "睡眠",
                subtitle: String(format: "%.1fh", snap.actualSleepHours)
            )
            .frame(maxWidth: .infinity)
        }
        .padding(.vertical, 16)
        .background(Theme.surface)
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.border, lineWidth: 1))
    }
    
    private func whoopRecoveryAssessmentCard(_ snap: WhoopSnapshot) -> some View {
        let zoneColor = Color(hex: snap.recoveryZone.hexColor)
        return VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 6) {
                Image(systemName: "heart.text.square.fill")
                    .font(.system(size: 13))
                    .foregroundColor(zoneColor)
                Text("恢复评估 Recovery")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Spacer()
                Button(action: { state.selectedTab = 4 }) {
                    HStack(spacing: 3) {
                        Text("完整恢复详情")
                        Image(systemName: "chevron.right")
                    }
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(Theme.primaryOrange)
                }
            }
            
            Text(snap.recoveryHeadline)
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(Theme.textPrimary)
            
            Text(snap.recoveryDetail)
                .font(.system(size: 12))
                .foregroundColor(Theme.textSecondary)
                .lineSpacing(2)
            
            HStack(spacing: 8) {
                recoveryMiniStat(title: "晨起初始恢复", value: "\(snap.morningRecoveryScore)%")
                recoveryMiniStat(title: "日间活动/压力消耗", value: "-\(snap.daytimeRecoveryDrainPct)%")
                if snap.daytimeNapBonusPct > 0 {
                    recoveryMiniStat(title: "午睡充电", value: "+\(snap.daytimeNapBonusPct)%")
                } else if let bbMax = snap.bodyBatteryMax, let bbCur = snap.bodyBatteryCurrent, bbMax > 0 {
                    recoveryMiniStat(title: "身体电量", value: "\(bbMax)→\(bbCur)")
                } else {
                    recoveryMiniStat(title: "当前实时恢复", value: "\(snap.realtimeRecoveryScore)%")
                }
            }
            
            HStack(spacing: 10) {
                recoveryBaselineTile(
                    title: "HRV",
                    value: "\(snap.hrvToday)",
                    unit: "ms",
                    baseline: "基线 \(snap.hrvBaseline)ms",
                    good: snap.hrvToday >= snap.hrvBaseline
                )
                recoveryBaselineTile(
                    title: "静息心率",
                    value: "\(snap.rhrToday)",
                    unit: "bpm",
                    baseline: "基线 \(snap.rhrBaseline)bpm",
                    good: snap.rhrToday <= snap.rhrBaseline
                )
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.border, lineWidth: 1))
    }
    
    private func dashboardMetricRing(progress: Double, color: Color, value: String, title: String, subtitle: String) -> some View {
        VStack(spacing: 8) {
            ZStack {
                Circle()
                    .stroke(color.opacity(0.15), lineWidth: 9)
                Circle()
                    .trim(from: 0, to: CGFloat(max(0.02, min(1.0, progress))))
                    .stroke(color, style: StrokeStyle(lineWidth: 9, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .animation(.easeOut(duration: 0.6), value: progress)
                VStack(spacing: 0) {
                    Text(value)
                        .font(.system(size: 18, weight: .black))
                        .foregroundColor(Theme.textPrimary)
                        .minimumScaleFactor(0.7)
                        .lineLimit(1)
                    Text(subtitle)
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundColor(Theme.textMuted)
                }
                .padding(.horizontal, 10)
            }
            .frame(width: 86, height: 86)
            Text(title)
                .font(.system(size: 12, weight: .bold))
                .foregroundColor(Theme.textSecondary)
        }
    }
    
    private func recoveryMiniStat(title: String, value: String) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(size: 15, weight: .heavy))
                .foregroundColor(Theme.textPrimary)
            Text(title)
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(Theme.surfaceSecondary)
        .cornerRadius(8)
    }
    
    private func recoveryBaselineTile(title: String, value: String, unit: String, baseline: String, good: Bool) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 10, weight: .semibold))
                .foregroundColor(Theme.textMuted)
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text(value)
                    .font(.system(size: 20, weight: .heavy))
                    .foregroundColor(Theme.textPrimary)
                Text(unit)
                    .font(.system(size: 10))
                    .foregroundColor(Theme.textMuted)
                Image(systemName: good ? "arrow.up.right" : "arrow.down.right")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(good ? Theme.accentGreen : Color(hex: "F43F5E"))
            }
            Text(baseline)
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Theme.surfaceSecondary)
        .cornerRadius(10)
    }
}
