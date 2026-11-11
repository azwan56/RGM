import Foundation
import UserNotifications
import UIKit
import BackgroundTasks

// ════════════════════════════════════════════════════════════════════
// MARK: - Morning Briefing (opt-in local push + pre-push watch auto-sync)
// Users choose whether to receive a morning recovery notification and at what time.
// Before the push fires each morning:
// 1. A BGAppRefreshTask ("com.zhongwan.rgmapp.morning_sync") is scheduled ~20 min
//    prior to the user's push time to proactively pull Garmin/COROS/Apple Watch data
//    and rewrite today's pending notification with live Recovery/HRV/RHR numbers.
// 2. HealthKit background delivery also triggers pre-push sync as soon as morning
//    sleep/HRV samples land on iPhone.
// ════════════════════════════════════════════════════════════════════

@MainActor
final class MorningBriefingManager: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    static let shared = MorningBriefingManager()
    static let bgTaskIdentifier = "com.zhongwan.rgmapp.morning_sync"
    
    @Published private(set) var isEnabled: Bool = false
    @Published private(set) var hour: Int = 7
    @Published private(set) var minute: Int = 0
    @Published private(set) var authStatus: UNAuthorizationStatus = .notDetermined
    
    /// Invoked when the user taps a morning briefing notification.
    var onOpenRecovery: (() -> Void)?
    
    /// Invoked in the background prior to the morning push (or upon notification tap)
    /// to proactively pull the latest watch data and refresh recovery metrics.
    var onPrePushSync: (() async -> Void)?
    
    private var uid: String = ""
    private let center = UNUserNotificationCenter.current()
    private static let idPrefix = "rgm_morning_briefing_"
    private let daysAhead = 14
    private var bgTaskRegistered = false
    
    // Last known content so time changes can reschedule without waiting for the next sync.
    private var lastSnapshot: WhoopSnapshot?
    private var lastHasTodayData: Bool = false
    private var upcomingWorkouts: [String: String] = [:]
    
    private static let dayKeyFormatter: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "Asia/Shanghai") ?? .current
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
    
    private override init() {
        super.init()
    }
    
    var timeText: String { String(format: "%02d:%02d", hour, minute) }
    
    // MARK: Setup & Background Task Registration
    
    func installDelegate() {
        center.delegate = self
        registerBackgroundRefreshTaskIfNeeded()
    }
    
    private func registerBackgroundRefreshTaskIfNeeded() {
        guard !bgTaskRegistered else { return }
        bgTaskRegistered = true
        BGTaskScheduler.shared.register(forTaskWithIdentifier: Self.bgTaskIdentifier, using: nil) { task in
            guard let refreshTask = task as? BGAppRefreshTask else {
                task.setTaskCompleted(success: false)
                return
            }
            Task { @MainActor in
                MorningBriefingManager.shared.scheduleBackgroundPrePushSync()
                let workTask = Task { @MainActor in
                    await MorningBriefingManager.shared.onPrePushSync?()
                }
                refreshTask.expirationHandler = {
                    workTask.cancel()
                }
                _ = await workTask.result
                refreshTask.setTaskCompleted(success: !workTask.isCancelled)
            }
        }
    }
    
    /// Schedules an iOS BGAppRefreshTask ~20 minutes before the next morning notification
    /// so the app can proactively fetch Garmin/COROS/Apple Watch data before the push banner fires.
    func scheduleBackgroundPrePushSync() {
        guard isEnabled else {
            BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: Self.bgTaskIdentifier)
            return
        }
        let cal = Calendar.current
        let now = Date()
        var comps = cal.dateComponents([.year, .month, .day], from: now)
        comps.hour = hour
        comps.minute = minute
        var nextPush = cal.date(from: comps) ?? now
        if nextPush <= now {
            nextPush = cal.date(byAdding: .day, value: 1, to: nextPush) ?? now.addingTimeInterval(3600 * 12)
        }
        // Wake 20 minutes before the notification (but at least 5 minutes from now)
        let preSyncDate = max(now.addingTimeInterval(5 * 60), nextPush.addingTimeInterval(-20 * 60))
        let req = BGAppRefreshTaskRequest(identifier: Self.bgTaskIdentifier)
        req.earliestBeginDate = preSyncDate
        try? BGTaskScheduler.shared.submit(req)
    }
    
    func configure(uid: String) {
        guard !uid.isEmpty, uid != self.uid else { return }
        self.uid = uid
        let d = UserDefaults.standard
        isEnabled = d.bool(forKey: key("enabled"))
        if d.object(forKey: key("h")) != nil {
            hour = d.integer(forKey: key("h"))
            minute = d.integer(forKey: key("m"))
        } else {
            hour = 7
            minute = 0
        }
        Task { await refreshAuthStatus() }
    }
    
    func refreshAuthStatus() async {
        let settings = await center.notificationSettings()
        authStatus = settings.authorizationStatus
        // If the user revoked permission in iOS Settings, reflect it as disabled.
        if isEnabled && (authStatus == .denied) {
            isEnabled = false
            persist()
            cancelAll()
        }
    }
    
    // MARK: User actions
    
    /// Returns an error message when the toggle could not be turned on.
    @discardableResult
    func setEnabled(_ on: Bool) async -> String? {
        if !on {
            isEnabled = false
            persist()
            cancelAll()
            BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: Self.bgTaskIdentifier)
            return nil
        }
        let settings = await center.notificationSettings()
        var status = settings.authorizationStatus
        if status == .notDetermined {
            let granted = (try? await center.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
            status = granted ? .authorized : .denied
        }
        authStatus = status
        guard status == .authorized || status == .provisional || status == .ephemeral else {
            isEnabled = false
            persist()
            return "通知权限未开启，请在 iPhone「设置 - 通知 - RGM」中允许通知"
        }
        isEnabled = true
        persist()
        // Proactively pull latest watch data right away when enabling morning push
        await onPrePushSync?()
        reschedule()
        return nil
    }
    
    func setTime(hour: Int, minute: Int) {
        self.hour = max(0, min(23, hour))
        self.minute = max(0, min(59, minute))
        persist()
        reschedule()
    }
    
    /// Proactively syncs watch data first, then fires a sample notification so users see real watch metrics.
    func sendTestNotification() {
        Task { @MainActor in
            await self.onPrePushSync?()
            let todayKey = Self.dayKeyFormatter.string(from: Date())
            let content = self.buildContent(forDateKey: todayKey, isToday: true, forceReal: self.lastSnapshot != nil)
            content.title = "【预览】" + content.title
            let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 2, repeats: false)
            try? await self.center.add(UNNotificationRequest(identifier: Self.idPrefix + "test", content: content, trigger: trigger))
        }
    }
    
    // MARK: Scheduling
    
    func update(snapshot: WhoopSnapshot, hasTodayData: Bool, upcomingWorkouts: [String: String] = [:]) {
        lastSnapshot = snapshot
        lastHasTodayData = hasTodayData
        if !upcomingWorkouts.isEmpty {
            self.upcomingWorkouts = upcomingWorkouts
        }
        reschedule()
    }
    
    func cancelAll() {
        let ids = (0..<daysAhead).map { Self.idPrefix + "\($0)" } + [Self.idPrefix + "test"]
        center.removePendingNotificationRequests(withIdentifiers: ids)
    }
    
    private func reschedule() {
        cancelAll()
        guard isEnabled else { return }
        scheduleBackgroundPrePushSync()
        let cal = Calendar.current
        let now = Date()
        for offset in 0..<daysAhead {
            guard let day = cal.date(byAdding: .day, value: offset, to: now) else { continue }
            var comps = cal.dateComponents([.year, .month, .day], from: day)
            comps.hour = hour
            comps.minute = minute
            guard let fireDate = cal.date(from: comps), fireDate > now else { continue }
            let dateKey = Self.dayKeyFormatter.string(from: day)
            let content = buildContent(forDateKey: dateKey, isToday: offset == 0, forceReal: false)
            let trigger = UNCalendarNotificationTrigger(dateMatching: comps, repeats: false)
            center.add(UNNotificationRequest(identifier: Self.idPrefix + "\(offset)", content: content, trigger: trigger))
        }
    }
    
    private func buildContent(forDateKey dateKey: String, isToday: Bool, forceReal: Bool) -> UNMutableNotificationContent {
        let content = UNMutableNotificationContent()
        content.sound = .default
        content.threadIdentifier = "rgm_morning_briefing"
        let workoutLine = upcomingWorkouts[dateKey]
        
        if let s = lastSnapshot, (isToday && lastHasTodayData) || forceReal {
            let zone: String
            switch s.recoveryZone {
            case .green: zone = "🟢 绿灯"
            case .yellow: zone = "🟡 黄灯"
            case .red: zone = "🔴 红灯"
            }
            content.title = "早安 · 今日恢复 \(s.recoveryScore)% \(zone)"
            if let wl = workoutLine, !wl.isEmpty {
                content.body = "HRV \(s.hrvToday)ms · 静息心率 \(s.rhrToday)bpm · 目标负荷 \(String(format: "%.1f", s.optimalStrainLow))–\(String(format: "%.1f", s.optimalStrainHigh))\n今日课表：\(wl)"
            } else {
                content.body = "HRV \(s.hrvToday)ms · 静息心率 \(s.rhrToday)bpm · 今日目标负荷 \(String(format: "%.1f", s.optimalStrainLow))–\(String(format: "%.1f", s.optimalStrainHigh))\n\(s.recoveryHeadline)"
            }
        } else if let s = lastSnapshot, s.missingInputs.isEmpty {
            // If pre-push background refresh was deferred by iOS battery heuristics, show latest baseline + today's scheduled workout
            let zone: String
            switch s.recoveryZone {
            case .green: zone = "🟢"
            case .yellow: zone = "🟡"
            case .red: zone = "🔴"
            }
            content.title = "早安 ☀️ 今日身体状态 \(zone) \(s.recoveryScore)%"
            if let wl = workoutLine, !wl.isEmpty {
                content.body = "今日课表：\(wl)\nHRV \(s.hrvToday)ms · 静息心率 \(s.rhrToday)bpm · 点按自动同步晨间最新手表数据"
            } else {
                content.body = "HRV \(s.hrvToday)ms · 静息心率 \(s.rhrToday)bpm · 目标负荷 \(String(format: "%.1f", s.optimalStrainLow))–\(String(format: "%.1f", s.optimalStrainHigh)) · 点按自动同步最新手表数据"
            }
        } else {
            content.title = "早安 ☀️ 今日身体状态与训练建议"
            if let wl = workoutLine, !wl.isEmpty {
                content.body = "今日课表：\(wl)\n点按自动同步手表数据，查看今日恢复度与目标负荷"
            } else {
                content.body = "点按自动同步手表数据，查看今日恢复度、目标负荷与 Canova 教练训练建议"
            }
        }
        return content
    }
    
    private func key(_ suffix: String) -> String { "rgm_morning_push_\(suffix)_\(uid)" }
    
    private func persist() {
        guard !uid.isEmpty else { return }
        let d = UserDefaults.standard
        d.set(isEnabled, forKey: key("enabled"))
        d.set(hour, forKey: key("h"))
        d.set(minute, forKey: key("m"))
    }
    
    // MARK: UNUserNotificationCenterDelegate
    
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            willPresent notification: UNNotification,
                                            withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }
    
    nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                            didReceive response: UNNotificationResponse,
                                            withCompletionHandler completionHandler: @escaping () -> Void) {
        if response.notification.request.identifier.hasPrefix("rgm_morning_briefing_") {
            Task { @MainActor in
                MorningBriefingManager.shared.onOpenRecovery?()
                await MorningBriefingManager.shared.onPrePushSync?()
            }
        }
        completionHandler()
    }
}
