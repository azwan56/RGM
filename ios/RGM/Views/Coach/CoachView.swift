import SwiftUI

struct CoachView: View {
    @EnvironmentObject var state: AppState
    
    // Tab switcher: "plan" vs "chat"
    @State private var activeTab: String = "chat"
    @State private var selectedWeekIndex: Int? = nil
    @State private var isWeeklyPreviewExpanded: Bool = true
    @State private var inputText: String = ""
    @State private var isDiagnosisExpanded: Bool = false
    @State private var showCitationsSheet: Bool = false
    @State private var dismissedAlertIds: Set<String> = []
    
    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            
            VStack(spacing: 0) {
                // 1. Coach Header
                coachHeader
                    .padding(.top, 8)
                
                // 2. Tab Bar: 科学周期课表 vs Canova 专项诊断
                coachTabBar
                
                // 3. Tab Content
                if activeTab == "plan" {
                    planTabContent
                } else {
                    chatTabContent
                }
            }
        }
        .sheet(isPresented: $showCitationsSheet) {
            ScientificCitationsSheet()
        }
    }
    
    // MARK: - Coach Header
    private var coachHeader: some View {
        HStack(spacing: 10) {
            ZStack {
                Circle()
                    .fill(LinearGradient(colors: [Theme.brandFill, Theme.brandGradientEnd], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 36, height: 36)
                Text("RC")
                    .font(.system(size: 13, weight: .black))
                    .foregroundColor(Theme.onBrand)
            }
            
            VStack(alignment: .leading, spacing: 1) {
                Text("Canova 教练")
                    .font(.system(size: 15, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                    .lineLimit(1)
                Text("专项化哲学 · 动态 TSB")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.textMuted)
                    .lineLimit(1)
            }
            .layoutPriority(1)
            
            Spacer(minLength: 4)
            
            Button(action: { showCitationsSheet = true }) {
                HStack(spacing: 3) {
                    Image(systemName: "book.pages.fill")
                    Text("文献")
                }
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(Theme.primaryOrange)
                .padding(.horizontal, 7)
                .padding(.vertical, 6)
                .background(Theme.brandTint)
                .cornerRadius(12)
            }
            
            Button(action: {
                Task {
                    await state.runCoachAnalysis()
                    activeTab = "chat"
                }
            }) {
                HStack(spacing: 4) {
                    if state.isAnalyzingCoach {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: Theme.onBrand))
                            .scaleEffect(0.7)
                    } else {
                        Text("⚡")
                    }
                    Text(state.isAnalyzingCoach ? "推理中..." : "专项推理")
                        .font(.system(size: 11, weight: .bold))
                        .lineLimit(1)
                }
                .foregroundColor(Theme.onBrand)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Theme.brandFill)
                .cornerRadius(16)
            }
            .disabled(state.isAnalyzingCoach)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Theme.surface)
        .overlay(Rectangle().frame(height: 1).foregroundColor(Theme.border), alignment: .bottom)
    }
    
    // MARK: - Tab Bar
    private var coachTabBar: some View {
        HStack(spacing: 8) {
            Button(action: { activeTab = "plan" }) {
                HStack(spacing: 4) {
                    Text("📅")
                    Text("科学周期课表")
                        .font(.system(size: 13, weight: activeTab == "plan" ? .bold : .medium))
                }
                .foregroundColor(activeTab == "plan" ? Theme.onBrand : Theme.textMuted)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(activeTab == "plan" ? Theme.brandFill : Color.clear)
                .cornerRadius(8)
            }
            
            Button(action: { activeTab = "chat" }) {
                HStack(spacing: 4) {
                    Text("⚡")
                    Text("Canova 专项诊断与对话")
                        .font(.system(size: 13, weight: activeTab == "chat" ? .bold : .medium))
                }
                .foregroundColor(activeTab == "chat" ? Theme.onBrand : Theme.textMuted)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(activeTab == "chat" ? Theme.brandFill : Color.clear)
                .cornerRadius(8)
            }
        }
        .padding(4)
        .background(Theme.surface)
        .overlay(Rectangle().frame(height: 1).foregroundColor(Theme.border), alignment: .bottom)
    }
    
    // MARK: - Plan Tab Content
    private var planTabContent: some View {
        let weeks = state.activePlan?.schedule_data?.weeks ?? []
        let activeWeekIdx = selectedWeekIndex ?? currentWeekPlan.week_index ?? state.activePlan?.current_week_index ?? 1
        let displayedWeek = weeks.first(where: { $0.week_index == activeWeekIdx }) ?? currentWeekPlan
        
        return ScrollView {
            VStack(spacing: 16) {
                // 1. Active Plan Overview Card
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(state.activePlan?.title ?? "Canova 科学周期训练计划")
                                .font(.system(size: 16, weight: .bold))
                                .foregroundColor(Theme.textPrimary)
                            Text("执行中 · \(state.activePlan?.weeks_count ?? 12)周宏观周期 · 当前第 \(state.activePlan?.current_week_index ?? displayedWeek.week_index ?? 1) 周")
                                .font(.system(size: 11))
                                .foregroundColor(Theme.accentGreen)
                        }
                        Spacer()
                    }
                    
                    HStack(spacing: 12) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("目标赛事")
                                .font(.system(size: 10))
                                .foregroundColor(Theme.textMuted)
                            Text(state.activePlan?.target_race_name ?? state.userRaces.first?.name ?? "未设置")
                                .font(.system(size: 14, weight: .bold))
                                .foregroundColor(Theme.primaryOrange)
                        }
                        
                        Divider().frame(height: 24).background(Theme.border)
                        
                        VStack(alignment: .leading, spacing: 2) {
                            Text("赛事日期 / 目标")
                                .font(.system(size: 10))
                                .foregroundColor(Theme.textMuted)
                            Text(state.activePlan?.target_date ?? state.activePlan?.target_time ?? "备赛推进中")
                                .font(.system(size: 14, weight: .bold))
                                .foregroundColor(Theme.textPrimary)
                        }
                    }
                    
                    if let summary = state.activePlan?.overview_summary, !summary.isEmpty {
                        Text(summary)
                            .font(.system(size: 11.5))
                            .foregroundColor(Theme.textSecondary)
                            .lineSpacing(2)
                    }
                }
                .padding(16)
                .background(Theme.surface)
                .cornerRadius(14)
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
                
                // 2. Weekly Training Plan Section (本周训练计划)
                weeklyTrainingScheduleCard(displayedWeek: displayedWeek, allWeeks: weeks)
                
                // 3. Periodization 4 Phases
                VStack(alignment: .leading, spacing: 12) {
                    Text("Canova 周期化阶段架构")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    
                    let curW = state.activePlan?.current_week_index ?? 7
                    VStack(spacing: 8) {
                        phaseRow(title: "基础期 (Fundamental) · 第1-4周", desc: "有氧容量构建、毛细血管新生与骨骼肌适应", status: curW > 4 ? "已完成" : "当前阶段", color: curW > 4 ? Theme.accentGreen : Theme.primaryOrange)
                        phaseRow(title: "专项准备期 (Special) · 第5-6周", desc: "专项有氧耐力发展、乳酸清除能力与爬升/门槛强化", status: curW > 6 ? "已完成" : (curW >= 5 ? "当前阶段" : "待开启"), color: curW > 6 ? Theme.accentGreen : (curW >= 5 ? Theme.primaryOrange : Theme.textMuted))
                        phaseRow(title: "专项突破期 (Specific) · 第7-10周", desc: "马拉松/越野专项配速耐受性与大负荷超量恢复", status: curW > 10 ? "已完成" : (curW >= 7 ? "当前阶段" : "待开启"), color: curW > 10 ? Theme.accentGreen : (curW >= 7 ? Theme.primaryOrange : Theme.textMuted))
                        phaseRow(title: "减量调整期 (Taper) · 第11-12周", desc: "急性能量超量补偿，TSB 冲顶迎接比赛", status: curW >= 11 ? "当前阶段" : "待开启", color: curW >= 11 ? Theme.primaryOrange : Theme.textMuted)
                    }
                }
                .padding(16)
                .background(Theme.surface)
                .cornerRadius(14)
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
            }
            .padding(16)
            .padding(.bottom, 100)
        }
    }
    
    // MARK: - Weekly Training Schedule Card & Helpers
    private var todayDateString: String {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Asia/Shanghai") ?? .current
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: Date())
    }
    
    private var currentWeekPlan: PlanWeekItem {
        let todayKey = todayDateString
        if let weeks = state.activePlan?.schedule_data?.weeks, !weeks.isEmpty {
            if let matchByDate = weeks.first(where: { w in
                (w.days ?? []).contains(where: { ($0.date ?? "") == todayKey })
            }) {
                return matchByDate
            }
            if let cwIdx = state.activePlan?.current_week_index,
               let matchByIdx = weeks.first(where: { $0.week_index == cwIdx }) {
                return matchByIdx
            }
            return weeks.first!
        }
        return fallbackCurrentWeekPlan
    }
    
    private var fallbackCurrentWeekPlan: PlanWeekItem {
        let wp = state.effectiveWeeklyProgress
        let breakdown = wp.daily_breakdown ?? []
        let targetKm = wp.target_week_km ?? 50.0
        let templates: [(type: String, title: String, ratio: Double, pace: String, hr: String, desc: String)] = [
            ("rest", "完全休息 / 泡沫轴筋膜放松", 0.0, "—", "—", "彻底放松下肢肌群，保证充足睡眠促进超量恢复。"),
            ("easy_run", "低心率基础有氧跑 (Zone 2)", 0.20, "5:45 - 6:15 /km", "心率 130-142 bpm", "稳态有氧巡航，结束后完成 4×100m 轻快跨步跑激活神经。"),
            ("easy_run", "排酸恢复慢跑 + 核心力量", 0.14, "6:00 - 6:30 /km", "心率 < 135 bpm", "轻松排酸慢跑，跑后进行 15 分钟臀中肌与核心抗阻训练。"),
            ("special", "Canova 混氧门槛 / 爬升专项课", 0.24, "4:55 - 5:15 /km", "心率 150-162 bpm", "热身 2km + 专项门槛巡航或坡道抗阻训练 + 冷身 2km。"),
            ("rest", "主动恢复 / 周末大课前蓄能", 0.0, "—", "—", "为周末长距离储备肌糖原，早睡并注意电解质水合。"),
            ("easy_run", "周末前唤醒轻松跑 (Shakeout)", 0.12, "5:50 - 6:15 /km", "心率 128-138 bpm", "轻快活动心肺与踝膝关节，不堆积疲劳。"),
            ("long_run", "周末长距离专项耐力跑 (LSD)", 0.30, "5:45 渐进至 5:05 /km", "心率 135-155 bpm", "前段保持低心率稳态，后三分之一渐进提速，每 45 分钟演练能量胶补给。")
        ]
        var days: [PlanDayWorkout] = []
        for idx in 0..<7 {
            let tpl = templates[idx]
            let bDay = idx < breakdown.count ? breakdown[idx] : nil
            let dStr = bDay?.full_date
            let dayName = bDay?.day_name ?? ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][idx]
            let actualKm = bDay?.distance_km ?? 0.0
            let plannedKm = ((targetKm * tpl.ratio) * 10).rounded() / 10.0
            days.append(PlanDayWorkout(
                day_of_week: dayName,
                date: dStr,
                day_index: idx,
                workout_type: tpl.type,
                title: tpl.title,
                distance_km: plannedKm,
                target_pace: tpl.pace,
                target_hr_zone: tpl.hr,
                description: tpl.desc,
                completed: actualKm > 0,
                coach_notes: nil,
                actual_distance_km: actualKm > 0 ? actualKm : nil,
                actual_pace: nil,
                actual_heartrate: nil,
                actual_execution_text: nil,
                recovery_pct: nil,
                strain_score: nil
            ))
        }
        return PlanWeekItem(
            week_index: wp.week_number ?? 1,
            week_title: "\(wp.week_label ?? "本周") · Canova 专项周期课表",
            phase: state.coachAnalysis?.periodization_phase ?? "专项推进期",
            weekly_mileage_km: targetKm,
            key_focus: "严格遵循 80/20 极化原则，保质完成周中门槛课与周末长距离耐力课",
            days: days,
            week_summary: nil
        )
    }
    
    private func weeklyTrainingScheduleCard(displayedWeek: PlanWeekItem, allWeeks: [PlanWeekItem]) -> some View {
        let curWeekIdx = currentWeekPlan.week_index ?? state.activePlan?.current_week_index ?? 1
        let isCurrentWeek = (displayedWeek.week_index == curWeekIdx)
        let plannedKm = displayedWeek.weekly_mileage_km ?? state.effectiveWeeklyProgress.target_week_km ?? 50.0
        let actualKm: Double = {
            if isCurrentWeek {
                return state.effectiveWeeklyProgress.current_week_km ?? displayedWeek.week_summary?.actual_mileage_km ?? 0.0
            }
            return displayedWeek.week_summary?.actual_mileage_km ?? 0.0
        }()
        
        return VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .center) {
                HStack(spacing: 6) {
                    Text("📋 本周训练计划")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    if isCurrentWeek {
                        Text("当前周")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(Theme.onBrand)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Theme.brandFill)
                            .cornerRadius(4)
                    }
                }
                Spacer()
                Text("已跑 \(String(format: "%.1f", actualKm)) / 计划 \(String(format: "%.1f", plannedKm)) km")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(Theme.primaryOrange)
            }
            
            // Week Selector Strip (if multi-week schedule exists)
            if allWeeks.count > 1 {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(allWeeks) { w in
                            let wIdx = w.week_index ?? 1
                            let isSelected = (displayedWeek.week_index == wIdx)
                            let isNow = (wIdx == curWeekIdx)
                            Button(action: {
                                withAnimation(.easeInOut(duration: 0.15)) {
                                    selectedWeekIndex = wIdx
                                }
                            }) {
                                HStack(spacing: 3) {
                                    Text("第\(wIdx)周")
                                        .font(.system(size: 11, weight: isSelected ? .bold : .medium))
                                    if isNow {
                                        Circle()
                                            .fill(isSelected ? Theme.onBrand : Theme.accentGreen)
                                            .frame(width: 5, height: 5)
                                    }
                                }
                                .foregroundColor(isSelected ? Theme.onBrand : Theme.textSecondary)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(isSelected ? Theme.brandFill : Theme.surfaceSecondary)
                                .cornerRadius(8)
                            }
                        }
                    }
                }
            }
            
            // Week Title & Key Focus Banner
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(displayedWeek.week_title ?? "本周专项训练课表")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Spacer()
                    if let phase = displayedWeek.phase, !phase.isEmpty {
                        Text(phase)
                            .font(.system(size: 9.5, weight: .semibold))
                            .foregroundColor(Theme.accentGreen)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Theme.accentGreen.opacity(0.12))
                            .cornerRadius(4)
                    }
                }
                if let focus = displayedWeek.key_focus, !focus.isEmpty {
                    Text("🎯 本周重点：\(focus)")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textSecondary)
                        .lineSpacing(2)
                }
            }
            .padding(10)
            .background(Theme.surfaceSecondary)
            .cornerRadius(10)
            
            // 7-Day Workout List (Mon - Sun)
            VStack(spacing: 10) {
                ForEach(displayedWeek.days ?? []) { day in
                    planDayRow(day)
                }
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private func planDayRow(_ day: PlanDayWorkout) -> some View {
        let todayKey = todayDateString
        let isToday = (day.date == todayKey)
        let wType = (day.workout_type ?? "easy_run").lowercased()
        let isRest = wType == "rest" || (day.distance_km ?? 0) <= 0
        
        // Also check if user logged a run on this date in recentActivities
        let dayRunKm: Double = {
            if let actual = day.actual_distance_km, actual > 0 { return actual }
            guard let d = day.date, !d.isEmpty else { return 0.0 }
            return state.dashboard.recentActivities
                .filter { ($0.start_time ?? "").hasPrefix(d) }
                .map { $0.distanceKm }
                .reduce(0.0, +)
        }()
        let isCompleted = (day.completed == true) || dayRunKm > 0
        
        let badgeInfo: (label: String, color: Color) = {
            if isRest { return ("休息恢复", Theme.textMuted) }
            if wType.contains("long") { return ("长距离专项", Color(hex: "8B5CF6")) }
            if wType.contains("trail") || wType.contains("climb") { return ("山地爬升", Theme.primaryOrange) }
            if wType.contains("interval") || wType.contains("tempo") || wType.contains("special") { return ("门槛/间歇", Color(hex: "F43F5E")) }
            return ("有氧耐力", Color(hex: "0EA5E9"))
        }()
        
        let shortDateText: String = {
            guard let d = day.date, d.count >= 10 else { return "" }
            return String(d.suffix(5)).replacingOccurrences(of: "-", with: "/")
        }()
        
        return VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Text("\(day.day_of_week ?? "训练日") \(shortDateText)")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(isToday ? Theme.primaryOrange : Theme.textPrimary)
                
                if isToday {
                    Text("今日")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 1.5)
                        .background(Theme.primaryOrange)
                        .cornerRadius(4)
                }
                
                Text(badgeInfo.label)
                    .font(.system(size: 9.5, weight: .bold))
                    .foregroundColor(badgeInfo.color)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(badgeInfo.color.opacity(0.14))
                    .cornerRadius(4)
                
                Spacer()
                
                if isCompleted && !isRest {
                    Text(dayRunKm > 0 ? String(format: "✓ 已完成 %.1fkm", dayRunKm) : "✓ 已完成")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(Theme.accentGreen)
                } else if let dist = day.distance_km, dist > 0 {
                    Text(String(format: "%.1f km", dist))
                        .font(.system(size: 13, weight: .black, design: .rounded))
                        .foregroundColor(Theme.primaryOrange)
                } else {
                    Text("休息")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.textMuted)
                }
            }
            
            Text(day.title ?? "训练课表")
                .font(.system(size: 13, weight: .bold))
                .foregroundColor(Theme.textPrimary)
            
            if let desc = day.description, !desc.isEmpty {
                Text(desc)
                    .font(.system(size: 11))
                    .foregroundColor(Theme.textSecondary)
                    .lineSpacing(1.5)
            }
            
            if !isRest {
                HStack(spacing: 12) {
                    if let pace = day.target_pace, !pace.isEmpty, pace != "—" {
                        Text("⏱️ 配速: \(pace)")
                            .font(.system(size: 10, weight: .medium))
                            .foregroundColor(Theme.accentGreen)
                    }
                    if let hr = day.target_hr_zone, !hr.isEmpty, hr != "—" {
                        Text("💓 \(hr)")
                            .font(.system(size: 10, weight: .medium))
                            .foregroundColor(Theme.textMuted)
                    }
                }
            }
        }
        .padding(12)
        .background(isToday ? Theme.primaryOrange.opacity(0.08) : Theme.surfaceSecondary)
        .cornerRadius(10)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(isToday ? Theme.primaryOrange.opacity(0.6) : Color.clear, lineWidth: 1.2)
        )
    }
    
    // Compact Weekly Training Plan Card for the Chat/Diagnosis Tab
    private var weeklyPlanChatSummaryCard: some View {
        let week = currentWeekPlan
        let days = week.days ?? []
        let todayKey = todayDateString
        let plannedKm = week.weekly_mileage_km ?? state.effectiveWeeklyProgress.target_week_km ?? 50.0
        let actualKm = state.effectiveWeeklyProgress.current_week_km ?? 0.0
        
        return VStack(alignment: .leading, spacing: 10) {
            HStack {
                HStack(spacing: 6) {
                    Text("📅 本周训练计划")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text("已跑 \(String(format: "%.1f", actualKm))/\(String(format: "%.0f", plannedKm))km")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Theme.brandTint)
                        .cornerRadius(4)
                }
                Spacer()
                Button(action: {
                    withAnimation { activeTab = "plan" }
                }) {
                    HStack(spacing: 2) {
                        Text("完整周课表")
                        Image(systemName: "chevron.right")
                    }
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundColor(Theme.primaryOrange)
                }
            }
            
            // 7-day compact pills
            if !days.isEmpty {
                HStack(spacing: 5) {
                    ForEach(days) { d in
                        let isToday = (d.date == todayKey)
                        let km = d.distance_km ?? 0.0
                        let isRest = (d.workout_type == "rest" || km <= 0)
                        VStack(spacing: 3) {
                            Text((d.day_of_week ?? "").replacingOccurrences(of: "周", with: ""))
                                .font(.system(size: 9.5, weight: isToday ? .bold : .medium))
                                .foregroundColor(isToday ? Theme.primaryOrange : Theme.textMuted)
                            Text(isRest ? "休" : String(format: "%.0fk", km))
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(isRest ? Theme.textMuted : (isToday ? .white : Theme.textPrimary))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 5)
                                .background(isToday ? Theme.primaryOrange : (isRest ? Theme.surfaceSecondary.opacity(0.6) : Theme.surfaceSecondary))
                                .cornerRadius(6)
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
            }
            
            if let todayItem = days.first(where: { $0.date == todayKey }) ?? days.first {
                HStack(spacing: 6) {
                    Text("今日课表：\(todayItem.title ?? "有氧训练")")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.textSecondary)
                        .lineLimit(1)
                    Spacer()
                    if let dist = todayItem.distance_km, dist > 0 {
                        Text(String(format: "%.1f km", dist))
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(Theme.accentGreen)
                    }
                }
            }
        }
        .padding(12)
        .background(Theme.surface)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
    }
    
    private func phaseRow(title: String, desc: String, status: String, color: Color) -> some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Theme.textPrimary)
                Text(desc)
                    .font(.system(size: 10))
                    .foregroundColor(Theme.textMuted)
            }
            Spacer()
            Text(status)
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(color)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(color.opacity(0.12))
                .cornerRadius(4)
        }
        .padding(10)
        .background(Theme.surfaceSecondary)
        .cornerRadius(8)
    }
    
    // MARK: - Chat & Diagnosis Tab Content
    private static let topAnchorId = "coach_top_anchor"
    
    private var chatTabContent: some View {
        ScrollViewReader { proxy in
            VStack(spacing: 0) {
                // Slim pinned status bar (one line) – tapping jumps back to the alerts/diagnosis at the top
                if !visibleAlerts.isEmpty || state.coachAnalysis != nil {
                    pinnedStatusBar(proxy: proxy)
                }
                
                // Everything else scrolls together so the conversation can use the full height
                ScrollView {
                    VStack(spacing: 12) {
                        Color.clear.frame(height: 0).id(Self.topAnchorId)
                        
                        if !visibleAlerts.isEmpty {
                            proactiveAlertsStrip
                        }
                        
                        if let a = state.coachAnalysis {
                            diagnosisCard(a)
                        }
                        
                        // Weekly Training Plan Summary Card in Chat View
                        weeklyPlanChatSummaryCard
                        
                        ForEach(state.coachMessages) { msg in
                            messageBubble(msg)
                                .id(msg.id)
                        }
                        
                        if state.isCoachThinking {
                            HStack {
                                Text("🤖 Canova 教练正在结合您的 CTL/ATL 深度推演...")
                                    .font(.system(size: 12))
                                    .foregroundColor(Theme.textSecondary)
                                    .padding(10)
                                    .background(Theme.surface)
                                    .cornerRadius(12)
                                Spacer()
                            }
                        }
                    }
                    .padding(16)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: state.coachMessages.count) { _ in
                    if let last = state.coachMessages.last {
                        withAnimation {
                            proxy.scrollTo(last.id, anchor: .bottom)
                        }
                    }
                }
                
                // Quick Prompts
                quickPromptsScroll
                
                // Input Bar
                chatInputBar
            }
        }
    }
    
    private func pinnedStatusBar(proxy: ScrollViewProxy) -> some View {
        let snap = state.whoopSnapshot
        let zoneColor = Color(hex: snap.recoveryZone.hexColor)
        return Button(action: {
            withAnimation { proxy.scrollTo(Self.topAnchorId, anchor: .top) }
        }) {
            HStack(spacing: 8) {
                Circle().fill(zoneColor).frame(width: 7, height: 7)
                Text("恢复 \(snap.recoveryScore)% · Strain \(String(format: "%.1f", snap.dayStrain))")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                if !visibleAlerts.isEmpty {
                    Text("\(visibleAlerts.count) 条提醒")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color(hex: "F43F5E"))
                        .cornerRadius(8)
                }
                if let phase = state.coachAnalysis?.periodization_phase {
                    Text(phase)
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundColor(Theme.accentGreen)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
                Image(systemName: "arrow.up.to.line")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(Theme.textMuted)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 7)
            .background(Theme.surface)
            .overlay(Rectangle().frame(height: 1).foregroundColor(Theme.border), alignment: .bottom)
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    private func diagnosisCard(_ a: CoachAnalysisResponse) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Button(action: {
                withAnimation(.easeInOut(duration: 0.2)) {
                    isDiagnosisExpanded.toggle()
                }
            }) {
                HStack {
                    Text("⚡ Canova 专项诊断")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                    if let phase = a.periodization_phase {
                        Text(phase)
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundColor(Theme.accentGreen)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Theme.accentGreen.opacity(0.12))
                            .cornerRadius(4)
                    }
                    Spacer()
                    Text(isDiagnosisExpanded ? "收起" : "展开详情")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                    Image(systemName: isDiagnosisExpanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
            }
            
            if let sum = a.summary {
                Text(sum)
                    .font(.system(size: 12))
                    .foregroundColor(Theme.textPrimary)
                    .lineLimit(isDiagnosisExpanded ? nil : 2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            
            if isDiagnosisExpanded {
                if let suggestions = a.key_suggestions, !suggestions.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("💡 关键建议：")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(Theme.primaryOrange)
                        ForEach(suggestions, id: \.self) { s in
                            Text("• \(s)")
                                .font(.system(size: 11))
                                .foregroundColor(Theme.textSecondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    .padding(.top, 4)
                }
                
                if let rec = a.recovery_advice {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("🌿 恢复指导：")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(Theme.accentGreen)
                        Text(rec)
                            .font(.system(size: 11))
                            .foregroundColor(Theme.textSecondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.top, 2)
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surface)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
    }
    
    // MARK: - Proactive Alerts
    private var visibleAlerts: [ProactiveCoachAlert] {
        state.proactiveAlerts.filter { !dismissedAlertIds.contains($0.id) }
    }
    
    @ViewBuilder
    private var proactiveAlertsStrip: some View {
        if !visibleAlerts.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    Circle().fill(Color(hex: "F43F5E")).frame(width: 7, height: 7)
                    Text("教练主动提醒 · \(visibleAlerts.count) 条")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Spacer()
                    Button(action: { state.selectedTab = 4 }) {
                        HStack(spacing: 2) {
                            Text("恢复详情")
                            Image(systemName: "chevron.right")
                        }
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.primaryOrange)
                    }
                }
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 10) {
                        ForEach(visibleAlerts) { alert in
                            alertCard(alert)
                        }
                    }
                }
            }
        }
    }
    
    private func severityColor(_ s: String) -> Color {
        switch s {
        case "critical": return Color(hex: "F43F5E")
        case "warning": return Color(hex: "F59E0B")
        case "optimal": return Theme.accentGreen
        default: return Color(hex: "0EA5E9")
        }
    }
    
    private func alertCard(_ alert: ProactiveCoachAlert) -> some View {
        let color = severityColor(alert.severity)
        return VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 5) {
                Image(systemName: alert.icon)
                    .font(.system(size: 11))
                    .foregroundColor(color)
                Text(alert.category)
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(color)
                Spacer()
                Button(action: {
                    withAnimation { _ = dismissedAlertIds.insert(alert.id) }
                }) {
                    Image(systemName: "xmark")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(Theme.textMuted)
                }
            }
            Text(alert.title)
                .font(.system(size: 12, weight: .bold))
                .foregroundColor(Theme.textPrimary)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
            Text(alert.message)
                .font(.system(size: 10.5))
                .foregroundColor(Theme.textSecondary)
                .lineLimit(3)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
            HStack {
                Text(alert.metricTag)
                    .font(.system(size: 9, weight: .semibold))
                    .foregroundColor(Theme.textMuted)
                    .lineLimit(1)
                Spacer()
                Button(action: {
                    Task { await state.sendCoachMessage(alert.actionPrompt) }
                }) {
                    Text(alert.actionLabel)
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 5)
                        .background(color)
                        .cornerRadius(6)
                        .lineLimit(1)
                }
                .disabled(state.isCoachThinking)
            }
        }
        .padding(10)
        .frame(width: 270, height: 150, alignment: .topLeading)
        .background(color.opacity(0.08))
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(color.opacity(0.35), lineWidth: 1))
    }
    
    private func messageBubble(_ msg: CoachMessage) -> some View {
        HStack(alignment: .top, spacing: 8) {
            if msg.isUser {
                Spacer()
                Text(msg.text)
                    .font(.system(size: 14))
                    .foregroundColor(Theme.onBrand)
                    .padding(12)
                    .background(Theme.brandFill)
                    .cornerRadius(14)
                    .frame(maxWidth: 300, alignment: .trailing)
            } else {
                Text(msg.text)
                    .font(.system(size: 13.5))
                    .foregroundColor(Theme.textPrimary)
                    .padding(12)
                    .background(Theme.surface)
                    .cornerRadius(14)
                    .overlay(
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(Theme.border, lineWidth: 1)
                    )
                    .frame(maxWidth: 330, alignment: .leading)
                Spacer()
            }
        }
    }
    
    private var quickPromptsScroll: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                promptChip("今天恢复度 \(state.whoopSnapshot.recoveryScore)%，该怎么练？")
                promptChip("分析我最近的训练负荷与TSB")
                promptChip("今晚怎么睡能提升明天HRV？")
                promptChip("这周末该跑多长距离？")
                promptChip("如何提升乳酸阈值配速？")
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
        .background(Theme.surface.opacity(0.5))
    }
    
    private func promptChip(_ text: String) -> some View {
        Button(action: {
            Task {
                await state.sendCoachMessage(text)
            }
        }) {
            Text(text)
                .font(.system(size: 12))
                .foregroundColor(Theme.textSecondary)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Theme.surface)
                .cornerRadius(14)
                .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
        }
    }
    
    private var chatInputBar: some View {
        VStack(spacing: 4) {
            HStack(spacing: 10) {
                TextField("向 Canova 教练请教专项训练与体能...", text: $inputText)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 10)
                    .background(Theme.surfaceSecondary)
                    .cornerRadius(10)
                    .foregroundColor(Theme.textPrimary)
                
                Button(action: {
                    let msg = inputText
                    inputText = ""
                    Task {
                        await state.sendCoachMessage(msg)
                    }
                }) {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.system(size: 30))
                        .foregroundColor(inputText.isEmpty ? Theme.textMuted : Theme.primaryOrange)
                }
                .disabled(inputText.isEmpty || state.isCoachThinking)
            }
            
            Button(action: { showCitationsSheet = true }) {
                HStack(spacing: 4) {
                    Image(systemName: "exclamationmark.shield")
                    Text("AI 建议仅供运动参考 · 查看理论与免责 ➔")
                        .lineLimit(1)
                }
                .font(.system(size: 9.5))
                .foregroundColor(Theme.textMuted)
            }
        }
        .padding(.horizontal, 12)
        .padding(.top, 8)
        .padding(.bottom, 6)
        .background(Theme.surface)
        .overlay(Rectangle().frame(height: 1).foregroundColor(Theme.border), alignment: .top)
    }
}
