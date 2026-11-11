import SwiftUI

// MARK: - WHOOP-Style Recovery Module (恢复 · 负荷 · 睡眠 · 习惯日志)

struct RecoveryView: View {
    @EnvironmentObject var state: AppState
    @State private var showAllInsights: Bool = false
    
    var body: some View {
        let snap = state.whoopSnapshot
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: 16) {
                        headerSection(snap)
                        if !snap.missingInputs.isEmpty {
                            dataGapBanner(snap)
                        }
                        ringsSection(snap)
                        recoveryCard(snap)
                        strainCard(snap)
                        daytimeDynamicsCard(snap)
                        sleepCoachCard(snap)
                        MorningBriefingSettingsCard()
                        stressHealthspanCard(snap)
                        journalCard
                        insightsCard
                        askCoachButton(snap)
                        disclaimer
                    }
                    .padding(16)
                    .padding(.bottom, 40)
                }
                .refreshable {
                    await state.performPrePushWatchSync()
                }
            }
            .navigationBarHidden(true)
        }
        .navigationViewStyle(.stack)
    }
    
    // MARK: Header
    
    private func headerSection(_ snap: WhoopSnapshot) -> some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 4) {
                Text(Self.todayLabel)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Theme.textMuted)
                Text("身体准备好了吗？")
                    .font(.system(size: 24, weight: .black))
                    .foregroundColor(Theme.textPrimary)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                HStack(spacing: 4) {
                    Image(systemName: "applewatch.radiowaves.left.and.right")
                    Text(snap.dataSourceLabel)
                }
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(Theme.textSecondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 5)
                .background(Theme.surfaceSecondary)
                .cornerRadius(10)
                
                Text(snap.lastUpdatedText)
                    .font(.system(size: 9, weight: .medium))
                    .foregroundColor(Theme.textMuted)
            }
        }
        .padding(.top, 8)
    }
    
    private func dataGapBanner(_ snap: WhoopSnapshot) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "exclamationmark.circle.fill")
                .foregroundColor(Color(hex: "F59E0B"))
            Text("暂缺 \(snap.missingInputs.joined(separator: "、")) 数据，相关评分使用默认基线估算。请佩戴手表入睡并同步数据，以获得个人化结果。")
                .font(.system(size: 11))
                .foregroundColor(Theme.textSecondary)
                .lineSpacing(2)
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(hex: "F59E0B").opacity(0.12))
        .cornerRadius(10)
    }
    
    // MARK: Three Core Rings
    
    private func ringsSection(_ snap: WhoopSnapshot) -> some View {
        HStack(spacing: 0) {
            MetricRing(
                progress: Double(snap.recoveryScore) / 100.0,
                color: Color(hex: snap.recoveryZone.hexColor),
                value: "\(snap.recoveryScore)%",
                title: "实时恢复",
                subtitle: "晨起 \(snap.morningRecoveryScore)%"
            )
            .frame(maxWidth: .infinity)
            MetricRing(
                progress: snap.dayStrain / 21.0,
                color: Color(hex: "0EA5E9"),
                value: String(format: "%.1f", snap.dayStrain),
                title: "全天负荷",
                subtitle: "/ 21"
            )
            .frame(maxWidth: .infinity)
            MetricRing(
                progress: Double(snap.sleepPerformancePct) / 100.0,
                color: Color(hex: "8B5CF6"),
                value: "\(snap.sleepPerformancePct)%",
                title: "睡眠",
                subtitle: String(format: "%.1fh", snap.actualSleepHours)
            )
            .frame(maxWidth: .infinity)
        }
        .padding(.vertical, 18)
        .background(Theme.surface)
        .cornerRadius(16)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.border, lineWidth: 1))
    }
    
    // MARK: Recovery Detail
    
    private func recoveryCard(_ snap: WhoopSnapshot) -> some View {
        let zoneColor = Color(hex: snap.recoveryZone.hexColor)
        return CardContainer(icon: "heart.text.square.fill", title: "恢复评估 Recovery", tint: zoneColor) {
            VStack(alignment: .leading, spacing: 10) {
                Text(snap.recoveryHeadline)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Text(snap.recoveryDetail)
                    .font(.system(size: 12))
                    .foregroundColor(Theme.textSecondary)
                    .lineSpacing(2)
                
                HStack(spacing: 8) {
                    miniStat(title: "晨起初始恢复", value: "\(snap.morningRecoveryScore)%")
                    miniStat(title: "日间活动/压力消耗", value: "-\(snap.daytimeRecoveryDrainPct)%")
                    if snap.daytimeNapBonusPct > 0 {
                        miniStat(title: "午睡充电", value: "+\(snap.daytimeNapBonusPct)%")
                    } else if let bbMax = snap.bodyBatteryMax, let bbCur = snap.bodyBatteryCurrent, bbMax > 0 {
                        miniStat(title: "身体电量", value: "\(bbMax)→\(bbCur)")
                    } else {
                        miniStat(title: "当前实时恢复", value: "\(snap.realtimeRecoveryScore)%")
                    }
                }
                
                HStack(spacing: 10) {
                    baselineTile(title: "HRV", value: "\(snap.hrvToday)", unit: "ms",
                                 baseline: "基线 \(snap.hrvBaseline)ms",
                                 good: snap.hrvToday >= snap.hrvBaseline)
                    baselineTile(title: "静息心率", value: "\(snap.rhrToday)", unit: "bpm",
                                 baseline: "基线 \(snap.rhrBaseline)bpm",
                                 good: snap.rhrToday <= snap.rhrBaseline)
                }
            }
        }
    }
    
    private func baselineTile(title: String, value: String, unit: String, baseline: String, good: Bool) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 10, weight: .semibold))
                .foregroundColor(Theme.textMuted)
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text(value)
                    .font(.system(size: 22, weight: .heavy))
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
    
    // MARK: Strain
    
    private func strainCard(_ snap: WhoopSnapshot) -> some View {
        CardContainer(icon: "flame.fill", title: "全天负荷 Strain", tint: Color(hex: "0EA5E9")) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text(snap.strainStateLabel)
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Spacer()
                    Text("目标 \(String(format: "%.1f", snap.optimalStrainLow))–\(String(format: "%.1f", snap.optimalStrainHigh))")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(Color(hex: "0EA5E9"))
                }
                StrainGauge(value: snap.dayStrain, low: snap.optimalStrainLow, high: snap.optimalStrainHigh)
                    .frame(height: 30)
                HStack(spacing: 10) {
                    miniStat(title: "跑步训练", value: String(format: "%.1f", snap.workoutStrain))
                    miniStat(title: "日常生活 (+\(String(format: "%.1f", snap.daytimeActivityStrainAdded)))", value: String(format: "%.1f", snap.baselineLivingStrain))
                    miniStat(title: "剩余空间", value: String(format: "%.1f", max(0, snap.optimalStrainHigh - snap.dayStrain)))
                }
                Text("对数刻度：越接近 21 越难增加。今日日常步数、活动热量、压力与心率波动已动态增加 +\(String(format: "%.1f", snap.daytimeActivityStrainAdded)) 负荷。")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.textMuted)
            }
        }
    }
    
    // MARK: Daytime Activities, Naps, Stress & Heart Rate Fluctuation
    
    private func daytimeDynamicsCard(_ snap: WhoopSnapshot) -> some View {
        CardContainer(icon: "waveform.path.ecg.rectangle.fill", title: "日间生理与活动实时动态", tint: Theme.primaryOrange) {
            VStack(alignment: .leading, spacing: 10) {
                LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                    daytimeTile(
                        icon: "figure.walk",
                        title: "日常活动",
                        value: snap.daytimeSteps > 0 ? "\(snap.daytimeSteps)" : "同步中",
                        unit: snap.daytimeSteps > 0 ? "步" : "",
                        subtitle: snap.daytimeActiveCalories > 0 ? "消耗 \(snap.daytimeActiveCalories) kcal · 负荷 +\(String(format: "%.1f", snap.daytimeActivityStrainAdded))" : "自动计入日常 Strain",
                        tint: Color(hex: "0EA5E9")
                    )
                    daytimeTile(
                        icon: "powersleep",
                        title: "今日午睡 / 小睡",
                        value: snap.napMinutes > 0 ? "\(snap.napMinutes)" : "0",
                        unit: "分钟",
                        subtitle: snap.napMinutes > 0 ? "恢复 +\(snap.daytimeNapBonusPct)% · 抵扣睡眠 -\(snap.napMinutes)分" : "午睡可充恢复并抵扣睡眠",
                        tint: Color(hex: "8B5CF6")
                    )
                    daytimeTile(
                        icon: "brain.head.profile",
                        title: "日间压力指数",
                        value: String(format: "%.1f", snap.stressScore),
                        unit: "/ 3.0",
                        subtitle: snap.watchStressAvg != nil ? "手表均值 \(snap.watchStressAvg!) · 峰值 \(snap.watchStressMax ?? snap.watchStressAvg!)" : snap.stressLevelLabel,
                        tint: snap.stressScore < 1.2 ? Theme.accentGreen : (snap.stressScore < 2.0 ? Color(hex: "F59E0B") : Color(hex: "F43F5E"))
                    )
                    daytimeTile(
                        icon: "heart.fill",
                        title: "全天心率波动",
                        value: "\(snap.hrMinToday)–\(snap.hrMaxToday)",
                        unit: "bpm",
                        subtitle: (snap.bodyBatteryMax != nil && snap.bodyBatteryCurrent != nil && snap.bodyBatteryMax! > 0) ? "身体电量 \(snap.bodyBatteryMax!) → \(snap.bodyBatteryCurrent!) (-\(max(0, snap.bodyBatteryMax! - snap.bodyBatteryCurrent!)))" : "静息 \(snap.rhrToday) bpm · 跨度 \(max(0, snap.hrMaxToday - snap.hrMinToday)) bpm",
                        tint: Color(hex: "F43F5E")
                    )
                }
                Text("日间步数、压力、心率波动与身体电量实时驱动「全天负荷」上升并消耗「实时恢复」，午睡小睡则反向充电并抵扣今晚睡眠需求。")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.textMuted)
            }
        }
    }
    
    private func daytimeTile(icon: String, title: String, value: String, unit: String, subtitle: String, tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(tint)
                Text(title)
                    .font(.system(size: 10, weight: .bold))
                    .foregroundColor(Theme.textMuted)
            }
            HStack(alignment: .firstTextBaseline, spacing: 3) {
                Text(value)
                    .font(.system(size: 18, weight: .heavy).monospacedDigit())
                    .foregroundColor(Theme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.75)
                if !unit.isEmpty {
                    Text(unit)
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundColor(Theme.textMuted)
                }
            }
            Text(subtitle)
                .font(.system(size: 9))
                .foregroundColor(Theme.textSecondary)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Theme.surfaceSecondary)
        .cornerRadius(10)
    }
    
    private func miniStat(title: String, value: String) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.system(size: 16, weight: .heavy))
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
    
    // MARK: Sleep Coach
    
    private func sleepCoachCard(_ snap: WhoopSnapshot) -> some View {
        CardContainer(icon: "moon.stars.fill", title: "睡眠教练 Sleep Coach", tint: Color(hex: "8B5CF6")) {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline) {
                    Text("今晚需睡")
                        .font(.system(size: 12))
                        .foregroundColor(Theme.textSecondary)
                    Text(String(format: "%.1f 小时", snap.neededSleepHours))
                        .font(.system(size: 22, weight: .heavy))
                        .foregroundColor(Theme.textPrimary)
                    Spacer()
                }
                
                VStack(spacing: 6) {
                    sleepNeedRow(label: "基础需求", value: String(format: "%.1fh", snap.baselineSleepHours))
                    sleepNeedRow(label: "今日负荷追加", value: "+\(snap.strainAddedSleepMinutes) 分钟")
                    sleepNeedRow(label: "近3日睡眠债", value: "+\(snap.sleepDebtMinutes) 分钟")
                    sleepNeedRow(label: "今日午睡/小睡抵扣", value: snap.napMinutes > 0 ? "-\(snap.napMinutes) 分钟" : "0 分钟 (未检测到午睡)")
                }
                
                Divider().background(Theme.border)
                
                HStack {
                    Text("起床时间")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Theme.textSecondary)
                    Spacer()
                    Button(action: { state.adjustWakeTime(minutesDelta: -15) }) {
                        Image(systemName: "minus.circle.fill").font(.system(size: 22))
                    }
                    Text(snap.wakeTimeText)
                        .font(.system(size: 18, weight: .heavy).monospacedDigit())
                        .foregroundColor(Theme.textPrimary)
                        .frame(width: 64)
                    Button(action: { state.adjustWakeTime(minutesDelta: 15) }) {
                        Image(systemName: "plus.circle.fill").font(.system(size: 22))
                    }
                }
                .foregroundColor(Color(hex: "8B5CF6"))
                
                HStack(spacing: 10) {
                    bedtimeTile(title: "睡满 100%", time: snap.recommendedBedtime100, highlight: true)
                    bedtimeTile(title: "最低 85%", time: snap.recommendedBedtime85, highlight: false)
                }
            }
        }
    }
    
    private func sleepNeedRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 11))
                .foregroundColor(Theme.textMuted)
            Spacer()
            Text(value)
                .font(.system(size: 11, weight: .semibold))
                .foregroundColor(Theme.textSecondary)
        }
    }
    
    private func bedtimeTile(title: String, time: String, highlight: Bool) -> some View {
        VStack(spacing: 2) {
            Text(time)
                .font(.system(size: 20, weight: .heavy).monospacedDigit())
                .foregroundColor(highlight ? .white : Theme.textPrimary)
            Text("\(title) 入睡")
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(highlight ? .white.opacity(0.85) : Theme.textMuted)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(highlight ? Color(hex: "8B5CF6") : Theme.surfaceSecondary)
        .cornerRadius(10)
    }
    
    // MARK: Stress & Healthspan
    
    private func stressHealthspanCard(_ snap: WhoopSnapshot) -> some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 6) {
                Label("生理压力", systemImage: "waveform.path.ecg")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(Theme.textMuted)
                HStack(alignment: .firstTextBaseline, spacing: 2) {
                    Text(String(format: "%.1f", snap.stressScore))
                        .font(.system(size: 26, weight: .heavy))
                        .foregroundColor(Theme.textPrimary)
                    Text("/ 3")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                }
                Text(snap.stressLevelLabel)
                    .font(.system(size: 10))
                    .foregroundColor(Theme.textSecondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(Theme.surface)
            .cornerRadius(14)
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
            
            VStack(alignment: .leading, spacing: 6) {
                Label("跑者生理年龄", systemImage: "hourglass")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(Theme.textMuted)
                Text(snap.biologicalAgeDelta <= 0
                     ? String(format: "年轻 %.1f 岁", abs(snap.biologicalAgeDelta))
                     : String(format: "偏大 %.1f 岁", snap.biologicalAgeDelta))
                    .font(.system(size: 20, weight: .heavy))
                    .foregroundColor(snap.biologicalAgeDelta <= 0 ? Theme.accentGreen : Color(hex: "F43F5E"))
                Text(String(format: "衰老速度 %.2fx · VO₂max %.1f", snap.paceOfAging, snap.vo2Max))
                    .font(.system(size: 10))
                    .foregroundColor(Theme.textSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(Theme.surface)
            .cornerRadius(14)
            .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
        }
    }
    
    // MARK: Journal
    
    private var journalCard: some View {
        CardContainer(icon: "checklist", title: "今日习惯日志", tint: Theme.primaryOrange) {
            VStack(alignment: .leading, spacing: 10) {
                Text("每天花 10 秒勾选，积累后自动分析每个习惯对你次日 HRV 的真实影响。")
                    .font(.system(size: 11))
                    .foregroundColor(Theme.textMuted)
                LazyVGrid(columns: [GridItem(.flexible(), spacing: 8), GridItem(.flexible(), spacing: 8)], spacing: 8) {
                    ForEach(WhoopJournalBehavior.allBehaviors) { b in
                        journalChip(b)
                    }
                }
            }
        }
    }
    
    private func journalChip(_ b: WhoopJournalBehavior) -> some View {
        let selected = state.todayJournalBehaviors.contains(b.id)
        let tint = b.isPositiveHabit ? Theme.accentGreen : Color(hex: "F43F5E")
        return Button(action: {
            withAnimation(.easeInOut(duration: 0.15)) {
                state.toggleJournalBehavior(b.id)
            }
        }) {
            HStack(spacing: 6) {
                Image(systemName: b.icon)
                    .font(.system(size: 12))
                    .foregroundColor(selected ? .white : tint)
                    .frame(width: 16)
                Text(b.title)
                    .font(.system(size: 11, weight: selected ? .bold : .medium))
                    .foregroundColor(selected ? .white : Theme.textPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.8)
                Spacer(minLength: 0)
                if selected {
                    Image(systemName: "checkmark")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.white)
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 9)
            .background(selected ? tint : Theme.surfaceSecondary)
            .cornerRadius(9)
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    // MARK: Insights
    
    private var insightsCard: some View {
        let impacts = state.habitImpacts
        let personalizedCount = impacts.filter { $0.isPersonalized }.count
        let shown = showAllInsights ? impacts : Array(impacts.prefix(5))
        return CardContainer(icon: "chart.bar.xaxis", title: "习惯影响分析", tint: Theme.primaryOrange) {
            VStack(alignment: .leading, spacing: 10) {
                Text(personalizedCount > 0
                     ? "已有 \(personalizedCount) 项习惯积累足够数据，显示你的个人次日 HRV 差异；其余为运动医学参考值。"
                     : "个人分析需要每个习惯「做了」与「没做」各至少 3 天且次日有 HRV 数据。在此之前显示运动医学参考值。")
                    .font(.system(size: 11))
                    .foregroundColor(Theme.textMuted)
                    .lineSpacing(2)
                ForEach(shown) { impact in
                    insightRow(impact)
                }
                if impacts.count > 5 {
                    Button(action: { withAnimation { showAllInsights.toggle() } }) {
                        Text(showAllInsights ? "收起" : "查看全部 \(impacts.count) 项")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(Theme.primaryOrange)
                            .frame(maxWidth: .infinity)
                    }
                }
            }
        }
    }
    
    private func insightRow(_ impact: WhoopHabitImpact) -> some View {
        let positive = impact.impactPct >= 0
        let color = positive ? Theme.accentGreen : Color(hex: "F43F5E")
        let barWidth = min(1.0, Double(abs(impact.impactPct)) / 25.0)
        return VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                Image(systemName: impact.behavior.icon)
                    .font(.system(size: 11))
                    .foregroundColor(color)
                    .frame(width: 16)
                Text(impact.behavior.title)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Theme.textPrimary)
                Text(impact.isPersonalized ? "个人" : "参考")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(impact.isPersonalized ? .white : Theme.textMuted)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(impact.isPersonalized ? Theme.primaryOrange : Theme.surfaceSecondary)
                    .cornerRadius(4)
                Spacer()
                Text("\(positive ? "+" : "")\(impact.impactPct)%")
                    .font(.system(size: 13, weight: .heavy))
                    .foregroundColor(color)
            }
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Theme.surfaceSecondary)
                    Capsule().fill(color).frame(width: geo.size.width * barWidth)
                }
            }
            .frame(height: 5)
            Text(impact.isPersonalized
                 ? "次日 HRV \(impact.hrvDeltaMs >= 0 ? "+" : "")\(impact.hrvDeltaMs)ms（做了 \(impact.yesDays) 天 vs 没做 \(impact.noDays) 天）"
                 : "已记录 \(impact.loggedDaysCount) 天 · \(impact.behavior.subtitle)")
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
        }
        .padding(.vertical, 2)
    }
    
    // MARK: Coach Bridge
    
    private func askCoachButton(_ snap: WhoopSnapshot) -> some View {
        Button(action: {
            state.selectedTab = 1
            Task {
                await state.sendCoachMessage("请结合我今天的恢复度 \(snap.recoveryScore)%、负荷 Strain \(String(format: "%.1f", snap.dayStrain)) 和睡眠情况，告诉我今天该怎么练、今晚该怎么恢复。")
            }
        }) {
            HStack(spacing: 8) {
                Image(systemName: "brain.head.profile")
                Text("让 Canova 教练解读今日状态")
            }
            .font(.system(size: 14, weight: .bold))
            .foregroundColor(Theme.onBrand)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 13)
            .background(Theme.brandFill)
            .cornerRadius(12)
        }
    }
    
    private var disclaimer: some View {
        Text("恢复、负荷、睡眠需求与生理年龄均为基于手表 HRV、静息心率、睡眠与训练 TRIMP 的算法估算，仅供训练参考，不构成医疗诊断。")
            .font(.system(size: 10))
            .foregroundColor(Theme.textMuted)
            .multilineTextAlignment(.center)
            .padding(.horizontal, 8)
    }
    
    private static var todayLabel: String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "zh_CN")
        f.dateFormat = "M月d日 EEEE"
        return f.string(from: Date())
    }
}

// MARK: - Morning Briefing Push Settings (opt-in, default off)

struct MorningBriefingSettingsCard: View {
    @ObservedObject private var manager = MorningBriefingManager.shared
    @State private var errorText: String?
    @State private var infoText: String?
    @State private var isWorking: Bool = false
    
    private var timeBinding: Binding<Date> {
        Binding(
            get: {
                var c = DateComponents()
                c.hour = manager.hour
                c.minute = manager.minute
                return Calendar.current.date(from: c) ?? Date()
            },
            set: { newDate in
                let c = Calendar.current.dateComponents([.hour, .minute], from: newDate)
                manager.setTime(hour: c.hour ?? 7, minute: c.minute ?? 0)
            }
        )
    }
    
    private var toggleBinding: Binding<Bool> {
        Binding(
            get: { manager.isEnabled },
            set: { on in
                isWorking = true
                errorText = nil
                infoText = nil
                Task {
                    errorText = await manager.setEnabled(on)
                    if errorText == nil && on {
                        infoText = "已开启，每天 \(manager.timeText) 推送今日恢复状态"
                    }
                    isWorking = false
                }
            }
        )
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Image(systemName: "bell.badge.fill")
                    .font(.system(size: 15))
                    .foregroundColor(Theme.primaryOrange)
                VStack(alignment: .leading, spacing: 2) {
                    Text("晨间恢复推送")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text("每天早上推送恢复度、HRV 与今日目标负荷")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                }
                Spacer()
                Toggle("", isOn: toggleBinding)
                    .labelsHidden()
                    .tint(Theme.primaryOrange)
                    .disabled(isWorking)
            }
            
            if manager.isEnabled {
                HStack {
                    Text("推送时间")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Theme.textSecondary)
                    Spacer()
                    DatePicker("", selection: timeBinding, displayedComponents: .hourAndMinute)
                        .labelsHidden()
                        .environment(\.locale, Locale(identifier: "zh_CN"))
                }
                Text("系统会在推送前自动向手表（佳明 / 高驰 / Apple Watch）拉取昨晚睡眠与 HRV 数据，直接推送今日恢复度与训练课表（建议设在起床后 20–40 分钟）。")
                    .font(.system(size: 10))
                    .foregroundColor(Theme.textMuted)
                    .lineSpacing(2)
                Button(action: {
                    manager.sendTestNotification()
                    infoText = "正在拉取最新手表数据并发送预览推送（可切到后台查看）"
                }) {
                    Text("同步手表并发送预览推送")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.primaryOrange)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(Theme.primaryOrange.opacity(0.12))
                        .cornerRadius(6)
                }
            }
            
            if let err = errorText {
                HStack(spacing: 8) {
                    Text(err)
                        .font(.system(size: 11))
                        .foregroundColor(Color(hex: "F43F5E"))
                    Spacer()
                    if manager.authStatus == .denied {
                        Button("去设置") {
                            if let url = URL(string: UIApplication.openSettingsURLString) {
                                UIApplication.shared.open(url)
                            }
                        }
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                    }
                }
            } else if let info = infoText {
                Text(info)
                    .font(.system(size: 11))
                    .foregroundColor(Theme.accentGreen)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
        .task {
            await manager.refreshAuthStatus()
        }
    }
}

// MARK: - Reusable Components

private struct CardContainer<Content: View>: View {
    let icon: String
    let title: String
    let tint: Color
    @ViewBuilder let content: () -> Content
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 13))
                    .foregroundColor(tint)
                Text(title)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Spacer()
            }
            content()
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
}

private struct MetricRing: View {
    let progress: Double
    let color: Color
    let value: String
    let title: String
    let subtitle: String
    
    var body: some View {
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
            .frame(width: 88, height: 88)
            Text(title)
                .font(.system(size: 12, weight: .bold))
                .foregroundColor(Theme.textSecondary)
        }
    }
}

private struct StrainGauge: View {
    let value: Double
    let low: Double
    let high: Double
    
    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let x: (Double) -> CGFloat = { CGFloat(min(21, max(0, $0)) / 21.0) * w }
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(Theme.surfaceSecondary)
                    .frame(height: 10)
                Rectangle()
                    .fill(Color(hex: "0EA5E9").opacity(0.28))
                    .frame(width: max(2, x(high) - x(low)), height: 10)
                    .offset(x: x(low))
                Capsule()
                    .fill(Color(hex: "0EA5E9"))
                    .frame(width: max(6, x(value)), height: 10)
                Circle()
                    .fill(Color.white)
                    .frame(width: 16, height: 16)
                    .overlay(Circle().stroke(Color(hex: "0EA5E9"), lineWidth: 3))
                    .offset(x: max(0, x(value) - 8))
            }
            .frame(height: 16)
            .overlay(
                HStack {
                    Text("0").font(.system(size: 9)).foregroundColor(Theme.textMuted)
                    Spacer()
                    Text("21").font(.system(size: 9)).foregroundColor(Theme.textMuted)
                }
                .offset(y: 14)
            )
        }
    }
}
