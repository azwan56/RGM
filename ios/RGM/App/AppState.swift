import SwiftUI
import Combine

@MainActor
class AppState: ObservableObject {
    @Published var currentUser: UserProfile?
    @Published var isLoggedIn: Bool = false
    @Published var selectedTab: Int = 0
    @Published var dashboard = DashboardData()
    
    // Science & Health
    @Published var scienceMetrics: ScienceMetricsResponse?
    @Published var healthTrend: [HealthTrendPoint] = []
    
    // Coach Plan & Analysis
    @Published var activePlan: ActivePlanData?
    @Published var coachAnalysis: CoachAnalysisResponse?
    @Published var isAnalyzingCoach: Bool = false
    
    // Full Profile & Races
    @Published var fullProfile: FullProfileData?
    @Published var userGoal: UserGoalData?
    @Published var userRaces: [RaceItem] = []
    @Published var isSavingProfile: Bool = false
    
    @Published var isSyncing: Bool = false
    @Published var syncNotice: String?
    @Published var errorMessage: String?
    @Published var themeMode: ThemeMode = Theme.current
    
    // WHOOP-Style Journal & Sleep Coach Preferences
    @Published var todayJournalBehaviors: Set<String> = []
    @Published var journalHistory: [String: [String]] = [:]
    @Published var preferredWakeHour: Int = 6
    @Published var preferredWakeMinute: Int = 30
    
    // Proactive AI Coach Alerts
    @Published var proactiveAlerts: [ProactiveCoachAlert] = []
    @Published var hasDeliveredMorningBriefing: Bool = false
    @Published var localTodayHealth: [String: Any] = [:]
    
    func setTheme(_ mode: ThemeMode) {
        Theme.setMode(mode)
        self.themeMode = mode
    }
    
    @Published var coachMessages: [CoachMessage] = [
        CoachMessage(isUser: false, text: "你好！我是 Renato Canova AI 耐力教练。我会实时监测你的 WHOOP 级恢复度 (Recovery)、全天生理负荷 (Strain)、HRV/静息心率基线与睡眠债，主动为你调整每日训练处方。今天感觉如何？")
    ]
    @Published var isCoachThinking: Bool = false
    
    private var lastRefreshedDayKey: String = ""
    private var lastRefreshedAt: Date = .distantPast
    private var lastAutoWatchSyncAt: Date = .distantPast
    private var daytimeSyncTimer: AnyCancellable?
    
    init() {
        self.currentUser = StorageManager.shared.loadUser()
        // Only treat as logged in when both a token and a stored user exist.
        // Fresh installs / after logout or account deletion always start logged out.
        self.isLoggedIn = StorageManager.shared.token != nil && self.currentUser != nil
        if let uid = self.currentUser?.id {
            loadWhoopJournal(uid: uid)
        }
        
        MorningBriefingManager.shared.installDelegate()
        MorningBriefingManager.shared.onOpenRecovery = { [weak self] in
            self?.selectedTab = 4
        }
        MorningBriefingManager.shared.onPrePushSync = { [weak self] in
            await self?.performPrePushWatchSync()
        }
        if self.isLoggedIn, let uid = self.currentUser?.id {
            MorningBriefingManager.shared.configure(uid: uid)
        }
        
        // Install HealthKit background observer so morning sleep/HRV and daytime naps/HR/steps trigger watch sync
        HealthKitManager.shared.startBackgroundObserver { [weak self] in
            await self?.performPrePushWatchSync()
        }
        
        // Periodic 5-minute foreground timer so daytime activities, naps, stress & HR fluctuations auto-refresh
        daytimeSyncTimer = Timer.publish(every: 300, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                guard let self = self, self.isLoggedIn else { return }
                Task { @MainActor in
                    await self.onAppBecameActive(forceWatchSync: false)
                }
            }
        
        if self.isLoggedIn {
            Task { [weak self] in
                await self?.onAppBecameActive(forceWatchSync: true)
            }
        }
    }
    
    /// Proactively pulls the latest watch data (Garmin/COROS cloud or Apple Watch HealthKit)
    /// before the morning push notification fires or when the app wakes in the morning.
    func performPrePushWatchSync() async {
        guard isLoggedIn, let uid = currentUser?.id, !uid.isEmpty else { return }
        lastAutoWatchSyncAt = Date()
        if let watch = connectedWatchBrand() {
            if watch.id == "garmin" || watch.id == "coros" {
                _ = try? await APIService.shared.triggerSync(uid: uid)
                try? await Task.sleep(nanoseconds: 2_500_000_000)
                await refreshData()
            } else if watch.id == "apple_watch" {
                _ = await syncHealthKit(watchBrand: "apple_watch")
            } else {
                await refreshData()
            }
        } else {
            await refreshData()
        }
    }
    
    /// Called whenever the app enters the foreground or the calendar day changes (e.g. Sunday -> Monday).
    func onAppBecameActive(forceWatchSync: Bool = false) async {
        guard isLoggedIn else { return }
        let todayKey = Self.todayKeyString
        let dayChanged = (lastRefreshedDayKey != todayKey)
        let now = Date()
        
        // If we crossed into a new day (e.g. Monday morning), immediately clear stale yesterday workout
        // and roll weeklyProgress to the current Monday-Sunday week before network finishes.
        if dayChanged || !isWeeklyProgressForToday(dashboard.weeklyProgress) {
            dashboard.weeklyProgress = effectiveWeeklyProgress
            if let tw = dashboard.todayWorkout, let d = tw.date, !d.isEmpty, d != todayKey {
                dashboard.todayWorkout = nil
            }
        }
        
        if dayChanged || now.timeIntervalSince(lastRefreshedAt) > 30 {
            await refreshData()
        }
        
        // Proactively sync watch in the background if today's physiology hasn't arrived yet or >3 min elapsed
        // so daytime activities (steps/calories), naps, stress, and HR fluctuations update automatically
        let todayHealthSynced = (dashboard.todayHealth?.date ?? "").hasPrefix(todayKey)
        if connectedWatchBrand() != nil && (forceWatchSync || dayChanged || !todayHealthSynced || now.timeIntervalSince(lastAutoWatchSyncAt) > 180) {
            await performPrePushWatchSync()
        }
    }
    
    /// Always returns the Monday-Sunday WeeklyProgressData for the CURRENT Beijing calendar week,
    /// preventing Monday morning from ever displaying last week's (Mon-Sun) schedule.
    var effectiveWeeklyProgress: WeeklyProgressData {
        let todayKey = Self.todayKeyString
        if let wp = dashboard.weeklyProgress, isWeeklyProgressForToday(wp) {
            return wp
        }
        return buildClientCurrentWeekProgress(
            targetKm: dashboard.weeklyProgress?.target_week_km ?? 50.0,
            activities: dashboard.recentActivities
        )
    }
    
    /// Returns today's scheduled workout only if it matches today's date (never yesterday's workout on Monday morning).
    var effectiveTodayWorkout: TodayWorkoutData? {
        guard let tw = dashboard.todayWorkout else { return nil }
        if let d = tw.date, !d.isEmpty, d != Self.todayKeyString {
            return nil
        }
        return tw
    }
    
    private func isWeeklyProgressForToday(_ wp: WeeklyProgressData?) -> Bool {
        guard let wp = wp else { return false }
        let todayKey = Self.todayKeyString
        if let days = wp.daily_breakdown, !days.isEmpty {
            return days.contains { ($0.full_date == todayKey) && $0.is_today }
        }
        if let start = wp.week_start, let end = wp.week_end, !start.isEmpty, !end.isEmpty {
            return start <= todayKey && todayKey <= end
        }
        return false
    }
    
    private func buildClientCurrentWeekProgress(targetKm: Double, activities: [ActivityItem]) -> WeeklyProgressData {
        var cal = Calendar(identifier: .iso8601)
        cal.firstWeekday = 2 // Monday
        let tz = TimeZone(identifier: "Asia/Shanghai") ?? .current
        cal.timeZone = tz
        
        let now = Date()
        let todayStart = cal.startOfDay(for: now)
        let weekday = cal.component(.weekday, from: todayStart) // 1 = Sun, 2 = Mon ... 7 = Sat
        let daysFromMonday = (weekday + 5) % 7 // 0 = Mon ... 6 = Sun
        let monday = cal.date(byAdding: .day, value: -daysFromMonday, to: todayStart) ?? todayStart
        let sunday = cal.date(byAdding: .day, value: 6, to: monday) ?? todayStart
        let isoWeek = cal.component(.weekOfYear, from: todayStart)
        
        let fullFmt = DateFormatter()
        fullFmt.calendar = cal
        fullFmt.locale = Locale(identifier: "en_US_POSIX")
        fullFmt.timeZone = tz
        fullFmt.dateFormat = "yyyy-MM-dd"
        
        let shortFmt = DateFormatter()
        shortFmt.calendar = cal
        shortFmt.locale = Locale(identifier: "en_US_POSIX")
        shortFmt.timeZone = tz
        shortFmt.dateFormat = "MM/dd"
        
        let todayKey = fullFmt.string(from: todayStart)
        let shortNames = ["一", "二", "三", "四", "五", "六", "日"]
        
        var dailyKmByDate: [String: Double] = [:]
        for act in activities {
            guard let st = act.start_time, st.count >= 10 else { continue }
            let dKey = String(st.prefix(10))
            dailyKmByDate[dKey, default: 0.0] += act.distanceKm
        }
        
        var breakdown: [DayBreakdownItem] = []
        var totalWeekKm: Double = 0.0
        for idx in 0..<7 {
            let curDate = cal.date(byAdding: .day, value: idx, to: monday) ?? todayStart
            let curFull = fullFmt.string(from: curDate)
            let curShort = shortFmt.string(from: curDate)
            let km = ((dailyKmByDate[curFull] ?? 0.0) * 10).rounded() / 10.0
            totalWeekKm += km
            breakdown.append(
                DayBreakdownItem(
                    date: curShort,
                    full_date: curFull,
                    day_name: "周\(shortNames[idx])",
                    short_day: shortNames[idx],
                    distance_km: km,
                    is_today: curFull == todayKey,
                    is_past: curFull < todayKey
                )
            )
        }
        
        let cleanTotal = (totalWeekKm * 10).rounded() / 10.0
        let safeTarget = targetKm > 0 ? targetKm : 50.0
        let pct = ((cleanTotal / safeTarget) * 1000).rounded() / 10.0
        let remain = max(0.0, ((safeTarget - cleanTotal) * 10).rounded() / 10.0)
        let daysLeft = max(1, 7 - daysFromMonday)
        let dailyReq = ((remain / Double(daysLeft)) * 10).rounded() / 10.0
        
        return WeeklyProgressData(
            week_number: isoWeek,
            week_label: "第\(isoWeek)周 (\(shortFmt.string(from: monday))~\(shortFmt.string(from: sunday)))",
            week_start: fullFmt.string(from: monday),
            week_end: fullFmt.string(from: sunday),
            current_week_km: cleanTotal,
            target_week_km: safeTarget,
            progress_pct: pct,
            remaining_km: remain,
            daily_required_km: dailyReq,
            daily_breakdown: breakdown
        )
    }
    
    func refreshData() async {
        guard isLoggedIn, let uid = currentUser?.id, !uid.isEmpty else { return }
        loadWhoopJournal(uid: uid)
        lastRefreshedDayKey = Self.todayKeyString
        lastRefreshedAt = Date()
        
        // 1. Fetch Dashboard (User profile, month & week progress, recent workouts, CTL/ATL, yearly stats, health)
        do {
            let d = try await APIService.shared.fetchDashboard(uid: uid)
            if let u = d.user {
                self.currentUser = u
                StorageManager.shared.saveUser(u)
            }
            if let prog = d.progress {
                self.dashboard.monthMileage = prog.current_month_km ?? 0.0
                self.dashboard.monthTarget = prog.target_month_km ?? 200.0
                self.dashboard.progressPercent = prog.progress_pct ?? 0.0
            }
            self.dashboard.weeklyProgress = d.weekly_progress
            self.dashboard.todayWorkout = d.today_workout
            self.dashboard.yearlyStats = d.yearly_stats
            
            let acts = d.recent_activities ?? d.current_month_activities ?? []
            self.dashboard.recentActivities = acts
            self.dashboard.runCount = acts.count
            if let first = self.dashboard.recentActivities.first, let pace = first.avg_pace_str {
                self.dashboard.avgPace = pace
            }
            self.dashboard.fitnessForm = d.fitness_form
            self.dashboard.todayHealth = d.today_health
            self.dashboard.aiCoachTip = d.ai_coach_tip
        } catch {
            print("[AppState] Dashboard refresh error: \(error)")
        }
        
        // 2. Fetch Science Metrics & Health Trend (Decoupled for robustness)
        do {
            self.scienceMetrics = try await APIService.shared.fetchScienceMetrics(uid: uid)
        } catch {
            print("[AppState] Science metrics error: \(error)")
        }
        
        do {
            let trend = try await APIService.shared.fetchHealthTrend(uid: uid)
            self.healthTrend = trend
            print("[AppState] Successfully loaded \(trend.count) health trend points")
        } catch {
            print("[AppState] Health trend error: \(error)")
        }
        
        // 3. Fetch Coach Plan & Analysis
        do {
            async let planReq = APIService.shared.fetchCoachPlan(uid: uid)
            async let analysisReq = APIService.shared.fetchCoachAnalysis(uid: uid)
            
            let (p, a) = try await (planReq, analysisReq)
            self.activePlan = p
            self.coachAnalysis = a
        } catch {
            print("[AppState] Coach plan error: \(error)")
        }
        
        // 4. Fetch Full Profile & Races
        do {
            let pRes = try await APIService.shared.fetchFullProfile(uid: uid)
            self.fullProfile = pRes.profile
            if let g = pRes.goal {
                self.userGoal = g
            }
            self.userRaces = pRes.races ?? []
        } catch {
            print("[AppState] Profile error: \(error)")
        }
        
        // 4b. Read local iPhone HealthKit daytime metrics (steps, active calories, HR, naps) as real-time supplement
        let hkRecent = await HealthKitManager.shared.fetchDailyHealth(days: 1)
        if let todayEntry = hkRecent.first(where: { ($0["date"] as? String) == Self.todayKeyString }) {
            self.localTodayHealth = todayEntry
        }
        
        // 5. Evaluate WHOOP Recovery/Strain/Sleep & Generate Proactive Coach Alerts
        evaluateProactiveCoachAlerts()
        
        // 6. Refresh opt-in morning push with the latest numbers and today's workout
        MorningBriefingManager.shared.configure(uid: uid)
        let snap = whoopSnapshot
        let todayHealthIsToday = (dashboard.todayHealth?.date ?? "").hasPrefix(Self.todayKeyString)
        var upcomingMap: [String: String] = [:]
        if let tw = effectiveTodayWorkout, let title = tw.title, !title.isEmpty {
            let kmText = (tw.distance_km ?? 0) > 0 ? String(format: " (%.1fkm)", tw.distance_km ?? 0) : ""
            upcomingMap[Self.todayKeyString] = title + kmText
        }
        MorningBriefingManager.shared.update(
            snapshot: snap,
            hasTodayData: todayHealthIsToday && snap.missingInputs.isEmpty,
            upcomingWorkouts: upcomingMap
        )
    }
    
    func runCoachAnalysis() async {
        guard let uid = currentUser?.id else { return }
        isAnalyzingCoach = true
        do {
            let res = try await APIService.shared.triggerCoachAnalysis(uid: uid)
            self.coachAnalysis = res
            if let sum = res.summary {
                let note = "⚡ 【Canova 专项推理报告已更新】\n当前阶段：\(res.periodization_phase ?? "进阶期")\n\n\(sum)"
                self.coachMessages.append(CoachMessage(isUser: false, text: note))
            }
        } catch {
            print("[AppState] Trigger coach analysis error: \(error)")
        }
        isAnalyzingCoach = false
    }
    
    /// Returns the currently bound watch brand ID and label if any watch is bound.
    func connectedWatchBrand() -> (id: String, label: String)? {
        let g = fullProfile?.garmin_connected ?? currentUser?.garmin_connected ?? false
        let c = fullProfile?.coros_connected ?? currentUser?.coros_connected ?? false
        let aw = fullProfile?.apple_watch_connected ?? currentUser?.apple_watch_connected ?? false
        if g { return ("garmin", "佳明 Garmin") }
        if c { return ("coros", "高驰 COROS") }
        if aw { return ("apple_watch", "Apple Watch") }
        return nil
    }
    
    /// Reads running workouts (with HR / GPS route / cadence) and daily health metrics from Apple Health,
    /// uploads them to the server, then refreshes so CTL/ATL, stats, maps and the AI coach all use them.
    @discardableResult
    func syncHealthKit(watchBrand: String? = nil) async -> Bool {
        guard let uid = currentUser?.id, !uid.isEmpty else {
            syncNotice = "请先登录"
            return false
        }
        if let existing = connectedWatchBrand() {
            if let wb = watchBrand, existing.id != wb {
                syncNotice = "每个账号仅限连接一个运动手表，请先解绑【\(existing.label)】后再连接"
                return false
            }
            if watchBrand == nil && (existing.id == "garmin" || existing.id == "coros") {
                syncNotice = "当前已连接【\(existing.label)】云端直连，无需从 Apple 健康重复导入"
                return false
            }
        }
        isSyncing = true
        defer { isSyncing = false }
        let brandDisplay = watchBrand == "apple_watch" ? "Apple Watch" : "Apple 健康"
        syncNotice = "正在从 \(brandDisplay) 读取跑步记录..."
        
        guard await HealthKitManager.shared.requestAuthorization() else {
            syncNotice = "请在 iPhone「设置 - 健康 - 数据访问与设备」中允许 RGM 读取数据"
            return false
        }
        
        if let wb = watchBrand, wb == "apple_watch" {
            do {
                _ = try await APIService.shared.bindHealthWatch(uid: uid, brand: wb)
            } catch {
                syncNotice = error.localizedDescription
                return false
            }
            self.currentUser?.apple_watch_connected = true
            if let u = self.currentUser {
                StorageManager.shared.saveUser(u)
            }
        }
        
        let since = Calendar.current.date(byAdding: .day, value: -365, to: Date()) ?? Date()
        let rawWorkouts = await HealthKitManager.shared.fetchRunningWorkouts(since: since)
        // Exclude workouts written into Apple Health by Garmin Connect or COROS to prevent cross-brand duplicates
        let workouts = rawWorkouts.filter { w in
            let srcName = w.sourceRevision.source.name.lowercased()
            let bundleId = w.sourceRevision.source.bundleIdentifier.lowercased()
            let isGarminOrCoros = srcName.contains("garmin") || srcName == "connect" || bundleId.contains("garmin") || srcName.contains("coros") || bundleId.contains("coros")
            return !isGarminOrCoros
        }
        let uploaded = StorageManager.shared.uploadedHealthKitIds(uid: uid)
        let pending = workouts.filter { !uploaded.contains($0.uuid.uuidString) }
        let dailyHealth = await HealthKitManager.shared.fetchDailyHealth(days: 30)
        
        var importedTotal = 0
        var gpsTotal = 0
        var healthDays = 0
        do {
            if pending.isEmpty {
                // Still push the latest daily health metrics
                let res = try await APIService.shared.uploadHealthKit(uid: uid, workouts: [], dailyHealth: dailyHealth, watchBrand: watchBrand)
                healthDays = res.health_days ?? 0
            } else {
                let chunkSize = 20
                var first = true
                for start in stride(from: 0, to: pending.count, by: chunkSize) {
                    let chunk = Array(pending[start..<min(start + chunkSize, pending.count)])
                    syncNotice = "正在上传跑步记录 \(min(start + chunkSize, pending.count))/\(pending.count)..."
                    var payloads: [[String: Any]] = []
                    for w in chunk {
                        payloads.append(await HealthKitManager.shared.buildWorkoutPayload(w))
                    }
                    let res = try await APIService.shared.uploadHealthKit(
                        uid: uid, workouts: payloads, dailyHealth: first ? dailyHealth : [], watchBrand: watchBrand
                    )
                    first = false
                    importedTotal += res.imported_workouts ?? 0
                    gpsTotal += res.workouts_with_gps ?? 0
                    healthDays = max(healthDays, res.health_days ?? 0)
                    StorageManager.shared.markHealthKitUploaded(uid: uid, ids: chunk.map { $0.uuid.uuidString })
                }
            }
        } catch {
            syncNotice = "上传失败：\(error.localizedDescription)"
            await refreshData()
            return false
        }
        
        // Legacy local-only cache is no longer needed; server is the source of truth.
        StorageManager.shared.saveActivities([])
        
        if workouts.isEmpty {
            syncNotice = healthDays > 0 ? "已连接 \(brandDisplay) 并同步 \(healthDays) 天生理数据；暂未检测到跑步记录" : "已连接 \(brandDisplay)；Apple 健康中暂未找到跑步记录"
        } else if pending.isEmpty {
            syncNotice = "\(brandDisplay) 跑步记录已是最新 ✓（共 \(workouts.count) 条）"
        } else {
            syncNotice = "已从 \(brandDisplay) 同步 \(importedTotal) 条跑步记录（\(gpsTotal) 条含 GPS 轨迹）、\(healthDays) 天健康数据 ✓"
        }
        await refreshData()
        return true
    }
    
    func syncWatches() async {
        guard let uid = currentUser?.id else {
            syncNotice = "请先登录"
            return
        }
        isSyncing = true
        syncNotice = "正在向官方服务器同步最新数据..."
        do {
            let msg = try await APIService.shared.triggerSync(uid: uid)
            syncNotice = msg
            // Wait 2s and refresh
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            await refreshData()
        } catch {
            syncNotice = "同步失败: \(error.localizedDescription)"
        }
        isSyncing = false
    }
    
    func sendCoachMessage(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        
        let userMsg = CoachMessage(isUser: true, text: trimmed)
        coachMessages.append(userMsg)
        
        isCoachThinking = true
        
        var replyText: String? = nil
        let snap = whoopSnapshot
        let activeBehaviors = WhoopJournalBehavior.allBehaviors
            .filter { todayJournalBehaviors.contains($0.id) }
            .map { $0.title }
            .joined(separator: "、")
        let napText = snap.napMinutes > 0 ? "，今日午睡\(snap.napMinutes)分钟" : ""
        let stepsText = snap.daytimeSteps > 0 ? "，日常步数\(snap.daytimeSteps)步(\(snap.daytimeActiveCalories)kcal)" : ""
        let whoopContextPrefix = "[跑者实时生理与WHOOP状态：今日恢复度 \(snap.recoveryScore)%(\(snap.recoveryZone.label))，今日Strain负荷 \(String(format: "%.1f", snap.dayStrain))/21(目标\(String(format: "%.1f", snap.optimalStrainLow))-\(String(format: "%.1f", snap.optimalStrainHigh)))\(stepsText)，HRV \(snap.hrvToday)ms(基线\(snap.hrvBaseline)ms)，静息心率 \(snap.rhrToday)bpm(基线\(snap.rhrBaseline)bpm)，全天心率波动 \(snap.hrMinToday)-\(snap.hrMaxToday)bpm，生理压力 \(String(format: "%.1f", snap.stressScore))/3.0，昨晚睡眠 \(String(format: "%.1f", snap.actualSleepHours))h\(napText)(今晚需睡\(String(format: "%.1f", snap.neededSleepHours))h，建议\(snap.recommendedBedtime100)入睡)，今日行为日志：\(activeBehaviors.isEmpty ? "未勾选" : activeBehaviors)] "
        
        // 1. Try remote API first
        let isIdentity = isCoachIdentityQuery(trimmed)
        do {
            let remoteReply = try await APIService.shared.askCanovaCoach(message: whoopContextPrefix + trimmed, uid: currentUser?.id)
            if !remoteReply.isEmpty && !remoteReply.contains("教练正在分析您的训练负荷...") {
                let lowReply = remoteReply.lowercased()
                let hasModelInfo = lowReply.contains("qwen") || lowReply.contains("通义千问") || lowReply.contains("deepseek") || lowReply.contains("模型")
                if !isIdentity || hasModelInfo {
                    replyText = remoteReply
                }
            }
        } catch {
            print("[AppState] Remote coach chat unavailable (\(error.localizedDescription)), using individualized Canova reasoning engine.")
        }
        
        // 2. Fallback to authentic Canova coaching knowledge engine
        if replyText == nil {
            try? await Task.sleep(nanoseconds: 500_000_000)
            replyText = generateCanovaCoachAdvice(for: trimmed)
        }
        
        let coachMsg = CoachMessage(isUser: false, text: replyText ?? "教练正在分析您的训练负荷...")
        coachMessages.append(coachMsg)
        
        isCoachThinking = false
    }
    
    private func isCoachIdentityQuery(_ query: String) -> Bool {
        let q = query.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        let keywords = [
            "你是谁", "您是谁", "你是哪位", "你叫什么", "什么模型", "哪个模型",
            "什么大模型", "用什么模型", "底层模型", "llm", "自我介绍",
            "介绍一下你自己", "介绍下你自己", "介绍一下你", "你是干什么的",
            "你的简介", "教练简介", "who are you", "what model"
        ]
        if keywords.contains(where: { q.contains($0) }) {
            return true
        }
        let stripped = q.trimmingCharacters(in: CharacterSet(charactersIn: "？?！!。., "))
        return stripped == "你是" || stripped == "模型" || stripped == "介绍"
    }
    
    private func generateCanovaCoachAdvice(for query: String) -> String {
        let q = query.lowercased()
        
        // 优先使用看板实时的 90 天 EWMA Banister 体能负荷指标，保证全 App 数据绝对一致
        let ctlVal = dashboard.fitnessForm?.ctl ?? coachAnalysis?.tsb_metrics?.ctl ?? 0.0
        let atlVal = dashboard.fitnessForm?.atl ?? coachAnalysis?.tsb_metrics?.atl ?? 0.0
        let tsbVal = dashboard.fitnessForm?.tsb ?? coachAnalysis?.tsb_metrics?.tsb ?? 0.0
        let rawStatus = dashboard.fitnessForm?.status_label ?? coachAnalysis?.tsb_metrics?.status ?? "训练中"
        let statusLabel = rawStatus.contains("(") ? rawStatus : (tsbVal > 15 ? "巅峰就绪 (Peak Form)" : (tsbVal >= -10 ? "平衡稳健 (Neutral Form)" : (tsbVal >= -30 ? "训练中 (Productive Training)" : (tsbVal >= -45 ? "高度疲劳 (High Fatigue)" : "过度负荷 / 伤病高危"))))
        let tsbSign = tsbVal >= 0 ? "+\(String(format: "%.1f", tsbVal))" : "\(String(format: "%.1f", tsbVal))"
        let upcomingRaces = userRaces.filter { r in
            guard let dStr = r.race_date, !dStr.isEmpty else { return false }
            if r.status == "completed" || (r.finish_time != nil && !(r.finish_time?.isEmpty ?? true)) { return false }
            return true
        }.sorted { ($0.race_date ?? "") < ($1.race_date ?? "") }
        
        let nextRace = upcomingRaces.first
        let aGoalRace = upcomingRaces.first(where: { $0.priority == 1 }) ?? upcomingRaces.first
        let targetRace = nextRace?.name ?? aGoalRace?.name ?? activePlan?.target_race_name ?? coachAnalysis?.athlete_snapshot?.target_race ?? "未设置目标赛事"
        let isTrail = upcomingRaces.contains(where: { ($0.race_type ?? "").lowercased().contains("trail") || ($0.name ?? "").contains("越野") })
        let phase = coachAnalysis?.periodization_phase ?? (nextRace != nil ? "赛前减量调整期 (Taper)" : "进阶期 (Introductory Phase)")
        
        // 0. 身份与大模型简介问答 (如：“你是谁”、“你是什么模型”、“介绍一下你自己”)
        if isCoachIdentityQuery(q) {
            return """
👋 你好！我是 **RGM AI 耐力与恢复教练（Canova 教练）**。

🤖 **当前驱动的 LLM 模型**：
• **核心大模型**：**阿里云通义千问旗舰大模型 Qwen-Max (`qwen-max`)**
• **协同量化引擎**：RGM 运动生理学推理引擎（融合 Banister CTL/ATL/TSB 负荷动力学、Jack Daniels VDOT 跑力模型与 WHOOP 级生理恢复算法）

🏃‍♂️ **教练简介与训练哲学**：
我以意大利传奇马拉松与耐力训练大师 **Renato Canova（雷纳托·卡诺瓦）** 的科学训练体系为核心方法论，专注于为路跑与山地越野跑者提供一对一动态指导：
1. **Canova 专项周期化推进**：围绕您的目标赛事（当前：**\(targetRace)** · **\(phase)**），按「基础期 → 专项准备期 → 专项期 → 赛前减量期 (Taper)」动态演进，强调比赛配速收敛与山地垂直耐力，坚决杜绝无效“垃圾跑量”；
2. **WHOOP 级全天候恢复监测**：实时追踪您手表同步的夜间 **HRV（心率变异性）**、**静息心率 (RHR)**、**睡眠质量/睡眠债** 与日间 **Strain 生理负荷**，在晨间主动为您定制当日恢复与训练处方；
3. **Banister 负荷与多赛事统筹**：量化监控您的体能储备（当前 CTL \(String(format: "%.1f", ctlVal))）、急性疲劳（ATL \(String(format: "%.1f", atlVal))）与状态平衡指数（TSB \(tsbSign)，\(statusLabel)），科学统筹赛季 A/B/C 级赛事节奏，严防过度训练与运动损伤。
"""
        }
        
        // 1. 课表可行性与大负荷决断 (如：“明天再去跑30公里越野合适吗”)
        if q.contains("合适") || q.contains("能不能") || q.contains("可以吗") || q.contains("要不要") || q.contains("行不行") || q.contains("再跑") || q.contains("建议跑") || q.contains("跑不跑") {
            let isHeavy = q.contains("30") || q.contains("40") || q.contains("50") || q.contains("越野") || q.contains("大课") || q.contains("长距离") || q.contains("背靠背") || q.contains("全马")
            if isHeavy {
                return """
【Canova 教练裁决】：不建议盲目执行！

虽然您当前的 TSB 为 \(tsbSign)（处于\(statusLabel)），身体处于较好恢复窗口，但连续或盲目进行 30 公里以上大距离越野极易造成股四头肌离心肌纤维撕裂与深层结缔组织无效疲劳堆叠。

在 Canova 专项哲学中，“恢复也是训练的关键一环”。大负荷大课之间必须预留完整的超量补偿周期。

💡 明日建议调整方案：
• 方案 A（主动恢复）：将距离严格压缩至 15 ~ 18 公里以内（山地徒步或平路慢跑，时间不超 2 小时），全程心率压在持续有氧稳态区 (134-148 bpm)，重点演练下坡步频技术，切忌拼配速；
• 方案 B（彻底超量恢复）：安排完全休息或低阻力椭圆机/动感单车排酸 45 分钟，让神经肌肉完成深层修复，确保后续专项课质量。
"""
            } else {
                return """
【Canova 教练裁决】：可以执行，但须严格控制强度。

当前您的体能储备 CTL 为 \(String(format: "%.1f", ctlVal))，TSB 为 \(tsbSign)。当前具备训练吸收空间，但请务必杜绝既不慢又不够快的“中间垃圾配速”：
• 有氧跑课表：全程心率维持在 134-148 bpm 持续有氧区；
• 若计划跑间歇：务必严格按照专项配速执行，宁可少跑一组，绝不降低质量。
"""
            }
        }
        
        // 2. 身体疲劳与伤痛预警
        if q.contains("累") || q.contains("酸痛") || q.contains("膝盖") || q.contains("痛") || q.contains("心率高") || q.contains("足底") || q.contains("跟腱") || q.contains("受伤") || q.contains("不舒服") {
            return """
⚠️ 【Canova 运动生理与伤病防范警告】

当身体出现局限性酸痛或疲劳信号时，坚决严禁硬撑大课！组织适应具有滞后性，心肺耐力提升快于骨骼、肌腱的重塑周期。

🩺 紧急应对建议：
1. 立即停止任何高冲击下坡跑与大强度专项间歇；
2. 监测晨起静息心率与 HRV：若静息心率较平时升高 5 bpm 以上，代表自主神经系统处于交感亢奋疲劳期；
3. 执行 RICE 原则与筋膜球/泡沫轴局部深层放松，补充水合与高蛋白营养；
4. 若疼痛持续 48 小时以上，请及时寻求专业运动医学科医生评估。
"""
        }
        
        // 3. 负荷与 TSB 动力学诊断
        if q.contains("负荷") || q.contains("tsb") || q.contains("ctl") || q.contains("atl") || q.contains("体能") || q.contains("状态") {
            let dynamicInterpretation: String
            if tsbVal > 15 {
                dynamicInterpretation = """
1. 巅峰储备就绪：当前 TSB 显著为正 (\(tsbSign))，前期训练负荷已充分超量补偿 (Supercompensation)，身体机能与神经敏锐度达到巅峰。
2. 防范“体能钝化”：在 Canova 体系中，TSB 过高持续过久会导致氧化酶活性与毛细血管募集效率钝化，建议穿插高质量的短距离神经肌肉激活课。
"""
            } else if tsbVal >= -10 {
                dynamicInterpretation = """
1. 负荷动态平衡：当前 TSB 为 \(tsbSign)，体能储备 (CTL \(String(format: "%.1f", ctlVal))) 与近期疲劳 (ATL \(String(format: "%.1f", atlVal))) 处于平稳吸收期，属于高价值的专项训练窗口。
2. 稳步推进专项课：身体具备良好吸收空间，建议按既定周期扎实完成混氧门槛与专项耐力课，杜绝无效“中间垃圾跑量”。
"""
            } else if tsbVal >= -30 {
                dynamicInterpretation = """
1. 专项负荷累积：当前 TSB 为 \(tsbSign)，近期训练强度及跑量密集，急性疲劳处于正常累积与刺激阶段。
2. 重视吸收转化：此阶段需确保大负荷课后 48 小时内的营养补充、电解质水合与充足深睡眠，避免连续安排高强度重课。
"""
            } else {
                dynamicInterpretation = """
1. 疲劳深度承压预警：当前 TSB 为 \(tsbSign)，近期负荷已大幅超出长期适应基线，肌纤维与中枢神经系统疲劳显著。
2. 强制减量排酸：强烈建议预留 48~72 小时低心率排酸或彻底休整，防止过度训练导致运动损伤。
"""
            }

            var msg = """
⚡ 【Canova 训练负荷与 TSB 动力学诊断】

📊 实时核心生理平衡指标：
• 长期体能储备 (CTL)：\(String(format: "%.1f", ctlVal))
• 急性疲劳负荷 (ATL)：\(String(format: "%.1f", atlVal))
• 状态平衡指数 (TSB)：\(tsbSign)
• 当前生理形态：\(statusLabel)

🎯 Renato Canova 专项哲学深度解读：
\(dynamicInterpretation)
"""
            if let fitness = coachAnalysis?.fitness_status {
                msg += "\n\n💡 专项诊断详情：\n\(fitness)"
            } else if let suggestions = coachAnalysis?.key_suggestions, !suggestions.isEmpty {
                msg += "\n\n💡 关键战术建议：\n" + suggestions.map { "• \($0)" }.joined(separator: "\n")
            }
            if let workout = coachAnalysis?.focus_workout_of_the_week {
                msg += "\n\n🏃 本周推荐关键专项课：\n\(workout)"
            }
            return msg
        }
        
        // 4. 周末长距离专项安排 (必须同时包含周末/长距离与安排/多长)
        if (q.contains("周末") || q.contains("长距离") || q.contains("lsd")) && (q.contains("安排") || q.contains("计划") || q.contains("多长") || q.contains("跑什么") || q.contains("课表")) {
            if isTrail {
                return """
🏃 【Canova 山地超马长距离专项安排】
针对目标赛事【\(targetRace)】，当前处于【\(phase)】。Canova 哲学铁律：杜绝无目的的慢摇‘垃圾跑量’，山地超马必须高度模拟实战！

📋 建议周末执行方案（以驻留时间与爬升为核心）：
• 建议时间：3 ~ 4 小时有效山地驻留 (Time on Feet)
• 心率与爬升节奏架构：
  1. 上坡段：坚决压制心率在持续有氧区 (134-148 bpm)，熟练运用双杖或快步走 (Power Hiking) 提升垂直速度 (VAM)；
  2. 平缓山径：保持均匀小步频巡航，严禁盲目冲刺；
  3. 下坡技术段：重心微前倾、小步高频轻盈落地，重点演练股四头肌离心卸力，防范肌肉撕裂损伤。

🥤 胃肠代谢与补给实战演练：
每 40~45 分钟补充 1 支高能胶 (30-40g 碳水)，小口勤饮电解质水，深度模拟比赛日肠胃高负荷吸收耐受度！
"""
            } else {
                return """
🏃 【Canova 周末长距离专项安排】
针对目标赛事【\(targetRace)】，当前处于【\(phase)】。Canova 哲学铁律：杜绝无目的的慢摇‘垃圾跑量’，周末长距离必须高度模拟实战！

📋 建议周末执行方案：
• 建议距离：24 ~ 28 公里
• 配速与心率节奏架构：
  1. 初始段 (1~10 km)：持续有氧稳态区 (心率 134-148 bpm)，平稳激活脂代谢；
  2. 核心段 (11~22 km)：提升至混氧门槛巡航 (心率 150-162 bpm)，模拟后程抗疲劳推进；
  3. 冲刺段 (最后 2~3 km)：保持步频刚性与神经紧张度。

🥤 补给与肠胃演练：
每 45 分钟摄入 1 支高能胶 (30-40g 碳水)，小口补充电解质水，深度演练比赛日肠胃吸收耐受度！
"""
            }
        }
        
        if q.contains("乳酸") || q.contains("阈值") || q.contains("门槛") || q.contains("提升") || q.contains("配速") || q.contains("提高") {
            return """
⚡ 【Canova 乳酸门槛 (LT2) 巡航动力学】
提升乳酸阈值配速的核心，绝不是盲目跑力竭，而是通过「混氧门槛巡航 (Continuous Threshold)」与「间歇漂浮跑 (Float Recoveries)」，提升心肌与慢肌纤维对乳酸的再利用清除效率。

🔥 经典 Canova 专项课模版 (Special Block)：
1. 间歇漂浮跑：
   • 4 × 3000m @ 目标乳酸门槛配速（心率 155-165 bpm）
   • 每组间隔 1000m「漂浮跑 (Float)」恢复（而非慢走！心率维持在 140-148 bpm 巡航，强迫身体在动态中吸收乳酸）。
2. 持续渐进跑 (Progressive Run)：
   • 14 ~ 16 公里：前 6km 基础有氧 -> 中间 6km 门槛前沿 -> 最后 2-3km 逼近目标比赛配速。

⚠️ 注意事项：
大负荷门槛课后必须预留 48~72 小时超量恢复窗口，切忌连续两天堆叠高强度！
"""
        }
        
        if q.contains("全马") || q.contains("破3") || q.contains("课表") || q.contains("周期") || q.contains("准备期") || q.contains("马拉松") {
            return """
🏅 【Canova 全马专项突破体系】
从马拉松科学训练视角，全马破局的核心是「专项配速收敛 (Specific Pace Extension)」与「糖原节约效率」，严禁混淆各阶段训练重点：

📅 四大宏观周期进阶：
1. 基础期 (Fundamental, 4-6周)：建立微血管网与慢肌有氧底座，辅以基础力量与坡道冲刺。
2. 专项准备期 (Special, 4-6周)：扩展乳酸门槛 (LT2) 巡航区间，消除‘中间垃圾配速’。
3. 专项期 (Specific, 4-6周)：全马核心灵魂！进行 100% 目标配速 (MP) 的 24~35 公里超长距离实战延伸课。
4. 减量调整期 (Taper, 2周)：D-14 削减 35% 跑量，D-7 削减 60%，保持短距离高配速神经兴奋性，使 TSB 冲上 +10~+15 巅峰就绪状态！
"""
        }
        
        if q.contains("越野") || q.contains("爬升") || q.contains("山地") || q.contains("下坡") || q.contains("海拔") {
            return """
🏔️ 【Canova 山地越野专项哲学】
越野耐力赛与平路路跑截然不同，胜负关键在于：心率储备 (%HRR) 控制、垂直爬升 (D+) 功率输出以及下坡股四头肌离心抗撕裂耐受。

🧗 核心实战策略：
1. 爬坡上行 (Power Hiking)：结合双杖与前脚掌发力，将心率控制在 134-151 bpm 稳态区间，严禁过早顶爆红线导致肌糖原提前耗竭。
2. 技术下坡 (Technical Downhill)：保持高步频与低重心，利用重力顺势下落，避免硬刹车冲击膝关节软骨。
3. 赛程冲突警惕：多赛事日历中，若两场长距离越野间隔 < 21 天，必须将后一场设为 C 标（以赛代练），严禁连续拼全力突破，防止应力性骨折与中枢神经过度消耗！
"""
        }
        
        if q.contains("恢复") || q.contains("累") || q.contains("心率") || q.contains("睡眠") || q.contains("生病") || q.contains("疲劳") || q.contains("酸痛") {
            let sleepScore = dashboard.todayHealth?.sleep_score ?? 85
            let rhr = dashboard.todayHealth?.resting_heart_rate ?? 50
            let hrv = dashboard.todayHealth?.hrv_status ?? "均衡良好"
            let advice = coachAnalysis?.recovery_advice ?? "大师组跑者深层肌纤维与结缔组织微损伤至少需要 72~96 小时超量恢复。若感觉疲劳明显或晨脉偏高 5+ bpm，今日应坚决放弃主课，改为 30-40 分钟心率 < 130 bpm 的排酸极慢跑或彻底跑休，保证 8 小时优质睡眠与高蛋白补充。"
            
            return """
🌿 【Canova 生理机能与超量恢复指导】
• 今日睡眠评分：\(sleepScore) 分
• 静息心率 (RHR)：\(rhr) bpm
• HRV 状态：\(hrv)

💡 恢复战术建议：
\(advice)

记住：体能是在深度睡眠与超量补偿中增长的，而不是在疲劳训练中增长的！疲劳时勇于减量休整，才能保证下一次专项课的绝对质量。
"""
        }
        
        // General query fallback
        let summary = coachAnalysis?.summary ?? "坚持专项化训练，注重有氧底座与比赛目标配速收敛。"
        let suggestions = coachAnalysis?.key_suggestions?.joined(separator: "\n• ") ?? "保持80/20极化训练，大负荷后留足恢复窗口。"
        
        return """
⚡ 【Canova 教练专项答复】
当前备赛目标：【\(targetRace)】 · 阶段：【\(phase)】

🎯 核心战略指导：
\(summary)

💡 关键执行要点：
• \(suggestions)

如果针对具体配速、周末课表或特定比赛战术有疑问，随时点击下方快捷按钮或直接向我提问！
"""
    }
    
    func updateFullProfile(_ dict: [String: Any]) async throws {
        guard let uid = currentUser?.id else { return }
        isSavingProfile = true
        defer { isSavingProfile = false }
        let res = try await APIService.shared.updateProfile(uid: uid, data: dict)
        self.fullProfile = res.profile
        if let g = res.goal {
            self.userGoal = g
        }
        self.userRaces = res.races ?? []
        if let newName = res.profile?.display_name, !newName.isEmpty {
            self.currentUser?.display_name = newName
        }
        if let newAvatar = res.profile?.avatar_url, !newAvatar.isEmpty {
            self.currentUser?.avatar_url = newAvatar
        }
    }
    
    func saveUserGoal(targetDistance: Int, weeklyTarget: Int, monthlyTargets: [Int]) async throws {
        guard let uid = currentUser?.id ?? fullProfile?.id, !uid.isEmpty else { return }
        isSavingProfile = true
        defer { isSavingProfile = false }
        if let updatedGoal = try await APIService.shared.updateUserGoal(
            uid: uid,
            targetDistance: targetDistance,
            weeklyTarget: weeklyTarget,
            monthlyTargets: monthlyTargets
        ) {
            self.userGoal = updatedGoal
        }
        await refreshData()
    }
    
    func syncDeviceBiometrics() async {
        guard let uid = currentUser?.id else { return }
        do {
            let res = try await APIService.shared.syncDeviceProfile(uid: uid)
            self.fullProfile = res.profile
            await refreshData()
        } catch {
            print("[AppState] syncDeviceBiometrics error: \(error)")
        }
    }
    
    func importGarminPB() async {
        guard let uid = currentUser?.id else { return }
        do {
            let res = try await APIService.shared.importGarminPB(uid: uid)
            self.fullProfile = res.profile
            await refreshData()
        } catch {
            print("[AppState] importGarminPB error: \(error)")
        }
    }
    
    // MARK: - Race Management
    
    func saveRace(_ raceData: [String: Any]) async throws {
        guard let uid = currentUser?.id ?? fullProfile?.id, !uid.isEmpty else { return }
        let updatedRaces = try await APIService.shared.saveRacePlan(uid: uid, raceData: raceData)
        self.userRaces = updatedRaces
        await refreshData()
    }
    
    func deleteRace(raceId: String) async throws {
        guard let uid = currentUser?.id ?? fullProfile?.id, !uid.isEmpty else { return }
        let updatedRaces = try await APIService.shared.deleteRacePlan(uid: uid, raceId: raceId)
        self.userRaces = updatedRaces
        await refreshData()
    }
    
    func lookupRaceIntel(
        raceName: String,
        raceType: String?,
        targetTime: String?,
        raceDate: String?,
        raceId: String?
    ) async throws -> RaceIntelLookupResponse {
        let uid = currentUser?.id ?? fullProfile?.id
        let res = try await APIService.shared.lookupRaceIntelligence(
            uid: uid,
            raceName: raceName,
            raceType: raceType,
            targetTime: targetTime,
            raceDate: raceDate,
            raceId: raceId
        )
        // If backend auto-persisted race_info to an existing race, refresh local races list
        if let uid = uid, !uid.isEmpty, let rid = raceId, !rid.isEmpty, res.success == true {
            if let pRes = try? await APIService.shared.fetchFullProfile(uid: uid), let rList = pRes.races {
                self.userRaces = rList
            }
        }
        return res
    }
    
    func saveRaceInfo(raceId: String, raceInfo: RaceInfoData) async throws {
        guard let uid = currentUser?.id ?? fullProfile?.id, !uid.isEmpty else { return }
        let updatedRaces = try await APIService.shared.updateRaceInfo(
            uid: uid,
            raceId: raceId,
            raceInfo: raceInfo.toDictionary()
        )
        if !updatedRaces.isEmpty {
            self.userRaces = updatedRaces
        }
    }
    
    func updateRacePriority(raceId: String, priority: Int) async throws {
        guard let uid = currentUser?.id ?? fullProfile?.id, !uid.isEmpty else { return }
        let updatedRaces = try await APIService.shared.updateRacePriority(
            uid: uid,
            raceId: raceId,
            priority: priority
        )
        if !updatedRaces.isEmpty {
            self.userRaces = updatedRaces
        }
    }
    
    func matchRaceActivity(raceId: String, raceDate: String) async throws -> MatchedRaceActivityResponse {
        guard let uid = currentUser?.id ?? fullProfile?.id, !uid.isEmpty else {
            throw APIError.serverError("请先登录")
        }
        return try await APIService.shared.fetchMatchedRaceActivity(uid: uid, raceId: raceId, raceDate: raceDate)
    }
    
    func uploadRacePhoto(raceId: String, imageData: Data) async throws -> (photoUrl: String?, photos: [String]) {
        guard let uid = currentUser?.id ?? fullProfile?.id, !uid.isEmpty else {
            throw APIError.serverError("请先登录")
        }
        let b64 = imageData.base64EncodedString()
        let res = try await APIService.shared.uploadRacePhotoBase64(uid: uid, raceId: raceId, imageBase64: b64, ext: ".jpg")
        if let updatedRaces = res.races, !updatedRaces.isEmpty {
            self.userRaces = updatedRaces
        }
        return (res.photoUrl, res.photos)
    }
    
    func deleteRacePhoto(raceId: String, photoUrl: String) async throws -> [String] {
        guard let uid = currentUser?.id ?? fullProfile?.id, !uid.isEmpty else {
            throw APIError.serverError("请先登录")
        }
        let res = try await APIService.shared.deleteRacePhoto(uid: uid, raceId: raceId, photoUrl: photoUrl)
        if let updatedRaces = res.races, !updatedRaces.isEmpty {
            self.userRaces = updatedRaces
        }
        return res.photos
    }
    
    // MARK: - Club Reports, Cockpit & Events
    func logout() {
        MorningBriefingManager.shared.cancelAll()
        StorageManager.shared.clear()
        currentUser = nil
        isLoggedIn = false
        dashboard = DashboardData()
        scienceMetrics = nil
        healthTrend = []
        activePlan = nil
        coachAnalysis = nil
        fullProfile = nil
        userGoal = nil
        userRaces = []
    }
    
    // MARK: - Account Deletion (App Store Guideline 5.1.1(v))
    
    func deleteAccount() async {
        guard let uid = currentUser?.id ?? fullProfile?.id else {
            logout()
            return
        }
        do {
            _ = try await APIService.shared.deleteAccount(uid: uid)
        } catch {
            print("Delete account remote error: \(error)")
        }
        logout()
    }
    
    // MARK: - Watch Account Binding (Garmin / COROS)
    
    @discardableResult
    func bindWatch(brand: String, account: String, password: String, domain: String, mfaCode: String? = nil) async throws -> String {
        if isLoggedIn, let existing = connectedWatchBrand(), existing.id != brand {
            throw APIError.serverError("每个账号仅限连接一个运动手表，请先解绑【\(existing.label)】后再连接")
        }
        let (profile, message) = try await APIService.shared.bindOrLoginDevice(
            uid: currentUser?.id,
            brand: brand,
            account: account,
            password: password,
            domain: domain,
            mfaCode: mfaCode
        )
        StorageManager.shared.saveActivities([])
        StorageManager.shared.clearHealthKitUploaded(uid: profile.id)
        self.currentUser = profile
        self.isLoggedIn = true
        self.syncNotice = message ?? "设备绑定成功，正在同步最新运动记录..."
        await refreshData()
        Task { [weak self] in
            try? await Task.sleep(nanoseconds: 3_500_000_000)
            await self?.refreshData()
        }
        return message ?? "运动手表账号绑定成功 ✓"
    }
    
    func unbindWatch(brand: String) async throws -> String {
        guard let uid = currentUser?.id, !uid.isEmpty else {
            throw APIError.serverError("请先登录")
        }
        let msg = try await APIService.shared.unbindDevice(uid: uid, brand: brand)
        switch brand {
        case "garmin":
            self.currentUser?.garmin_connected = false
            self.currentUser?.garmin_email = nil
        case "coros":
            self.currentUser?.coros_connected = false
            self.currentUser?.coros_account = nil
        case "apple_watch":
            self.currentUser?.apple_watch_connected = false
            StorageManager.shared.clearHealthKitUploaded(uid: uid)
        case "huawei":
            self.currentUser?.huawei_connected = false
            self.currentUser?.huawei_account = nil
            StorageManager.shared.clearHealthKitUploaded(uid: uid)
        default:
            break
        }
        if let u = self.currentUser {
            StorageManager.shared.saveUser(u)
        }
        await refreshData()
        return msg
    }
    
    func importTrackFile(url: URL, brand: String = "huawei") async throws -> String {
        guard let uid = currentUser?.id, !uid.isEmpty else {
            throw APIError.serverError("请先登录")
        }
        if let existing = connectedWatchBrand(), existing.id != brand {
            throw APIError.serverError("每个账号仅限连接一个运动手表，请先解绑【\(existing.label)】后再导入")
        }
        let accessed = url.startAccessingSecurityScopedResource()
        defer {
            if accessed {
                url.stopAccessingSecurityScopedResource()
            }
        }
        let data = try Data(contentsOf: url)
        let b64 = data.base64EncodedString()
        let res = try await APIService.shared.importTrackFile(
            uid: uid,
            filename: url.lastPathComponent,
            contentBase64: b64,
            sourceBrand: brand
        )
        if brand == "huawei" {
            self.currentUser?.huawei_connected = true
            self.currentUser?.huawei_account = "华为运动健康 App"
        } else if brand == "apple_watch" {
            self.currentUser?.apple_watch_connected = true
        }
        if let u = self.currentUser {
            StorageManager.shared.saveUser(u)
        }
        await refreshData()
        return res.message ?? "轨迹文件导入成功 ✓"
    }
    
    // MARK: - Sign in with Apple
    
    func loginWithApple(userId: String, identityToken: String?, email: String?, fullName: String?) async throws {
        let profile = try await APIService.shared.appleLogin(
            appleUserId: userId,
            identityToken: identityToken,
            email: email,
            fullName: fullName
        )
        self.currentUser = profile
        self.isLoggedIn = true
        await refreshData()
    }
    
    // MARK: - Demo Account Fast Login for Reviewers & Users
    
    /// Signs into a dedicated synthetic demo account provided by the backend (no real user data).
    func loginDemoAccount() async throws {
        let profile = try await APIService.shared.demoLogin()
        self.currentUser = profile
        self.isLoggedIn = true
        await refreshData()
    }
    
    // MARK: - WHOOP-Style Physiological Recovery, Strain, Sleep & Journal Engine
    
    private static var todayKeyString: String {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Asia/Shanghai") ?? .current
        f.dateFormat = "yyyy-MM-dd"
        return f.string(from: Date())
    }
    
    func loadWhoopJournal(uid: String) {
        let defaults = UserDefaults.standard
        let histKey = "rgm_whoop_journal_v1_\(uid)"
        if let data = defaults.data(forKey: histKey),
           let decoded = try? JSONDecoder().decode([String: [String]].self, from: data) {
            self.journalHistory = decoded
        } else {
            self.journalHistory = [:]
        }
        let todayKey = Self.todayKeyString
        self.todayJournalBehaviors = Set(self.journalHistory[todayKey] ?? [])
        
        let wakeHKey = "rgm_whoop_wake_h_\(uid)"
        let wakeMKey = "rgm_whoop_wake_m_\(uid)"
        if defaults.object(forKey: wakeHKey) != nil {
            self.preferredWakeHour = defaults.integer(forKey: wakeHKey)
            self.preferredWakeMinute = defaults.integer(forKey: wakeMKey)
        }
    }
    
    func toggleJournalBehavior(_ behaviorId: String) {
        if todayJournalBehaviors.contains(behaviorId) {
            todayJournalBehaviors.remove(behaviorId)
        } else {
            todayJournalBehaviors.insert(behaviorId)
        }
        let todayKey = Self.todayKeyString
        journalHistory[todayKey] = Array(todayJournalBehaviors)
        if let uid = currentUser?.id, !uid.isEmpty {
            let histKey = "rgm_whoop_journal_v1_\(uid)"
            if let data = try? JSONEncoder().encode(journalHistory) {
                UserDefaults.standard.set(data, forKey: histKey)
            }
        }
        evaluateProactiveCoachAlerts()
    }
    
    func adjustWakeTime(minutesDelta: Int) {
        var totalMins = preferredWakeHour * 60 + preferredWakeMinute + minutesDelta
        if totalMins < 4 * 60 { totalMins = 4 * 60 }
        if totalMins > 10 * 60 { totalMins = 10 * 60 }
        preferredWakeHour = totalMins / 60
        preferredWakeMinute = totalMins % 60
        if let uid = currentUser?.id, !uid.isEmpty {
            UserDefaults.standard.set(preferredWakeHour, forKey: "rgm_whoop_wake_h_\(uid)")
            UserDefaults.standard.set(preferredWakeMinute, forKey: "rgm_whoop_wake_m_\(uid)")
        }
        evaluateProactiveCoachAlerts()
    }
    
    var habitImpacts: [WhoopHabitImpact] {
        // Map date -> HRV / derived recovery proxy, so we can compare "next morning" outcomes.
        var hrvByDate: [String: Int] = [:]
        for pt in healthTrend {
            if let d = pt.date, let h = pt.hrv, h > 0 { hrvByDate[String(d.prefix(10))] = h }
        }
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.dateFormat = "yyyy-MM-dd"
        func nextDay(_ s: String) -> String? {
            guard let d = f.date(from: s), let n = Calendar.current.date(byAdding: .day, value: 1, to: d) else { return nil }
            return f.string(from: n)
        }
        // Only days where the user actually opened the journal count as samples (yes or no).
        let journaledDays = journalHistory.keys.sorted()
        
        return WhoopJournalBehavior.allBehaviors.map { b in
            var yesHrv: [Int] = []
            var noHrv: [Int] = []
            for day in journaledDays {
                guard let nd = nextDay(day), let h = hrvByDate[nd] else { continue }
                if (journalHistory[day] ?? []).contains(b.id) { yesHrv.append(h) } else { noHrv.append(h) }
            }
            let loggedCount = journalHistory.values.filter { $0.contains(b.id) }.count
            // Require at least 3 samples on each side before showing a personal correlation.
            if yesHrv.count >= 3 && noHrv.count >= 3 {
                let yesAvg = Double(yesHrv.reduce(0, +)) / Double(yesHrv.count)
                let noAvg = Double(noHrv.reduce(0, +)) / Double(noHrv.count)
                let delta = yesAvg - noAvg
                let pct = noAvg > 0 ? Int((delta / noAvg * 100).rounded()) : 0
                return WhoopHabitImpact(behavior: b, impactPct: pct, hrvDeltaMs: Int(delta.rounded()),
                                        loggedDaysCount: loggedCount, isPersonalized: true,
                                        yesDays: yesHrv.count, noDays: noHrv.count)
            }
            return WhoopHabitImpact(behavior: b, impactPct: b.baseImpactPct, hrvDeltaMs: b.baseHrvDeltaMs,
                                    loggedDaysCount: loggedCount, isPersonalized: false,
                                    yesDays: yesHrv.count, noDays: noHrv.count)
        }.sorted {
            if $0.isPersonalized != $1.isPersonalized { return $0.isPersonalized }
            return abs($0.impactPct) > abs($1.impactPct)
        }
    }
    
    var whoopSnapshot: WhoopSnapshot {
        let th = dashboard.todayHealth
        let validHrvHistory = healthTrend.compactMap { $0.hrv }.filter { $0 > 0 }
        let validRhrHistory = healthTrend.compactMap { $0.resting_heart_rate }.filter { $0 > 0 }
        let validSleepHours = healthTrend.compactMap { pt -> Double? in
            if let h = pt.sleep_duration_hours, h > 0 { return h }
            if let s = pt.sleep_duration_seconds, s > 0 { return Double(s) / 3600.0 }
            return nil
        }
        
        let hrvBaseline = validHrvHistory.isEmpty ? (th?.hrv_weekly_avg ?? 58) : Int(Double(validHrvHistory.reduce(0, +)) / Double(validHrvHistory.count))
        let hrvToday = th?.hrv_ms ?? validHrvHistory.last ?? hrvBaseline
        
        let rhrBaseline = validRhrHistory.isEmpty ? (fullProfile?.resting_heart_rate ?? currentUser?.resting_heart_rate ?? 52) : Int(Double(validRhrHistory.reduce(0, +)) / Double(validRhrHistory.count))
        let rhrToday = th?.resting_heart_rate ?? validRhrHistory.last ?? rhrBaseline
        
        let actualSleepHours: Double = {
            if let h = th?.sleep_duration_hours, h > 0 { return h }
            if let lastS = validSleepHours.last, lastS > 0 { return lastS }
            return 7.3
        }()
        
        var missingInputs: [String] = []
        if th?.hrv_ms == nil && validHrvHistory.isEmpty { missingInputs.append("HRV") }
        if th?.resting_heart_rate == nil && validRhrHistory.isEmpty { missingInputs.append("静息心率") }
        if (th?.sleep_duration_hours ?? 0) <= 0 && validSleepHours.isEmpty { missingInputs.append("睡眠") }
        
        // 1. Today's Running TRIMP, Daytime Daily Activities (Steps & Active Calories) & Strain (0 - 21 logarithmic scale)
        let todayPrefix = Self.todayKeyString
        let todayRuns = dashboard.recentActivities.filter { ($0.start_time ?? "").hasPrefix(todayPrefix) }
        var todayWorkoutTrimp = todayRuns.compactMap { $0.trimp }.reduce(0.0, +)
        let totalTodayRunKm = todayRuns.map { $0.distanceKm }.reduce(0.0, +)
        if todayWorkoutTrimp <= 0 && !todayRuns.isEmpty {
            todayWorkoutTrimp = totalTodayRunKm * 9.5
        }
        // If no run today yet, also check latest fitnessHistory item
        if todayWorkoutTrimp <= 0, let lastHist = dashboard.fitnessForm?.history?.last, lastHist.date == todayPrefix {
            todayWorkoutTrimp = lastHist.trimp ?? 0.0
        }
        
        let localSteps = (localTodayHealth["steps"] as? Int) ?? 0
        let localKcal = (localTodayHealth["active_calories"] as? Int) ?? 0
        let localNapSec = (localTodayHealth["nap_duration_seconds"] as? Int) ?? 0
        let localHrMin = (localTodayHealth["hr_min"] as? Int) ?? 0
        let localHrMax = (localTodayHealth["hr_max"] as? Int) ?? 0
        let localStressAvg = (localTodayHealth["stress_avg"] as? Int)
        let localStressMax = (localTodayHealth["stress_max"] as? Int)
        
        let daytimeSteps = max(0, max(th?.steps ?? 0, localSteps))
        let daytimeActiveCalories = max(0, max(th?.active_calories ?? 0, localKcal))
        let mergedNapSec = max(th?.nap_duration_seconds ?? 0, localNapSec)
        let napMinutes = max(0, max(th?.nap_duration_minutes ?? 0, mergedNapSec / 60))
        let effectiveStressAvg = th?.stress_avg ?? localStressAvg
        let effectiveStressMax = th?.stress_max ?? localStressMax
        
        // All-Day Heart Rate Fluctuation & Autonomic Stress Score (0.0 - 3.0)
        let candidateHrMin = [th?.hr_min, localHrMin > 0 ? localHrMin : nil].compactMap { $0 }.min() ?? rhrToday
        let hrMinToday = min(rhrToday, candidateHrMin)
        let todayRunMaxHr = todayRuns.compactMap { $0.average_heartrate }.max().map { $0 + 14 } ?? 0
        let rawWatchHrMax = max(th?.hr_max ?? 0, localHrMax)
        let hrMaxToday = max(rawWatchHrMax, max(todayRunMaxHr, rhrToday + (daytimeSteps > 3000 ? 45 : 32)))
        
        var rawStress: Double
        if let wStress = effectiveStressAvg, wStress > 0 {
            // Map watch 0-100 stress level + peak stress onto WHOOP 0.0-3.0 autonomic stress scale, blended with HRV/RHR
            let peakBoost = Double(max(0, (effectiveStressMax ?? wStress) - 65)) * 0.012
            let watchMapped = Double(wStress) / 100.0 * 3.0 + peakBoost
            let bioStress = 1.0 + Double(rhrToday - rhrBaseline) * 0.10 - Double(hrvToday - hrvBaseline) * 0.025
            rawStress = 0.65 * watchMapped + 0.35 * bioStress
        } else {
            rawStress = 1.0 + Double(rhrToday - rhrBaseline) * 0.12 - Double(hrvToday - hrvBaseline) * 0.03
            let hrSpan = hrMaxToday - hrMinToday
            if hrSpan > 55 && todayRuns.isEmpty {
                rawStress += min(0.55, Double(hrSpan - 55) * 0.014)
            }
        }
        if todayJournalBehaviors.contains("high_work_stress") { rawStress += 0.45 }
        if todayJournalBehaviors.contains("alcohol") { rawStress += 0.55 }
        if todayJournalBehaviors.contains("foam_roll") || todayJournalBehaviors.contains("no_screen_bed") { rawStress -= 0.2 }
        if napMinutes >= 15 { rawStress -= 0.18 }
        let stressScore = (min(2.9, max(0.3, rawStress)) * 10).rounded() / 10.0
        let stressLevelLabel = stressScore < 1.0 ? "低压力 · 副交感修复态" : (stressScore < 2.0 ? "中等压力 · 日常生理激活" : "高压力 · 交感神经应激态")
        
        // Non-running daytime activity load (walking, commuting, daily chores, stress, HR fluctuations & Body Battery drain)
        var shCal = Calendar(identifier: .gregorian)
        shCal.timeZone = TimeZone(identifier: "Asia/Shanghai") ?? .current
        let nowComps = shCal.dateComponents([.hour, .minute], from: Date())
        let nowMinsOfDay = (nowComps.hour ?? 12) * 60 + (nowComps.minute ?? 0)
        let wakeTotalMins = preferredWakeHour * 60 + preferredWakeMinute
        let awakeHours = max(1.0, min(16.5, Double(max(60, nowMinsOfDay - wakeTotalMins)) / 60.0))
        
        let runStepsEst = Int((totalTodayRunKm * 1250.0).rounded())
        let nonRunSteps = max(0, daytimeSteps - runStepsEst)
        let runKcalEst = Int((totalTodayRunKm * 62.0).rounded())
        let nonRunKcal = max(0, daytimeActiveCalories - runKcalEst)
        
        let basalCircadianTrimp = 6.0 + awakeHours * 0.72
        let stepsTrimp = Double(nonRunSteps) / 1000.0 * 3.4
        let kcalTrimp = Double(nonRunKcal) / 100.0 * 2.6
        let watchStressTrimp = Double(max(0, (effectiveStressAvg ?? 25) - 20)) * 0.35 + Double(max(0, (effectiveStressMax ?? 50) - 60)) * 0.18 + (todayJournalBehaviors.contains("high_work_stress") ? 9.0 : 0.0)
        let hrFluctuationTrimp = todayRuns.isEmpty ? Double(max(0, (hrMaxToday - rhrToday) - 30)) * 0.22 : 0.0
        let bbMaxVal = th?.body_battery_max ?? 0
        let bbCurVal = th?.body_battery_current ?? bbMaxVal
        let bbDrainPts = max(0, bbMaxVal - bbCurVal)
        let bbDrainTrimp = Double(bbDrainPts) * 0.14
        
        let daytimeDynamicTrimp = min(48.0, stepsTrimp + kcalTrimp + watchStressTrimp + hrFluctuationTrimp + bbDrainTrimp)
        let baselineLivingTrimp = basalCircadianTrimp + daytimeDynamicTrimp
        let totalTrimp = todayWorkoutTrimp + baselineLivingTrimp
        
        // Logarithmic mapping onto WHOOP 0-21 scale:
        let rawDayStrain = min(20.7, max(2.1, 5.4 * log(1.0 + totalTrimp / 14.0)))
        let dayStrain = (rawDayStrain * 10).rounded() / 10.0
        let workoutStrain = todayWorkoutTrimp > 0 ? ((min(20.5, 5.2 * log(1.0 + todayWorkoutTrimp / 14.0)) * 10).rounded() / 10.0) : 0.0
        let livingStrain = max(2.1, ((min(15.5, 5.4 * log(1.0 + baselineLivingTrimp / 14.0)) * 10).rounded() / 10.0))
        let basalOnlyStrain = max(2.0, ((5.4 * log(1.0 + basalCircadianTrimp / 14.0)) * 10).rounded() / 10.0)
        let daytimeActivityStrainAdded = max(0.0, ((livingStrain - basalOnlyStrain) * 10).rounded() / 10.0)
        
        // 2. Sleep Need & Sleep Performance (incorporating daytime naps to reduce tonight's sleep need)
        let baselineSleepHours = 7.5
        let strainAddedMins = Int(min(75.0, max(10.0, dayStrain * 3.2)).rounded())
        let avgRecentSleep = validSleepHours.suffix(3).isEmpty ? actualSleepHours : (validSleepHours.suffix(3).reduce(0.0, +) / Double(validSleepHours.suffix(3).count))
        let sleepDebtMins = Int(max(0.0, min(95.0, (baselineSleepHours - avgRecentSleep) * 60.0 * 1.2)).rounded())
        let neededSleepHours = ((max(5.5, baselineSleepHours + Double(strainAddedMins + sleepDebtMins - napMinutes) / 60.0)) * 10).rounded() / 10.0
        let effectiveTotalSleepHours = actualSleepHours + Double(napMinutes) / 60.0
        let sleepPerformancePct = min(100, max(35, Int((effectiveTotalSleepHours / max(6.5, neededSleepHours + Double(napMinutes) / 60.0) * 100.0).rounded())))
        
        // 3. Recovery Score (0 - 100%): Morning Baseline vs. Real-Time Dynamic Readiness
        let hrvRatio = Double(hrvToday - hrvBaseline) / Double(max(15, hrvBaseline))
        let hrvComponent = min(100.0, max(15.0, 72.0 + hrvRatio * 115.0))
        let rhrDiff = Double(rhrBaseline - rhrToday) // Lower RHR than baseline = better recovery
        let rhrComponent = min(100.0, max(15.0, 72.0 + rhrDiff * 5.5))
        let sleepComponent = Double(sleepPerformancePct)
        
        let tsbVal = dashboard.fitnessForm?.tsb ?? scienceMetrics?.current_tsb ?? 0.0
        let tsbMod = min(6.0, max(-10.0, tsbVal * 0.22))
        
        let rawMorningRecovery = 0.52 * hrvComponent + 0.25 * rhrComponent + 0.23 * sleepComponent + tsbMod
        let morningRecoveryScore = min(99, max(12, Int(rawMorningRecovery.rounded())))
        let morningRecoveryZone: WhoopRecoveryZone = morningRecoveryScore >= 67 ? .green : (morningRecoveryScore >= 34 ? .yellow : .red)
        
        // Real-time daytime drain from Strain, Stress, HR fluctuation & Garmin Body Battery drain + Nap recharge
        let strainStressDrain = max(0.0, (dayStrain - 2.0) * 1.9 + max(0.0, stressScore - 0.8) * 5.5)
        let rawDrainPct: Double
        if bbDrainPts > 0 {
            let bbDrainScaled = Double(bbDrainPts) * 0.42
            rawDrainPct = 0.52 * strainStressDrain + 0.48 * bbDrainScaled
        } else {
            rawDrainPct = strainStressDrain
        }
        let daytimeRecoveryDrainPct = min(46, max(0, Int(rawDrainPct.rounded())))
        let daytimeNapBonusPct = napMinutes >= 15 ? min(12, Int((Double(napMinutes) * 0.18).rounded())) : 0
        let realtimeRecoveryScore = min(99, max(12, morningRecoveryScore - daytimeRecoveryDrainPct + daytimeNapBonusPct))
        let recoveryScore = realtimeRecoveryScore
        let recoveryZone: WhoopRecoveryZone = recoveryScore >= 67 ? .green : (recoveryScore >= 34 ? .yellow : .red)
        
        // Optimal Strain target band for the day driven by Morning Baseline Recovery Zone
        let optimalLow: Double
        let optimalHigh: Double
        switch morningRecoveryZone {
        case .green:
            optimalLow = 13.5
            optimalHigh = 17.5
        case .yellow:
            optimalLow = 9.5
            optimalHigh = 13.8
        case .red:
            optimalLow = 4.0
            optimalHigh = 8.5
        }
        
        let strainStateLabel: String
        if dayStrain < optimalLow {
            strainStateLabel = "恢复蓄能区 · 尚有负荷余量"
        } else if dayStrain <= optimalHigh {
            strainStateLabel = "最佳目标负荷区 (Optimal Strain) ✓"
        } else {
            strainStateLabel = "超量负荷突破区 (Overreaching)"
        }
        
        let bbSummaryText: String = {
            if bbMaxVal > 0 && bbCurVal > 0 && bbMaxVal != bbCurVal {
                return "，身体电量由晨起 \(bbMaxVal) 消耗至 \(bbCurVal)（-\(bbDrainPts)）"
            }
            return ""
        }()
        let napSummaryText = daytimeNapBonusPct > 0 ? "，午睡充电 +\(daytimeNapBonusPct)%" : ""
        
        let recoveryHeadline: String
        let recoveryDetail: String
        switch recoveryZone {
        case .green:
            recoveryHeadline = "副交感神经充沛，实时机能处于高就绪窗口"
            recoveryDetail = "晨起初始恢复 \(morningRecoveryScore)%（HRV \(hrvToday)ms / 静息心率 \(rhrToday)bpm），叠加日间活动与压力消耗 -\(daytimeRecoveryDrainPct)%\(napSummaryText)\(bbSummaryText)，当前实时恢复 \(realtimeRecoveryScore)%，适合执行专项课或耐力课。"
        case .yellow:
            recoveryHeadline = "晨起 \(morningRecoveryScore)% → 实时 \(realtimeRecoveryScore)%，机能处于日间动态消耗期"
            recoveryDetail = "晨起初始恢复 \(morningRecoveryScore)%，随今日步数 (\(daytimeSteps)步)、心率波动 (\(hrMinToday)–\(hrMaxToday)bpm) 与压力消耗 -\(daytimeRecoveryDrainPct)%\(napSummaryText)\(bbSummaryText)，当前实时机能余量 \(realtimeRecoveryScore)%，建议合理控制晚间强度并按时入睡。"
        case .red:
            recoveryHeadline = "实时机能余量偏低 (\(realtimeRecoveryScore)%)，亟需主动恢复与睡眠补偿"
            recoveryDetail = "晨起恢复 \(morningRecoveryScore)%，叠加今日日间消耗 -\(daytimeRecoveryDrainPct)%\(bbSummaryText)，当前交感神经疲劳明显，强烈建议放松排酸并在 \(String(format: "%02d:%02d", ((wakeTotalMins - Int((neededSleepHours * 60.0).rounded()) + 1440) % 1440) / 60, ((wakeTotalMins - Int((neededSleepHours * 60.0).rounded()) + 1440) % 1440) % 60)) 前入睡。"
        }
        
        // Recommended Bedtime calculation from preferredWakeHour:preferredWakeMinute
        let wakeTimeText = String(format: "%02d:%02d", preferredWakeHour, preferredWakeMinute)
        let bed100Mins = (wakeTotalMins - Int((neededSleepHours * 60.0).rounded()) + 1440) % 1440
        let bed85Mins = (wakeTotalMins - Int((neededSleepHours * 0.85 * 60.0).rounded()) + 1440) % 1440
        let recommendedBedtime100 = String(format: "%02d:%02d", bed100Mins / 60, bed100Mins % 60)
        let recommendedBedtime85 = String(format: "%02d:%02d", bed85Mins / 60, bed85Mins % 60)
        
        // Format lastUpdatedText from todayHealth.updated_at
        var lastUpdatedText = "日间自动同步已开启"
        if let upd = th?.updated_at, upd.count >= 16 {
            let isoFmt = ISO8601DateFormatter()
            isoFmt.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            let dt = isoFmt.date(from: upd) ?? ISO8601DateFormatter().date(from: upd)
            if let dt = dt {
                let hmFmt = DateFormatter()
                hmFmt.timeZone = TimeZone(identifier: "Asia/Shanghai") ?? .current
                hmFmt.dateFormat = "HH:mm"
                lastUpdatedText = "自动更新于 \(hmFmt.string(from: dt))"
            }
        }
        
        // 5. Healthspan & Runner Biological Age Delta
        let vo2 = th?.vo2_max ?? fullProfile?.vo2max ?? currentUser?.vo2max ?? scienceMetrics?.vdot ?? 52.0
        let ctl = dashboard.fitnessForm?.ctl ?? scienceMetrics?.current_ctl ?? 42.0
        // Higher VO2max, lower RHR, and consistent CTL reduce biological age relative to chronological norm
        let vo2Bonus = (vo2 - 42.0) * 0.28
        let rhrBonus = Double(62 - rhrToday) * 0.14
        let ctlBonus = min(2.5, ctl * 0.03)
        let rawAgeDelta = -min(12.0, max(-8.0, vo2Bonus + rhrBonus + ctlBonus))
        let bioAgeDelta = (rawAgeDelta * 10).rounded() / 10.0
        let rawPace = max(0.62, min(1.25, 1.0 + bioAgeDelta * 0.032))
        let paceOfAging = (rawPace * 100).rounded() / 100.0
        
        let sourceBrand = connectedWatchBrand()?.label ?? "智能运动手表"
        
        return WhoopSnapshot(
            recoveryScore: recoveryScore,
            morningRecoveryScore: morningRecoveryScore,
            realtimeRecoveryScore: realtimeRecoveryScore,
            daytimeRecoveryDrainPct: daytimeRecoveryDrainPct,
            daytimeNapBonusPct: daytimeNapBonusPct,
            recoveryZone: recoveryZone,
            recoveryHeadline: recoveryHeadline,
            recoveryDetail: recoveryDetail,
            dayStrain: dayStrain,
            workoutStrain: workoutStrain,
            baselineLivingStrain: livingStrain,
            daytimeActivityStrainAdded: daytimeActivityStrainAdded,
            optimalStrainLow: optimalLow,
            optimalStrainHigh: optimalHigh,
            strainStateLabel: strainStateLabel,
            sleepPerformancePct: sleepPerformancePct,
            actualSleepHours: (actualSleepHours * 10).rounded() / 10.0,
            neededSleepHours: neededSleepHours,
            baselineSleepHours: baselineSleepHours,
            strainAddedSleepMinutes: strainAddedMins,
            sleepDebtMinutes: sleepDebtMins,
            recommendedBedtime100: recommendedBedtime100,
            recommendedBedtime85: recommendedBedtime85,
            wakeTimeText: wakeTimeText,
            hrvToday: hrvToday,
            hrvBaseline: hrvBaseline,
            rhrToday: rhrToday,
            rhrBaseline: rhrBaseline,
            stressScore: stressScore,
            stressLevelLabel: stressLevelLabel,
            daytimeSteps: daytimeSteps,
            daytimeActiveCalories: daytimeActiveCalories,
            napMinutes: napMinutes,
            watchStressAvg: effectiveStressAvg,
            watchStressMax: effectiveStressMax,
            hrMinToday: hrMinToday,
            hrMaxToday: hrMaxToday,
            bodyBatteryCurrent: th?.body_battery_current ?? th?.body_battery_max,
            bodyBatteryMax: th?.body_battery_max,
            lastUpdatedText: lastUpdatedText,
            vo2Max: (vo2 * 10).rounded() / 10.0,
            biologicalAgeDelta: bioAgeDelta,
            paceOfAging: paceOfAging,
            dataSourceLabel: sourceBrand,
            missingInputs: missingInputs
        )
    }
    
    // MARK: - Proactive AI Coach Monitoring & Alert Engine
    
    func evaluateProactiveCoachAlerts() {
        let snap = whoopSnapshot
        let tsb = dashboard.fitnessForm?.tsb ?? scienceMetrics?.current_tsb ?? 0.0
        let ctl = dashboard.fitnessForm?.ctl ?? scienceMetrics?.current_ctl ?? 0.0
        var alerts: [ProactiveCoachAlert] = []
        
        // 1. Recovery & Autonomic Nervous System Alert
        if snap.recoveryZone == .red {
            alerts.append(ProactiveCoachAlert(
                id: "recovery_red",
                severity: "critical",
                category: "恢复预警",
                icon: "exclamationmark.triangle.fill",
                title: "今日恢复度处于红灯区 (\(snap.recoveryScore)%)，建议降级高强度课表",
                message: "晨起 HRV (\(snap.hrvToday)ms) 较基线 (\(snap.hrvBaseline)ms) 偏低或静息心率 (\(snap.rhrToday)bpm) 偏高，交感神经疲劳尚未解除。今日建议将目标负荷控制在 Strain \(String(format: "%.1f", snap.optimalStrainLow))-\(String(format: "%.1f", snap.optimalStrainHigh)) 以内。",
                metricTag: "Recovery \(snap.recoveryScore)% · RHR \(snap.rhrToday)bpm",
                actionLabel: "请教练降级今日课表",
                actionPrompt: "我今天的WHOOP恢复度只有\(snap.recoveryScore)%（红灯区），HRV \(snap.hrvToday)ms，静息心率\(snap.rhrToday)bpm，请帮我把今天的跑步课表调整为安全的恢复方案。"
            ))
        } else if snap.recoveryZone == .green {
            alerts.append(ProactiveCoachAlert(
                id: "recovery_green",
                severity: "optimal",
                category: "巅峰窗口",
                icon: "bolt.heart.fill",
                title: "今日恢复度绿灯 (\(snap.recoveryScore)%)，处于高质量专项课冲击窗口",
                message: "您的副交感神经恢复充沛（HRV \(snap.hrvToday)ms / RHR \(snap.rhrToday)bpm），身体可承受 Strain \(String(format: "%.1f", snap.optimalStrainLow))-\(String(format: "%.1f", snap.optimalStrainHigh)) 的专项训练刺激。",
                metricTag: "Recovery \(snap.recoveryScore)% · 绿灯就绪",
                actionLabel: "生成今日专项配速方案",
                actionPrompt: "我今天恢复度达到\(snap.recoveryScore)%（绿灯巅峰区），最佳目标负荷Strain \(String(format: "%.1f", snap.optimalStrainLow))-\(String(format: "%.1f", snap.optimalStrainHigh))，请给我制定今天的高质量专项训练配速与心率执行方案。"
            ))
        } else {
            alerts.append(ProactiveCoachAlert(
                id: "recovery_yellow",
                severity: "info",
                category: "恢复评估",
                icon: "waveform.path.ecg",
                title: "今日恢复度黄灯 (\(snap.recoveryScore)%)，宜执行稳态有氧训练",
                message: "HRV \(snap.hrvToday)ms（基线 \(snap.hrvBaseline)ms），身体处于常规负荷吸收期。建议今日总负荷控制在 Strain \(String(format: "%.1f", snap.optimalStrainLow))-\(String(format: "%.1f", snap.optimalStrainHigh)) 区间。",
                metricTag: "Recovery \(snap.recoveryScore)% · 稳态区",
                actionLabel: "查看今日心率控制建议",
                actionPrompt: "我今天恢复度为\(snap.recoveryScore)%（黄灯稳态区），请告诉我今天跑步应该把心率和配速控制在什么区间最科学？"
            ))
        }
        
        // 2. Strain & TSB Load Monitoring Alert
        if snap.dayStrain > snap.optimalStrainHigh || tsb < -22 {
            alerts.append(ProactiveCoachAlert(
                id: "strain_overreach",
                severity: "warning",
                category: "负荷监控",
                icon: "flame.fill",
                title: "生理负荷突破上限 (Strain \(String(format: "%.1f", snap.dayStrain)) / TSB \(String(format: "%.1f", tsb)))",
                message: "今日累积心血管负荷已超出最佳靶区上限 (\(String(format: "%.1f", snap.optimalStrainHigh))) 或近期急性疲劳较高。请立即启动跑后糖原补给与筋膜放松，明日严禁背靠背大强度课。",
                metricTag: "Strain \(String(format: "%.1f", snap.dayStrain)) / 21",
                actionLabel: "获取超量负荷排酸方案",
                actionPrompt: "我今天的身体负荷已经达到 Strain \(String(format: "%.1f", snap.dayStrain))（TSB \(String(format: "%.1f", tsb))），超出了最佳负荷区间，请给我今晚和明天的排酸恢复与饮食补给建议。"
            ))
        }
        
        // 3. Sleep Coach & Bedtime Prescription Alert
        if snap.sleepDebtMinutes >= 25 || snap.sleepPerformancePct < 82 {
            alerts.append(ProactiveCoachAlert(
                id: "sleep_prescription",
                severity: "warning",
                category: "睡眠处方",
                icon: "bed.double.fill",
                title: "睡眠教练提醒：今晚建议 \(snap.recommendedBedtime85) - \(snap.recommendedBedtime100) 入睡",
                message: "昨晚睡眠 \(String(format: "%.1f", snap.actualSleepHours)) 小时（表现 \(snap.sleepPerformancePct)%）。叠加今日 Strain 负荷 (\(String(format: "%.1f", snap.dayStrain))) 与睡眠债 (\(snap.sleepDebtMinutes)分钟)，今晚需睡满 \(String(format: "%.1f", snap.neededSleepHours)) 小时以完成肌纤维修复。",
                metricTag: "需睡 \(String(format: "%.1f", snap.neededSleepHours))h · \(snap.recommendedBedtime100)入睡",
                actionLabel: "咨询提升深睡与HRV方案",
                actionPrompt: "我昨晚睡了\(String(format: "%.1f", snap.actualSleepHours))小时，今晚需要睡\(String(format: "%.1f", snap.neededSleepHours))小时，作为跑者有哪些立竿见影的方法可以提高今晚慢波深睡和夜间HRV？"
            ))
        }
        
        // 4. WHOOP Journal Negative Habit Trigger Alert
        let negativeLogged = WhoopJournalBehavior.allBehaviors.filter { !$0.isPositiveHabit && todayJournalBehaviors.contains($0.id) }
        if !negativeLogged.isEmpty {
            let names = negativeLogged.map { $0.title }.joined(separator: "、")
            let totalPenalty = negativeLogged.map { $0.baseImpactPct }.reduce(0, +)
            alerts.append(ProactiveCoachAlert(
                id: "journal_trigger",
                severity: "warning",
                category: "习惯联动",
                icon: "checklist.unchecked",
                title: "行为日志提醒：「\(names)」可能拉低明早恢复",
                message: "您在今日习惯日志中记录了【\(names)】。运动医学研究普遍显示这类行为会推高夜间静息心率、压缩慢波深睡（参考影响约 \(abs(totalPenalty))%，积累足够日志后将替换为您的个人数据）。建议睡前补充 400ml 电解质水，明早若恢复偏低则推迟强度课。",
                metricTag: "参考影响 \(totalPenalty)% Recovery",
                actionLabel: "请教练定制补救措施",
                actionPrompt: "我今天在行为日志里记录了【\(names)】，应该怎么补救才能尽量减少对今晚HRV恢复和明天跑步训练的负面影响？"
            ))
        }
        
        // 5. Data gap disclosure – the coach is explicit when scores rely on defaults
        if !snap.missingInputs.isEmpty {
            alerts.insert(ProactiveCoachAlert(
                id: "data_gap",
                severity: "info",
                category: "数据完整度",
                icon: "antenna.radiowaves.left.and.right.slash",
                title: "缺少 \(snap.missingInputs.joined(separator: "、")) 数据，恢复评分为估算值",
                message: "请佩戴手表入睡并在「我的」页面同步最新数据。佳明/高驰需在手表中开启夜间 HRV 与睡眠监测；Apple Watch 需开启睡眠追踪。",
                metricTag: "来源：\(snap.dataSourceLabel)",
                actionLabel: "如何获取更准确的恢复数据",
                actionPrompt: "我的恢复评分缺少\(snap.missingInputs.joined(separator: "、"))数据，我用的是\(snap.dataSourceLabel)，应该怎么设置才能让夜间HRV和睡眠数据更完整准确？"
            ), at: 0)
        }
        
        self.proactiveAlerts = alerts
        
        // 5. Proactively update the opening Morning Briefing in coachMessages so the coach speaks first with live data!
        let briefingText = """
⚡ 【Canova × WHOOP 每日生理监测主动播报】
• 今日恢复评估：\(snap.recoveryScore)%（\(snap.recoveryZone.label)）｜HRV \(snap.hrvToday)ms（基线 \(snap.hrvBaseline)ms）｜静息心率 \(snap.rhrToday)bpm
• 今日身体负荷：Strain \(String(format: "%.1f", snap.dayStrain)) / 21.0（今日最佳负荷靶区：\(String(format: "%.1f", snap.optimalStrainLow)) - \(String(format: "%.1f", snap.optimalStrainHigh))）
• 睡眠处方建议：昨晚睡眠 \(String(format: "%.1f", snap.actualSleepHours))h（\(snap.sleepPerformancePct)%），今晚需睡 \(String(format: "%.1f", snap.neededSleepHours))h，建议在 \(snap.recommendedBedtime85) - \(snap.recommendedBedtime100) 入睡
• 体能状态指数：CTL \(String(format: "%.1f", ctl)) ｜ TSB \(String(format: "%+.1f", tsb))

💡 教练主动建议：\(snap.recoveryDetail)
"""
        if !coachMessages.isEmpty && !coachMessages[0].isUser {
            coachMessages[0] = CoachMessage(isUser: false, text: briefingText)
        } else if !hasDeliveredMorningBriefing {
            coachMessages.insert(CoachMessage(isUser: false, text: briefingText), at: 0)
            hasDeliveredMorningBriefing = true
        }
    }
}


