import Foundation
import HealthKit
import CoreLocation

// ════════════════════════════════════════════════════════════════════
// MARK: - Local-First Storage Manager
// ════════════════════════════════════════════════════════════════════

class StorageManager {
    static let shared = StorageManager()
    private let defaults = UserDefaults.standard
    
    private let tokenKey = "rgm_jwt_token"
    private let userKey = "rgm_cached_user"
    private let clientUuidKey = "rgm_client_uuid"
    private let localActivitiesKey = "rgm_local_activities"
    private let healthKitSyncedKey = "rgm_healthkit_synced_v2"
    
    var token: String? {
        get { defaults.string(forKey: tokenKey) }
        set { defaults.set(newValue, forKey: tokenKey) }
    }
    
    var clientUUID: String {
        if let uuid = defaults.string(forKey: clientUuidKey) {
            return uuid
        }
        let newUuid = "c_ios_" + UUID().uuidString.prefix(8).lowercased()
        defaults.set(newUuid, forKey: clientUuidKey)
        return newUuid
    }
    
    func saveUser(_ user: UserProfile) {
        if let data = try? JSONEncoder().encode(user) {
            defaults.set(data, forKey: userKey)
        }
    }
    
    func loadUser() -> UserProfile? {
        guard let data = defaults.data(forKey: userKey) else { return nil }
        return try? JSONDecoder().decode(UserProfile.self, from: data)
    }
    
    func saveActivities(_ activities: [ActivityItem]) {
        if let data = try? JSONEncoder().encode(activities) {
            defaults.set(data, forKey: localActivitiesKey)
        }
    }
    
    func loadActivities() -> [ActivityItem] {
        guard let data = defaults.data(forKey: localActivitiesKey) else { return [] }
        return (try? JSONDecoder().decode([ActivityItem].self, from: data)) ?? []
    }
    
    func uploadedHealthKitIds(uid: String) -> Set<String> {
        Set(defaults.stringArray(forKey: "\(healthKitSyncedKey)_\(uid)") ?? [])
    }
    
    func markHealthKitUploaded(uid: String, ids: [String]) {
        var set = uploadedHealthKitIds(uid: uid)
        set.formUnion(ids)
        defaults.set(Array(set), forKey: "\(healthKitSyncedKey)_\(uid)")
    }
    
    func clearHealthKitUploaded(uid: String) {
        defaults.removeObject(forKey: "\(healthKitSyncedKey)_\(uid)")
    }
    
    func clear() {
        defaults.removeObject(forKey: tokenKey)
        defaults.removeObject(forKey: userKey)
        defaults.removeObject(forKey: localActivitiesKey)
        defaults.removeObject(forKey: healthKitSyncedKey)
        for key in defaults.dictionaryRepresentation().keys where key.hasPrefix(healthKitSyncedKey) {
            defaults.removeObject(forKey: key)
        }
    }
}

// ════════════════════════════════════════════════════════════════════
// MARK: - Apple HealthKit Sync Manager
// Reads running workouts (heart rate, elevation, GPS route) and daily
// health metrics, and builds JSON payloads for /api/sync/healthkit.
// ════════════════════════════════════════════════════════════════════

class HealthKitManager {
    static let shared = HealthKitManager()
    private let healthStore = HKHealthStore()
    private let bpmUnit = HKUnit.count().unitDivided(by: .minute())
    private var backgroundObserversInstalled = false
    private var lastObserverTriggerAt: Date = .distantPast
    
    var isAvailable: Bool {
        HKHealthStore.isHealthDataAvailable()
    }
    
    func requestAuthorization() async -> Bool {
        guard isAvailable else { return false }
        
        var readTypes: Set<HKObjectType> = [HKObjectType.workoutType(), HKSeriesType.workoutRoute()]
        let quantityIds: [HKQuantityTypeIdentifier] = [
            .heartRate, .restingHeartRate, .heartRateVariabilitySDNN, .vo2Max,
            .activeEnergyBurned, .distanceWalkingRunning, .runningSpeed, .stepCount
        ]
        for id in quantityIds {
            if let t = HKObjectType.quantityType(forIdentifier: id) { readTypes.insert(t) }
        }
        if let sleep = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) {
            readTypes.insert(sleep)
        }
        
        do {
            try await healthStore.requestAuthorization(toShare: [], read: readTypes)
            return true
        } catch {
            print("HealthKit authorization failed: \(error)")
            return false
        }
    }
    
    /// Enables background delivery for sleep (including daytime naps), HRV, resting heart rate,
    /// all-day heart rate fluctuations, steps, and active energy so iOS automatically wakes/triggers sync
    /// both in the morning and throughout the day.
    func startBackgroundObserver(onNewMorningData: @escaping @Sendable () async -> Void) {
        guard isAvailable, !backgroundObserversInstalled else { return }
        backgroundObserversInstalled = true
        
        var sampleTypes: [HKSampleType] = []
        if let sleep = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) {
            sampleTypes.append(sleep)
        }
        let qtyIds: [HKQuantityTypeIdentifier] = [
            .heartRateVariabilitySDNN, .restingHeartRate, .heartRate, .stepCount, .activeEnergyBurned
        ]
        for qId in qtyIds {
            if let qType = HKObjectType.quantityType(forIdentifier: qId) {
                sampleTypes.append(qType)
            }
        }
        
        for sampleType in sampleTypes {
            let query = HKObserverQuery(sampleType: sampleType, predicate: nil) { [weak self] _, completionHandler, error in
                guard error == nil, let self = self else {
                    completionHandler()
                    return
                }
                let now = Date()
                // Debounce within 3 minutes to coalesce rapid HealthKit sample writes while keeping daytime data fresh
                guard now.timeIntervalSince(self.lastObserverTriggerAt) > 180 else {
                    completionHandler()
                    return
                }
                self.lastObserverTriggerAt = now
                Task {
                    await onNewMorningData()
                    completionHandler()
                }
            }
            healthStore.execute(query)
            healthStore.enableBackgroundDelivery(for: sampleType, frequency: .immediate) { _, _ in }
        }
    }
    
    // MARK: Workouts
    
    func fetchRunningWorkouts(since: Date, limit: Int = 400) async -> [HKWorkout] {
        guard isAvailable else { return [] }
        let predicate = NSCompoundPredicate(andPredicateWithSubpredicates: [
            HKQuery.predicateForWorkouts(with: .running),
            HKQuery.predicateForSamples(withStart: since, end: Date(), options: [])
        ])
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)
        return await withCheckedContinuation { continuation in
            let query = HKSampleQuery(sampleType: .workoutType(), predicate: predicate, limit: limit, sortDescriptors: [sort]) { _, samples, _ in
                continuation.resume(returning: (samples as? [HKWorkout]) ?? [])
            }
            healthStore.execute(query)
        }
    }
    
    /// Builds the upload payload for one workout, including heart rate stats, cadence, source device, and a downsampled GPS route.
    func buildWorkoutPayload(_ w: HKWorkout, includeRoute: Bool = true) async -> [String: Any] {
        let devName = [w.device?.manufacturer, w.device?.name, w.device?.model]
            .compactMap { $0 }
            .joined(separator: " ")
        var dict: [String: Any] = [
            "uuid": w.uuid.uuidString,
            "start_time": ISO8601DateFormatter().string(from: w.startDate),
            "duration_seconds": Int(w.duration),
            "source_name": w.sourceRevision.source.name,
            "device_name": devName,
            "bundle_id": w.sourceRevision.source.bundleIdentifier
        ]
        
        var distance = w.totalDistance?.doubleValue(for: .meter()) ?? 0
        if distance <= 0, let dt = HKQuantityType.quantityType(forIdentifier: .distanceWalkingRunning),
           let sum = w.statistics(for: dt)?.sumQuantity() {
            distance = sum.doubleValue(for: .meter())
        }
        dict["distance_meters"] = distance
        
        if let hrType = HKQuantityType.quantityType(forIdentifier: .heartRate), let stats = w.statistics(for: hrType) {
            if let avg = stats.averageQuantity()?.doubleValue(for: bpmUnit) { dict["average_heartrate"] = Int(avg.rounded()) }
            if let mx = stats.maximumQuantity()?.doubleValue(for: bpmUnit) { dict["max_heartrate"] = Int(mx.rounded()) }
        }
        // Third-party apps (e.g. Huawei Health / Garmin Connect) often write HR samples that are not
        // associated with the workout object, so fall back to samples in the workout window.
        var hrSamples: [(Date, Int)]? = nil
        if dict["average_heartrate"] == nil {
            let samples = await fetchHeartRateSamples(start: w.startDate, end: w.endDate)
            hrSamples = samples
            if !samples.isEmpty {
                let values = samples.map { $0.1 }
                dict["average_heartrate"] = Int((Double(values.reduce(0, +)) / Double(values.count)).rounded())
                dict["max_heartrate"] = values.max()
            }
        }
        // Compute average cadence (steps/min) from stepCount during workout window
        if w.duration >= 60 {
            var totalSteps: Double = 0
            if let stepType = HKQuantityType.quantityType(forIdentifier: .stepCount),
               let sum = w.statistics(for: stepType)?.sumQuantity()?.doubleValue(for: .count()) {
                totalSteps = sum
            }
            if totalSteps <= 0 {
                totalSteps = await fetchStepCountSum(start: w.startDate, end: w.endDate)
            }
            let spm = totalSteps / (w.duration / 60.0)
            if spm >= 100 && spm <= 240 {
                dict["average_cadence"] = (spm * 10).rounded() / 10
            }
        }
        if let energyType = HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned),
           let kcal = w.statistics(for: energyType)?.sumQuantity()?.doubleValue(for: .kilocalorie()) {
            dict["calories"] = Int(kcal.rounded())
        }
        if let elev = w.metadata?[HKMetadataKeyElevationAscended] as? HKQuantity {
            dict["elevation_gain_meters"] = elev.doubleValue(for: .meter())
        }
        let indoor = (w.metadata?[HKMetadataKeyIndoorWorkout] as? Bool) ?? false
        dict["is_indoor"] = indoor
        
        if includeRoute && !indoor {
            let locations = await fetchRouteLocations(for: w)
            if locations.count >= 2 {
                let sampled = downsample(locations, maxPoints: 600)
                let routeHr: [(Date, Int)]
                if let cached = hrSamples {
                    routeHr = cached
                } else {
                    routeHr = await fetchHeartRateSamples(start: w.startDate, end: w.endDate)
                }
                var hrIdx = 0
                var route: [[String: Any]] = []
                route.reserveCapacity(sampled.count)
                for loc in sampled {
                    var p: [String: Any] = [
                        "lat": loc.coordinate.latitude,
                        "lon": loc.coordinate.longitude,
                        "alt": loc.altitude
                    ]
                    // Two-pointer nearest-in-time heart rate match
                    if !routeHr.isEmpty {
                        while hrIdx + 1 < routeHr.count &&
                              abs(routeHr[hrIdx + 1].0.timeIntervalSince(loc.timestamp)) <= abs(routeHr[hrIdx].0.timeIntervalSince(loc.timestamp)) {
                            hrIdx += 1
                        }
                        if abs(routeHr[hrIdx].0.timeIntervalSince(loc.timestamp)) < 30 {
                            p["hr"] = routeHr[hrIdx].1
                        }
                    }
                    route.append(p)
                }
                dict["route"] = route
            }
        }
        return dict
    }
    
    private func fetchRouteLocations(for workout: HKWorkout) async -> [CLLocation] {
        let routes: [HKWorkoutRoute] = await withCheckedContinuation { continuation in
            let q = HKSampleQuery(sampleType: HKSeriesType.workoutRoute(),
                                  predicate: HKQuery.predicateForObjects(from: workout),
                                  limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, _ in
                continuation.resume(returning: (samples as? [HKWorkoutRoute]) ?? [])
            }
            healthStore.execute(q)
        }
        var all: [CLLocation] = []
        for route in routes {
            let locs: [CLLocation] = await withCheckedContinuation { continuation in
                var buffer: [CLLocation] = []
                var resumed = false
                let q = HKWorkoutRouteQuery(route: route) { _, locations, done, error in
                    if let locations = locations { buffer.append(contentsOf: locations) }
                    if (done || error != nil) && !resumed {
                        resumed = true
                        continuation.resume(returning: buffer)
                    }
                }
                healthStore.execute(q)
            }
            all.append(contentsOf: locs)
        }
        return all.sorted { $0.timestamp < $1.timestamp }
    }
    
    private func fetchHeartRateSamples(start: Date, end: Date) async -> [(Date, Int)] {
        guard let hrType = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return [] }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: [])
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        return await withCheckedContinuation { continuation in
            let q = HKSampleQuery(sampleType: hrType, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { _, samples, _ in
                let unit = HKUnit.count().unitDivided(by: .minute())
                let result = ((samples as? [HKQuantitySample]) ?? []).map {
                    ($0.startDate, Int($0.quantity.doubleValue(for: unit).rounded()))
                }
                continuation.resume(returning: result)
            }
            healthStore.execute(q)
        }
    }
    
    private func fetchStepCountSum(start: Date, end: Date) async -> Double {
        guard let stepType = HKQuantityType.quantityType(forIdentifier: .stepCount) else { return 0 }
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: .strictStartDate)
        return await withCheckedContinuation { continuation in
            let q = HKStatisticsQuery(quantityType: stepType, quantitySamplePredicate: predicate, options: .cumulativeSum) { _, stats, _ in
                let sum = stats?.sumQuantity()?.doubleValue(for: .count()) ?? 0
                continuation.resume(returning: sum)
            }
            healthStore.execute(q)
        }
    }
    
    private func downsample(_ points: [CLLocation], maxPoints: Int) -> [CLLocation] {
        guard points.count > maxPoints, maxPoints > 1 else { return points }
        let step = Double(points.count - 1) / Double(maxPoints - 1)
        return (0..<maxPoints).map { points[min(points.count - 1, Int((Double($0) * step).rounded()))] }
    }
    
    // MARK: Daily health metrics (resting HR, HRV, sleep, daytime naps, steps, active calories, HR min/max, stress, VO2max)
    
    func fetchDailyHealth(days: Int = 30) async -> [[String: Any]] {
        let rhr = await dailyAverage(.restingHeartRate, unit: bpmUnit, days: days)
        let hrv = await dailyAverage(.heartRateVariabilitySDNN, unit: .secondUnit(with: .milli), days: days)
        let vo2Unit = HKUnit.literUnit(with: .milli).unitDivided(by: HKUnit.gramUnit(with: .kilo).unitMultiplied(by: .minute()))
        let vo2 = await dailyAverage(.vo2Max, unit: vo2Unit, days: days)
        let (sleep, naps) = await dailySleepAndNapSeconds(days: days)
        let steps = await dailyCumulativeSum(.stepCount, unit: .count(), days: days)
        let activeKcal = await dailyCumulativeSum(.activeEnergyBurned, unit: .kilocalorie(), days: days)
        let (hrMinMap, hrMaxMap, hrAvgMap) = await dailyHeartRateMinMaxAvg(days: days)
        
        let avgHrvBaseline = hrv.values.isEmpty ? 58.0 : (hrv.values.reduce(0, +) / Double(hrv.values.count))
        let avgRhrBaseline = rhr.values.isEmpty ? 54.0 : (rhr.values.reduce(0, +) / Double(rhr.values.count))
        
        let keys = Set(rhr.keys)
            .union(hrv.keys)
            .union(vo2.keys)
            .union(sleep.keys)
            .union(naps.keys)
            .union(steps.keys)
            .union(activeKcal.keys)
            .union(hrMaxMap.keys)
        return keys.sorted().map { day in
            var d: [String: Any] = ["date": day]
            if let v = rhr[day] { d["resting_heart_rate"] = Int(v.rounded()) }
            if let v = hrv[day] { d["hrv_ms"] = (v * 10).rounded() / 10 }
            if let v = vo2[day] { d["vo2_max"] = (v * 10).rounded() / 10 }
            if let v = sleep[day] { d["sleep_duration_seconds"] = v }
            if let n = naps[day], n > 0 { d["nap_duration_seconds"] = n }
            if let s = steps[day], s > 0 { d["steps"] = Int(s.rounded()) }
            if let k = activeKcal[day], k > 0 { d["active_calories"] = Int(k.rounded()) }
            if let mn = hrMinMap[day], mn > 0 { d["hr_min"] = Int(mn.rounded()) }
            if let mx = hrMaxMap[day], mx > 0 { d["hr_max"] = Int(mx.rounded()) }
            
            // Derive autonomic stress (0-100) when HRV or all-day HR fluctuation is available
            let dayRhr = rhr[day] ?? avgRhrBaseline
            let dayHrv = hrv[day] ?? avgHrvBaseline
            let dayAvgHr = hrAvgMap[day] ?? (dayRhr + 16.0)
            if hrv[day] != nil || hrAvgMap[day] != nil {
                let hrvStress = max(-18.0, min(28.0, (avgHrvBaseline - dayHrv) * 0.75))
                let hrElevStress = max(-10.0, min(25.0, (dayAvgHr - (dayRhr + 15.0)) * 1.1))
                let estStress = Int(min(92.0, max(15.0, 34.0 + hrvStress + hrElevStress)).rounded())
                d["stress_avg"] = estStress
                if let mx = hrMaxMap[day] {
                    let maxStress = Int(min(98.0, max(Double(estStress), Double(estStress) + (mx - dayAvgHr) * 0.45)).rounded())
                    d["stress_max"] = maxStress
                }
            }
            return d
        }
    }
    
    private static let dayFormatter: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
    
    private func dailyAverage(_ id: HKQuantityTypeIdentifier, unit: HKUnit, days: Int) async -> [String: Double] {
        guard let type = HKQuantityType.quantityType(forIdentifier: id) else { return [:] }
        let cal = Calendar.current
        let end = Date()
        let start = cal.startOfDay(for: cal.date(byAdding: .day, value: -days, to: end) ?? end)
        return await withCheckedContinuation { continuation in
            let q = HKStatisticsCollectionQuery(
                quantityType: type,
                quantitySamplePredicate: HKQuery.predicateForSamples(withStart: start, end: end, options: []),
                options: .discreteAverage,
                anchorDate: start,
                intervalComponents: DateComponents(day: 1)
            )
            q.initialResultsHandler = { _, results, _ in
                var out: [String: Double] = [:]
                results?.enumerateStatistics(from: start, to: end) { stats, _ in
                    if let v = stats.averageQuantity()?.doubleValue(for: unit) {
                        out[HealthKitManager.dayFormatter.string(from: stats.startDate)] = v
                    }
                }
                continuation.resume(returning: out)
            }
            healthStore.execute(q)
        }
    }
    
    private func dailyCumulativeSum(_ id: HKQuantityTypeIdentifier, unit: HKUnit, days: Int) async -> [String: Double] {
        guard let type = HKQuantityType.quantityType(forIdentifier: id) else { return [:] }
        let cal = Calendar.current
        let end = Date()
        let start = cal.startOfDay(for: cal.date(byAdding: .day, value: -days, to: end) ?? end)
        return await withCheckedContinuation { continuation in
            let q = HKStatisticsCollectionQuery(
                quantityType: type,
                quantitySamplePredicate: HKQuery.predicateForSamples(withStart: start, end: end, options: []),
                options: .cumulativeSum,
                anchorDate: start,
                intervalComponents: DateComponents(day: 1)
            )
            q.initialResultsHandler = { _, results, _ in
                var out: [String: Double] = [:]
                results?.enumerateStatistics(from: start, to: end) { stats, _ in
                    if let v = stats.sumQuantity()?.doubleValue(for: unit), v > 0 {
                        out[HealthKitManager.dayFormatter.string(from: stats.startDate)] = v
                    }
                }
                continuation.resume(returning: out)
            }
            healthStore.execute(q)
        }
    }
    
    private func dailyHeartRateMinMaxAvg(days: Int) async -> ([String: Double], [String: Double], [String: Double]) {
        guard let type = HKQuantityType.quantityType(forIdentifier: .heartRate) else { return ([:], [:], [:]) }
        let cal = Calendar.current
        let end = Date()
        let start = cal.startOfDay(for: cal.date(byAdding: .day, value: -days, to: end) ?? end)
        let unit = bpmUnit
        return await withCheckedContinuation { continuation in
            let q = HKStatisticsCollectionQuery(
                quantityType: type,
                quantitySamplePredicate: HKQuery.predicateForSamples(withStart: start, end: end, options: []),
                options: [.discreteMin, .discreteMax, .discreteAverage],
                anchorDate: start,
                intervalComponents: DateComponents(day: 1)
            )
            q.initialResultsHandler = { _, results, _ in
                var minOut: [String: Double] = [:]
                var maxOut: [String: Double] = [:]
                var avgOut: [String: Double] = [:]
                results?.enumerateStatistics(from: start, to: end) { stats, _ in
                    let dayKey = HealthKitManager.dayFormatter.string(from: stats.startDate)
                    if let mn = stats.minimumQuantity()?.doubleValue(for: unit), mn > 0 {
                        minOut[dayKey] = mn
                    }
                    if let mx = stats.maximumQuantity()?.doubleValue(for: unit), mx > 0 {
                        maxOut[dayKey] = mx
                    }
                    if let av = stats.averageQuantity()?.doubleValue(for: unit), av > 0 {
                        avgOut[dayKey] = av
                    }
                }
                continuation.resume(returning: (minOut, maxOut, avgOut))
            }
            healthStore.execute(q)
        }
    }
    
    /// Separates overnight asleep seconds and daytime nap seconds per day.
    /// Daytime naps are contiguous sleep blocks that start between 10:30 and 18:30 local time
    /// and last between 10 minutes and 3.5 hours.
    private func dailySleepAndNapSeconds(days: Int) async -> ([String: Int], [String: Int]) {
        guard let type = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return ([:], [:]) }
        let end = Date()
        let start = Calendar.current.date(byAdding: .day, value: -(days + 1), to: end) ?? end
        let samples: [HKCategorySample] = await withCheckedContinuation { continuation in
            let q = HKSampleQuery(sampleType: type,
                                  predicate: HKQuery.predicateForSamples(withStart: start, end: end, options: []),
                                  limit: HKObjectQueryNoLimit,
                                  sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)]) { _, s, _ in
                continuation.resume(returning: (s as? [HKCategorySample]) ?? [])
            }
            healthStore.execute(q)
        }
        let asleepValues: Set<Int> = [
            HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue,
            HKCategoryValueSleepAnalysis.asleepCore.rawValue,
            HKCategoryValueSleepAnalysis.asleepDeep.rawValue,
            HKCategoryValueSleepAnalysis.asleepREM.rawValue
        ]
        var byDay: [String: [(Date, Date)]] = [:]
        for s in samples where asleepValues.contains(s.value) {
            byDay[HealthKitManager.dayFormatter.string(from: s.endDate), default: []].append((s.startDate, s.endDate))
        }
        let cal = Calendar.current
        var nightOut: [String: Int] = [:]
        var napOut: [String: Int] = [:]
        for (day, intervals) in byDay {
            let sorted = intervals.sorted { $0.0 < $1.0 }
            // Merge overlapping or closely adjacent (<15 min gap) sleep intervals into sessions
            var sessions: [(Date, Date)] = []
            var cur = sorted[0]
            for iv in sorted.dropFirst() {
                if iv.0.timeIntervalSince(cur.1) <= 900 {
                    cur.1 = max(cur.1, iv.1)
                } else {
                    sessions.append(cur)
                    cur = iv
                }
            }
            sessions.append(cur)
            
            var nightTotal: TimeInterval = 0
            var napTotal: TimeInterval = 0
            for sess in sessions {
                let dur = sess.1.timeIntervalSince(sess.0)
                let startHour = cal.component(.hour, from: sess.0)
                let startMin = cal.component(.minute, from: sess.0)
                let startMinsOfDay = startHour * 60 + startMin
                // Daytime nap window: starts between 10:30 (630m) and 18:30 (1110m) and lasts 10m .. 210m
                if startMinsOfDay >= 630 && startMinsOfDay <= 1110 && dur >= 600 && dur <= 12600 {
                    napTotal += dur
                } else {
                    nightTotal += dur
                }
            }
            if nightTotal > 0 { nightOut[day] = Int(nightTotal) }
            if napTotal > 0 { napOut[day] = Int(napTotal) }
        }
        return (nightOut, napOut)
    }
}
