import Foundation

// MARK: - User & Auth Models

struct UserProfile: Codable, Identifiable {
    var id: String
    var display_name: String?
    var avatar_url: String?
    var phone: String?
    var garmin_connected: Bool?
    var garmin_email: String?
    var garmin_domain: String?
    var garmin_last_sync_at: String?
    var coros_connected: Bool?
    var coros_account: String?
    var coros_domain: String?
    var coros_last_sync_at: String?
    var apple_watch_connected: Bool?
    var huawei_connected: Bool?
    var huawei_account: String?
    var max_heart_rate: Int?
    var resting_heart_rate: Int?
    var vo2max: Double?
    var marathon_pb: Int?
    
    var displayName: String {
        display_name ?? "跑者"
    }
    
    var isGarminConnected: Bool {
        garmin_connected == true
    }
    
    var isCorosConnected: Bool {
        coros_connected == true
    }
    
    var isAppleWatchConnected: Bool {
        apple_watch_connected == true
    }
    
    var deviceRegionText: String {
        if isGarminConnected {
            return garmin_domain == "garmin.com" ? "佳明直连 · 国际区" : "佳明直连 · 中国区"
        } else if isCorosConnected {
            return "高驰直连"
        } else if isAppleWatchConnected {
            return "Apple Watch 直连"
        }
        return "未连接手表"
    }
    
    var marathonPBString: String {
        guard let sec = marathon_pb, sec > 0 else { return "--:--" }
        let h = sec / 3600
        let m = (sec % 3600) / 60
        let s = sec % 60
        return String(format: "%d:%02d:%02d", h, m, s)
    }
}

struct AuthResponse: Codable {
    let token: String?
    let uid: String?
    let display_name: String?
    let avatar_url: String?
    let garmin_connected: Bool?
    let garmin_email: String?
    let garmin_domain: String?
    let coros_connected: Bool?
    let coros_account: String?
    let coros_domain: String?
    let apple_watch_connected: Bool?
    let huawei_connected: Bool?
    let huawei_account: String?
    let needs_mfa: Bool?
    let needs_2fa: Bool?
    let message: String?
    let email: String?
    let account: String?
    let domain: String?
}

// MARK: - Activity Models

struct ActivityItem: Codable, Identifiable {
    let id: String
    let name: String
    let sport_type: String?
    let distance_meters: Double?
    let distance_km: Double?
    let moving_time_seconds: Int?
    let avg_pace_str: String?
    let average_heartrate: Int?
    let start_time: String?
    let elevation_gain_meters: Double?
    let trimp: Double?
    let ai_journal: String?
    let has_gps_track: Bool?
    let map_image_url: String?
    
    var distanceKm: Double {
        if let km = distance_km, km > 0 { return km }
        if let m = distance_meters, m > 0 { return m / 1000.0 }
        return 0.0
    }
    
    var durationString: String {
        guard let sec = moving_time_seconds, sec > 0 else { return "00:00" }
        let h = sec / 3600
        let m = (sec % 3600) / 60
        let s = sec % 60
        if h > 0 {
            return String(format: "%d:%02d:%02d", h, m, s)
        } else {
            return String(format: "%02d:%02d", m, s)
        }
    }
}

// MARK: - Weekly & Daily Breakdown Models

struct DayBreakdownItem: Codable, Identifiable {
    var id: String { full_date ?? date ?? UUID().uuidString }
    let date: String?
    let full_date: String?
    let day_name: String?
    let short_day: String?
    let distance_km: Double
    let is_today: Bool
    let is_past: Bool
}

struct WeeklyProgressData: Codable {
    let week_number: Int?
    let week_label: String?
    let week_start: String?
    let week_end: String?
    let current_week_km: Double?
    let target_week_km: Double?
    let progress_pct: Double?
    let remaining_km: Double?
    let daily_required_km: Double?
    let daily_breakdown: [DayBreakdownItem]?
}

// MARK: - Today's Workout Model

struct TodayWorkoutData: Codable, Identifiable {
    var id: String { "\(date ?? "")_\(title ?? UUID().uuidString)" }
    let date: String?
    let day_of_week: String?
    let title: String?
    let workout_type: String?
    let distance_km: Double?
    let target_pace: String?
    let target_hr_zone: String?
    let description: String?
    let coach_notes: String?
    let completed: Bool?
    let actual_distance_km: Double?
}

// MARK: - Yearly Stats & Monthly Breakdown Models

struct MonthBreakdownItem: Codable, Identifiable {
    var id: Int { month }
    let month: Int
    let month_label: String?
    let distance_km: Double
    let runs_count: Int
    let is_current: Bool
    let is_past: Bool
}

struct BestMonthData: Codable {
    let name: String?
    let distance_km: Double?
    let avg_pace: String?
}

struct YearlyStatsData: Codable {
    let year: Int?
    let total_km: Double?
    let total_runs: Int?
    let avg_monthly_km: Double?
    let projected_year_km: Double?
    let target_year_km: Double?
    let monthly_target_km: Double?
    let progress_pct: Double?
    let best_month: BestMonthData?
    let monthly_breakdown: [MonthBreakdownItem]?
}

// MARK: - Dashboard API Response Models

struct ProgressData: Codable {
    let current_month_km: Double?
    let target_month_km: Double?
    let progress_pct: Double?
    let remaining_km: Double?
    let days_left_in_month: Int?
    let daily_required_km: Double?
}

struct FitnessHistoryItem: Codable {
    let date: String?
    let short_date: String?
    let ctl: Double?
    let atl: Double?
    let tsb: Double?
    let tsb_color: String?
    let tsb_label: String?
    let trimp: Double?
}

struct FitnessFormData: Codable {
    let ctl: Double?
    let atl: Double?
    let tsb: Double?
    let status_label: String?
    let status_color: String?
    let history: [FitnessHistoryItem]?
}

struct TodayHealthData: Codable {
    let date: String?
    let device_brand: String?
    let sleep_score: Int?
    let sleep_duration_hours: Double?
    let sleep_duration_seconds: Int?
    let sleep_duration_text: String?
    let resting_heart_rate: Int?
    let body_battery_max: Int?
    let body_battery_min: Int?
    let body_battery_current: Int?
    let hrv_ms: Int?
    let hrv_weekly_avg: Int?
    let hrv_status: String?
    let vo2_max: Double?
    let steps: Int?
    let active_calories: Int?
    let nap_duration_seconds: Int?
    let nap_duration_minutes: Int?
    let stress_avg: Int?
    let stress_max: Int?
    let hr_min: Int?
    let hr_max: Int?
    let updated_at: String?
}

struct DashboardResponse: Codable {
    let user: UserProfile?
    let fitness_form: FitnessFormData?
    let progress: ProgressData?
    let weekly_progress: WeeklyProgressData?
    let today_workout: TodayWorkoutData?
    let yearly_stats: YearlyStatsData?
    let recent_activities: [ActivityItem]?
    let current_month_activities: [ActivityItem]?
    let today_health: TodayHealthData?
    let ai_coach_tip: String?
}

// MARK: - Science Metrics & Health Trend

struct RacePredictions: Codable {
    let five_k: String?
    let ten_k: String?
    let half_marathon: String?
    let marathon: String?
}

struct CanovaZoneItem: Codable {
    let name: String?
    let range: String?
    let desc: String?
}

struct TsbBadge: Codable {
    let category: String?
    let label: String?
    let color: String?
    
    init(category: String? = nil, label: String? = nil, color: String? = nil) {
        self.category = category
        self.label = label
        self.color = color
    }
    
    init(from decoder: Decoder) throws {
        if let container = try? decoder.singleValueContainer(), let str = try? container.decode(String.self) {
            self.category = nil
            self.label = str
            self.color = nil
            return
        }
        let dict = try decoder.container(keyedBy: CodingKeys.self)
        self.category = try? dict.decode(String.self, forKey: .category)
        self.label = try? dict.decode(String.self, forKey: .label)
        self.color = try? dict.decode(String.self, forKey: .color)
    }
    
    enum CodingKeys: String, CodingKey {
        case category, label, color
    }
}

struct CtlAtlTsbPoint: Codable, Identifiable {
    var id: String { date ?? UUID().uuidString }
    let date: String?
    let short_date: String?
    let ctl: Double?
    let atl: Double?
    let tsb: Double?
    let tsb_category: String?
    let tsb_label: String?
    let tsb_color: String?
    let trimp: Double?
}

struct ScienceMetricsResponse: Codable {
    let current_ctl: Double?
    let current_atl: Double?
    let current_tsb: Double?
    let current_tsb_badge: TsbBadge?
    let vdot: Double?
    let race_predictions: RacePredictions?
    let canova_zones: [String: CanovaZoneItem]?
    let ctl_atl_tsb_history: [CtlAtlTsbPoint]?
}

struct HealthTrendPoint: Codable, Identifiable {
    var id: String { date ?? UUID().uuidString }
    let date: String?
    let date_label: String?
    let resting_heart_rate: Int?
    let hrv: Int?
    let body_battery: Int?
    let sleep_score: Int?
    let sleep_duration_hours: Double?
    let sleep_duration_seconds: Int?
}

struct HealthTrendResponse: Codable {
    let trend: [HealthTrendPoint]?
}

// MARK: - Feed & Community

struct FeedComment: Codable, Identifiable {
    let id: String
    let activity_id: String?
    let user_id: String?
    let author_name: String?
    let author_avatar: String?
    let content: String
    let created_at: String?
}

struct FeedItem: Codable, Identifiable {
    let id: String
    let name: String
    let display_name: String
    let avatar_url: String?
    let distance_meters: Double
    let distance_km: Double?
    let avg_pace_str: String?
    let average_heartrate: Int?
    let elevation_gain_meters: Double?
    let trimp: Double?
    let ai_journal: String?
    let start_time: String?
    var likes_count: Int?
    var has_liked: Bool?
    var comments: [FeedComment]?
    
    var km: Double {
        if let k = distance_km, k > 0 { return k }
        return distance_meters / 1000.0
    }
}

struct FeedResponse: Codable {
    let feed: [FeedItem]?
}

extension ActivityItem {
    init(feed: FeedItem) {
        self.id = feed.id
        self.name = feed.name
        self.sport_type = "running"
        self.distance_meters = feed.distance_meters
        self.distance_km = feed.km
        self.moving_time_seconds = nil
        self.avg_pace_str = feed.avg_pace_str
        self.average_heartrate = feed.average_heartrate
        self.start_time = feed.start_time
        self.elevation_gain_meters = feed.elevation_gain_meters
        self.trimp = feed.trimp
        self.ai_journal = feed.ai_journal
        self.has_gps_track = true
        self.map_image_url = nil
    }
}

// MARK: - Coach Plan & Analysis

struct CoachPlanPhase: Codable, Identifiable {
    var id: String { name ?? UUID().uuidString }
    let name: String?
    let weeks_range: String?
    let focus: String?
    let description: String?
}

struct PlanDayWorkout: Codable, Identifiable {
    var id: String { "\(date ?? "")_\(day_index ?? 0)_\(title ?? "")" }
    let day_of_week: String?
    let date: String?
    let day_index: Int?
    let workout_type: String?
    let title: String?
    let distance_km: Double?
    let target_pace: String?
    let target_hr_zone: String?
    let description: String?
    let completed: Bool?
    let coach_notes: String?
    let actual_distance_km: Double?
    let actual_pace: String?
    let actual_heartrate: Int?
    let actual_execution_text: String?
    let recovery_pct: Int?
    let strain_score: Double?
}

struct PlanWeekSummary: Codable {
    let planned_mileage_km: Double?
    let actual_mileage_km: Double?
    let completion_pct: Double?
    let strength_count: Int?
    let summary_header_line: String?
    let coach_weekly_diagnosis: String?
}

struct PlanWeekItem: Codable, Identifiable {
    var id: Int { week_index ?? 1 }
    let week_index: Int?
    let week_title: String?
    let phase: String?
    let weekly_mileage_km: Double?
    let key_focus: String?
    let days: [PlanDayWorkout]?
    let week_summary: PlanWeekSummary?
}

struct PlanScheduleData: Codable {
    let macro_cycle_name: String?
    let goal_summary: String?
    let weeks: [PlanWeekItem]?
}

struct ActivePlanData: Codable {
    let id: String?
    let title: String?
    let target_race_name: String?
    let target_date: String?
    let target_time: String?
    let start_date: String?
    let end_date: String?
    let weeks_count: Int?
    let days_per_week: Int?
    let current_week: Int?
    let current_week_index: Int?
    let current_week_dates: [String]?
    let overview_summary: String?
    let coach_review_note: String?
    let phases: [CoachPlanPhase]?
    let summary: String?
    let schedule_data: PlanScheduleData?
}

struct CoachPlanResponse: Codable {
    let active_plan: ActivePlanData?
}

struct CoachTSBMetrics: Codable {
    let ctl: Double?
    let atl: Double?
    let tsb: Double?
    let acwr: Double?
    let status: String?
    let risk_warning: String?
}

struct CoachZoneDetail: Codable {
    let name: String?
    let range: String?
    let desc: String?
}

struct CoachRaceZones: Codable {
    let recovery: CoachZoneDetail?
    let fundamental: CoachZoneDetail?
    let special: CoachZoneDetail?
    let specific: CoachZoneDetail?
    let max_specific: CoachZoneDetail?
}

struct CoachAthleteSnapshot: Codable {
    let name: String?
    let age: Int?
    let gender: String?
    let years_running: Int?
    let target_race: String?
    let target_time: String?
    let race_category: String?
    let race_category_name: String?
}

struct CoachAnalysisResponse: Codable {
    let summary: String?
    let fitness_status: String?
    let periodization_phase: String?
    let key_suggestions: [String]?
    let focus_workout_of_the_week: String?
    let recovery_advice: String?
    let tsb_metrics: CoachTSBMetrics?
    let athlete_snapshot: CoachAthleteSnapshot?
    let race_zones: CoachRaceZones?
}

// MARK: - Client Dashboard State Data

struct DashboardData {
    var monthMileage: Double = 0.0
    var monthTarget: Double = 200.0
    var progressPercent: Double = 0.0
    var runCount: Int = 0
    var avgPace: String = "--"
    var recentActivities: [ActivityItem] = []
    var fitnessForm: FitnessFormData?
    var todayHealth: TodayHealthData?
    var aiCoachTip: String?
    
    var weeklyProgress: WeeklyProgressData?
    var todayWorkout: TodayWorkoutData?
    var yearlyStats: YearlyStatsData?
    
    var progress: Double {
        guard monthTarget > 0 else { return 0 }
        return min(monthMileage / monthTarget, 1.0)
    }
    
    var completionPercent: Int {
        if progressPercent > 0 {
            return Int(progressPercent)
        }
        return Int(progress * 100)
    }
}

// MARK: - Leaderboard & Club Models

struct ClubItem: Codable, Identifiable {
    let id: String
    let name: String
    let logo_url: String?
    let description: String?
    let city: String?
    let invite_code: String?
    let member_count: Int?
    let role: String?
    let join_mode: String?
}

struct MyClubsResponse: Codable {
    let clubs: [ClubItem]?
}

struct LeaderboardEntry: Codable, Identifiable {
    var id: String { user_id }
    let user_id: String
    let display_name: String
    let avatar_url: String?
    let role: String?
    let distance_km: Double?
    let target_km: Double?
    let progress_pct: Double?
    var rank: Int = 0
    
    var total_distance_km: Double { distance_km ?? 0.0 }
    var completion_rate: Double? {
        if let p = progress_pct { return p / 100.0 }
        return nil
    }
}

struct LeaderboardResponse: Codable {
    let leaderboard: [LeaderboardEntry]?
}

// MARK: - Coach Chat Models

struct CoachMessage: Identifiable, Equatable {
    let id = UUID()
    let isUser: Bool
    let text: String
    let date = Date()
}

// MARK: - GPS Track & Elevation Profile Models

struct GpsTrackPoint: Codable, Identifiable {
    var id: String { "\(latitude)_\(longitude)" }
    let latitude: Double
    let longitude: Double
}

struct ElevationProfilePoint: Codable, Identifiable {
    var id: Double { dist_km }
    let dist_km: Double
    let elevation_m: Double
    let hr: Int?
}

struct TrackBounds: Codable {
    let min_lat: Double?
    let max_lat: Double?
    let min_lon: Double?
    let max_lon: Double?
}

struct TrackCenter: Codable {
    let latitude: Double
    let longitude: Double
}

struct ActivityTrackData: Codable {
    let activity_id: String?
    let total_points: Int?
    let original_point_count: Int?
    let center: TrackCenter?
    let bounds: TrackBounds?
    let start_point: GpsTrackPoint?
    let end_point: GpsTrackPoint?
    let points: [GpsTrackPoint]?
    let elevation_profile: [ElevationProfilePoint]?
}

struct HealthKitImportResponse: Codable {
    let success: Bool?
    let imported_workouts: Int?
    let workouts_with_gps: Int?
    let health_days: Int?
    let message: String?
}

struct TrackFileImportResponse: Codable {
    let success: Bool?
    let activity_id: String?
    let distance_km: Double?
    let gps_points: Int?
    let message: String?
}

struct ActivityTrackResponse: Codable {
    let success: Bool?
    let activity: ActivityItem?
    let track: ActivityTrackData?
    let map_image_url: String?
}

// MARK: - Full Profile, Races & Organization Models

struct RaceInfoData: Codable, Equatable {
    var race_distance_km: Double?
    var elevation_gain_m: Double?
    var net_elevation_gain_m: Double?
    var elevation_loss_m: Double?
    var max_altitude_m: Double?
    var difficulty_level: String?
    var terrain_type: String?
    var climate_zone: String?
    var mandatory_gear: String?
    var cutoff_notes: String?
    var race_level: String?
    var course_profile: String?
    var course_surface: String?
    var avg_temp_c: Double?
    var humidity_pct: Double?
    var weather_notes: String?
    var typical_participants: Int?
    var custom_notes: String?
    
    init(
        race_distance_km: Double? = nil,
        elevation_gain_m: Double? = nil,
        net_elevation_gain_m: Double? = nil,
        elevation_loss_m: Double? = nil,
        max_altitude_m: Double? = nil,
        difficulty_level: String? = nil,
        terrain_type: String? = nil,
        climate_zone: String? = nil,
        mandatory_gear: String? = nil,
        cutoff_notes: String? = nil,
        race_level: String? = nil,
        course_profile: String? = nil,
        course_surface: String? = nil,
        avg_temp_c: Double? = nil,
        humidity_pct: Double? = nil,
        weather_notes: String? = nil,
        typical_participants: Int? = nil,
        custom_notes: String? = nil
    ) {
        self.race_distance_km = race_distance_km
        self.elevation_gain_m = elevation_gain_m
        self.net_elevation_gain_m = net_elevation_gain_m
        self.elevation_loss_m = elevation_loss_m
        self.max_altitude_m = max_altitude_m
        self.difficulty_level = difficulty_level
        self.terrain_type = terrain_type
        self.climate_zone = climate_zone
        self.mandatory_gear = mandatory_gear
        self.cutoff_notes = cutoff_notes
        self.race_level = race_level
        self.course_profile = course_profile
        self.course_surface = course_surface
        self.avg_temp_c = avg_temp_c
        self.humidity_pct = humidity_pct
        self.weather_notes = weather_notes
        self.typical_participants = typical_participants
        self.custom_notes = custom_notes
    }
    
    enum CodingKeys: String, CodingKey {
        case race_distance_km
        case elevation_gain_m
        case net_elevation_gain_m
        case elevation_loss_m
        case max_altitude_m
        case difficulty_level
        case terrain_type
        case climate_zone
        case mandatory_gear
        case cutoff_notes
        case race_level
        case course_profile
        case course_surface
        case avg_temp_c
        case humidity_pct
        case weather_notes
        case typical_participants
        case custom_notes
    }
    
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        func decodeDouble(_ key: CodingKeys) -> Double? {
            if let v = try? c.decodeIfPresent(Double.self, forKey: key) { return v }
            if let s = try? c.decodeIfPresent(String.self, forKey: key), let v = Double(s) { return v }
            return nil
        }
        func decodeInt(_ key: CodingKeys) -> Int? {
            if let v = try? c.decodeIfPresent(Int.self, forKey: key) { return v }
            if let d = try? c.decodeIfPresent(Double.self, forKey: key) { return Int(d.rounded()) }
            if let s = try? c.decodeIfPresent(String.self, forKey: key), let v = Int(s) { return v }
            return nil
        }
        func decodeStr(_ key: CodingKeys) -> String? {
            if let s = try? c.decodeIfPresent(String.self, forKey: key), !s.isEmpty { return s }
            return nil
        }
        race_distance_km = decodeDouble(.race_distance_km)
        elevation_gain_m = decodeDouble(.elevation_gain_m)
        net_elevation_gain_m = decodeDouble(.net_elevation_gain_m)
        elevation_loss_m = decodeDouble(.elevation_loss_m)
        max_altitude_m = decodeDouble(.max_altitude_m)
        difficulty_level = decodeStr(.difficulty_level)
        terrain_type = decodeStr(.terrain_type)
        climate_zone = decodeStr(.climate_zone)
        mandatory_gear = decodeStr(.mandatory_gear)
        cutoff_notes = decodeStr(.cutoff_notes)
        race_level = decodeStr(.race_level)
        course_profile = decodeStr(.course_profile)
        course_surface = decodeStr(.course_surface)
        avg_temp_c = decodeDouble(.avg_temp_c)
        humidity_pct = decodeDouble(.humidity_pct)
        weather_notes = decodeStr(.weather_notes)
        typical_participants = decodeInt(.typical_participants)
        custom_notes = decodeStr(.custom_notes)
    }
    
    var hasAnyValue: Bool {
        return race_distance_km != nil ||
            elevation_gain_m != nil ||
            net_elevation_gain_m != nil ||
            elevation_loss_m != nil ||
            max_altitude_m != nil ||
            (difficulty_level?.isEmpty == false) ||
            (terrain_type?.isEmpty == false) ||
            (climate_zone?.isEmpty == false) ||
            (mandatory_gear?.isEmpty == false) ||
            (cutoff_notes?.isEmpty == false) ||
            (race_level?.isEmpty == false) ||
            (course_profile?.isEmpty == false) ||
            (course_surface?.isEmpty == false) ||
            avg_temp_c != nil ||
            humidity_pct != nil ||
            (weather_notes?.isEmpty == false) ||
            typical_participants != nil ||
            (custom_notes?.isEmpty == false)
    }
    
    func toDictionary() -> [String: Any] {
        var dict: [String: Any] = [:]
        if let v = race_distance_km { dict["race_distance_km"] = v }
        if let v = elevation_gain_m { dict["elevation_gain_m"] = v }
        if let v = net_elevation_gain_m { dict["net_elevation_gain_m"] = v }
        if let v = elevation_loss_m { dict["elevation_loss_m"] = v }
        if let v = max_altitude_m { dict["max_altitude_m"] = v }
        if let v = difficulty_level, !v.isEmpty { dict["difficulty_level"] = v }
        if let v = terrain_type, !v.isEmpty { dict["terrain_type"] = v }
        if let v = climate_zone, !v.isEmpty { dict["climate_zone"] = v }
        if let v = mandatory_gear, !v.isEmpty { dict["mandatory_gear"] = v }
        if let v = cutoff_notes, !v.isEmpty { dict["cutoff_notes"] = v }
        if let v = race_level, !v.isEmpty { dict["race_level"] = v }
        if let v = course_profile, !v.isEmpty { dict["course_profile"] = v }
        if let v = course_surface, !v.isEmpty { dict["course_surface"] = v }
        if let v = avg_temp_c { dict["avg_temp_c"] = v }
        if let v = humidity_pct { dict["humidity_pct"] = v }
        if let v = weather_notes, !v.isEmpty { dict["weather_notes"] = v }
        if let v = typical_participants { dict["typical_participants"] = v }
        if let v = custom_notes, !v.isEmpty { dict["custom_notes"] = v }
        return dict
    }
}

struct RaceIntelLookupResponse: Codable {
    let success: Bool?
    let message: String?
    let race_category: String?
    let source: String?
    let race_info: RaceInfoData?
}

struct MatchedRaceActivityItem: Codable {
    let id: String?
    let name: String?
    let distance_km: Double?
    let formatted_time: String?
    let avg_pace_str: String?
}

struct MatchedRaceActivityResponse: Codable {
    let matched: Bool?
    let message: String?
    let activity: MatchedRaceActivityItem?
}

struct RaceItem: Codable, Identifiable {
    let id: String
    let name: String
    let race_type: String?
    let race_date: String?
    let target_time: String?
    let priority: Int?
    let status: String?
    let finish_time: String?
    let finish_notes: String?
    let is_completed: Bool?
    let is_past: Bool?
    let days_left: Int?
    let photo_url: String?
    let photos: [String]?
    let performance_badge: String?
    let diff_str: String?
    let race_info: RaceInfoData?
}

struct UserOrgItem: Codable, Identifiable {
    let id: String
    let name: String
    let logo_url: String?
    let description: String?
    let role: String?
    let status: String?
    let real_name: String?
    let class_name: String?
    let program: String?
    let class_detail: String?
    let gobi_experience: String?
    let age_group: String?
    let days_remaining: Int?
}

struct UserOrgsResponse: Codable {
    let organizations: [UserOrgItem]?
}

struct FullProfileData: Codable {
    let id: String
    let display_name: String?
    let avatar_url: String?
    let phone: String?
    let real_name: String?
    let id_card: String?
    let date_of_birth: String?
    let age: Int?
    let age_group: String?
    let gender: String?
    let program: String?
    let class_detail: String?
    let class_name: String?
    let gobi_experience: String?
    let clothing_size: String?
    let shoe_size: String?
    let height_cm: Double?
    let weight_kg: Double?
    let years_running: Int?
    let max_heart_rate: Int?
    let resting_heart_rate: Int?
    let vo2max: Double?
    let marathon_pb: Int?
    let half_pb: Int?
    let ten_k_pb: Int?
    let five_k_pb: Int?
    let garmin_connected: Bool?
    let garmin_email: String?
    let garmin_domain: String?
    let coros_connected: Bool?
    let coros_account: String?
    let coros_domain: String?
    let apple_watch_connected: Bool?
    let huawei_connected: Bool?
    let huawei_account: String?
    let bio: String?
}

struct UserGoalData: Codable, Equatable {
    let user_id: String?
    let year: Int?
    let period_type: String?
    let target_distance: Double?
    let weekly_target: Double?
    let monthly_targets: [Double]?
    
    var monthlyTargetsInt: [Int] {
        let fallback = Int((target_distance ?? 200.0).rounded())
        guard let arr = monthly_targets, !arr.isEmpty else {
            return Array(repeating: fallback, count: 12)
        }
        var result = arr.map { Int($0.rounded()) }
        while result.count < 12 {
            result.append(fallback)
        }
        return Array(result.prefix(12))
    }
}

struct FullProfileResponse: Codable {
    let profile: FullProfileData?
    let goal: UserGoalData?
    let races: [RaceItem]?
}

// MARK: - Club Periodic Report (周报 / 月报)

struct ClubReportRunner: Codable, Identifiable {
    var id: String { user_id }
    let user_id: String
    let display_name: String?
    let name: String?
    let avatar_url: String?
    let total_distance_km: Double?
    let distance_km: Double?
    let total_activities: Int?
    let runs_count: Int?
    let avg_pace: String?
    let avg_pace_str: String?
    let rank: Int?
    let target_km: Double?
    let completion_rate: Double?
    let status: String?
    let is_achieved: Bool?
    
    var effectiveName: String {
        display_name ?? name ?? "跑者"
    }
    
    var effectiveDistance: Double {
        total_distance_km ?? distance_km ?? 0.0
    }
    
    var effectiveActivities: Int {
        total_activities ?? runs_count ?? 0
    }
    
    var effectivePace: String? {
        avg_pace ?? avg_pace_str
    }
    
    var effectiveRank: Int {
        rank ?? 1
    }
}

struct PodiumRunner: Codable, Identifiable {
    var id: String { user_id }
    let user_id: String
    let name: String?
    let display_name: String?
    let distance_km: Double?
    let total_distance_km: Double?
    let rank: Int?
    let avatar_url: String?
    let avg_pace_str: String?
    
    var effectiveName: String {
        display_name ?? name ?? "跑者"
    }
    
    var effectiveDistance: Double {
        total_distance_km ?? distance_km ?? 0.0
    }
    
    var effectiveRank: Int {
        rank ?? 1
    }
}

struct ClubPeriodicReport: Codable {
    let club_id: String
    let club_name: String
    let period_type: String
    let period_label: String
    let date_range_str: String?
    let is_past_period: Bool?
    let total_distance_km: Double?
    let total_target_km: Double?
    let team_completion_rate: Double?
    let achieved_members_count: Int?
    let total_activities_count: Int?
    let active_members_count: Int?
    let total_members_count: Int?
    let attendance_rate_pct: Double?
    let avg_pace_str: String?
    let total_elevation_gain_m: Double?
    let total_trimp: Double?
    let leaderboard: [ClubReportRunner]?
    let podium: [PodiumRunner]?
    let canova_critique: String?
    let forward_text: String?
    
    var safeTotalDistance: Double { total_distance_km ?? 0.0 }
    var safeActiveMembers: Int { active_members_count ?? 0 }
    var safeTotalMembers: Int { total_members_count ?? 0 }
    var safeAttendancePct: Double { attendance_rate_pct ?? 0.0 }
}

// MARK: - Coach Cockpit (学员负荷罗盘)

struct CoachStudentMetric: Codable, Identifiable {
    var id: String { user_id }
    let user_id: String
    let display_name: String?
    let avatar_url: String?
    let ctl: Double?
    let atl: Double?
    let tsb: Double?
    let status_level: String? // "peak", "optimal", "tired", "danger"
    let status_label: String?
    let resting_heart_rate: Int?
    let hrv: Double?
    let target_race: String?
    let target_race_days: Int?
    let readiness_score: Int?
    let canova_advice: String?
}

struct CoachCockpitSummary: Codable {
    let total_students: Int
    let peak_count: Int
    let optimal_count: Int
    let tired_count: Int
    let danger_count: Int
}

struct CoachCockpitData: Codable {
    let summary: CoachCockpitSummary
    let students: [CoachStudentMetric]
}

// MARK: - Club Challenge & Events (跑团挑战赛)

struct ClubEvent: Codable, Identifiable {
    let id: String
    let club_id: String
    let title: String
    let event_type: String?
    let start_date: String?
    let end_date: String?
    let target_km: Double?
    let rules: String?
    let status: String?
    let participant_count: Int?
}

struct ClubEventsResponse: Codable {
    let events: [ClubEvent]?
}

// MARK: - WHOOP-Style Recovery, Strain, Sleep, Journal & Proactive Coach Models

enum WhoopRecoveryZone: String, Codable {
    case green  // 67% - 100%
    case yellow // 34% - 66%
    case red    // 0%  - 33%
    
    var label: String {
        switch self {
        case .green: return "绿灯 · 巅峰就绪"
        case .yellow: return "黄灯 · 稳态维持"
        case .red: return "红灯 · 亟需恢复"
        }
    }
    
    var hexColor: String {
        switch self {
        case .green: return "16EC06"
        case .yellow: return "FFDE00"
        case .red: return "FF0026"
        }
    }
}

struct WhoopJournalBehavior: Identifiable, Codable, Hashable {
    let id: String
    let title: String
    let subtitle: String
    let icon: String
    let isPositiveHabit: Bool
    let baseImpactPct: Int // Empirical baseline impact on next-day Recovery %
    let baseHrvDeltaMs: Int
    
    static let allBehaviors: [WhoopJournalBehavior] = [
        WhoopJournalBehavior(id: "foam_roll", title: "跑后拉伸 / 泡沫轴", subtitle: "15分钟以上筋膜放松", icon: "figure.cooldown", isPositiveHabit: true, baseImpactPct: 8, baseHrvDeltaMs: 4),
        WhoopJournalBehavior(id: "magnesium", title: "补镁 / 电解质水合", subtitle: "睡前镁剂或全天足量电解质", icon: "pills.fill", isPositiveHabit: true, baseImpactPct: 7, baseHrvDeltaMs: 5),
        WhoopJournalBehavior(id: "carb_refuel", title: "跑后黄金窗口补碳/蛋白", subtitle: "运动后30分钟内糖原补充", icon: "fork.knife", isPositiveHabit: true, baseImpactPct: 6, baseHrvDeltaMs: 3),
        WhoopJournalBehavior(id: "cold_therapy", title: "冷水浴 / 下肢冰敷", subtitle: "降低下肢微炎症反应", icon: "snowflake", isPositiveHabit: true, baseImpactPct: 5, baseHrvDeltaMs: 3),
        WhoopJournalBehavior(id: "no_screen_bed", title: "睡前远离蓝光 / 阅读", subtitle: "入睡前45分钟不刷手机", icon: "book.closed.fill", isPositiveHabit: true, baseImpactPct: 9, baseHrvDeltaMs: 5),
        WhoopJournalBehavior(id: "shoe_rotation", title: "非碳板缓震跑鞋轮换", subtitle: "减轻跟腱与小腿离心负荷", icon: "shoeprints.fill", isPositiveHabit: true, baseImpactPct: 4, baseHrvDeltaMs: 2),
        WhoopJournalBehavior(id: "alcohol", title: "饮酒", subtitle: "显著抑制慢波深睡与副交感恢复", icon: "wineglass.fill", isPositiveHabit: false, baseImpactPct: -19, baseHrvDeltaMs: -11),
        WhoopJournalBehavior(id: "late_caffeine", title: "15:00 后摄入咖啡因", subtitle: "延长入睡潜伏期、降低深睡占比", icon: "cup.and.saucer.fill", isPositiveHabit: false, baseImpactPct: -9, baseHrvDeltaMs: -5),
        WhoopJournalBehavior(id: "late_meal", title: "21:30 后深夜进食", subtitle: "夜间消化负荷推高静息心率", icon: "moon.zzz.fill", isPositiveHabit: false, baseImpactPct: -11, baseHrvDeltaMs: -6),
        WhoopJournalBehavior(id: "high_work_stress", title: "高压会议 / 精神焦虑", subtitle: "全天交感神经持续亢奋", icon: "brain.head.profile", isPositiveHabit: false, baseImpactPct: -10, baseHrvDeltaMs: -5),
        WhoopJournalBehavior(id: "muscle_soreness", title: "延迟性肌肉酸痛 (DOMS)", subtitle: "股四头肌/小腿紧绷或微损伤", icon: "bolt.heart.fill", isPositiveHabit: false, baseImpactPct: -8, baseHrvDeltaMs: -4),
        WhoopJournalBehavior(id: "travel_jetlag", title: "差旅奔波 / 作息紊乱", subtitle: "睡眠节律偏移与久坐疲劳", icon: "airplane", isPositiveHabit: false, baseImpactPct: -12, baseHrvDeltaMs: -7)
    ]
}

struct WhoopHabitImpact: Identifiable {
    var id: String { behavior.id }
    let behavior: WhoopJournalBehavior
    let impactPct: Int
    let hrvDeltaMs: Int
    let loggedDaysCount: Int
    /// true = computed from this runner's own journal vs. next-day HRV; false = literature reference value
    let isPersonalized: Bool
    let yesDays: Int
    let noDays: Int
}

struct WhoopSnapshot {
    // 1. Recovery (0 - 100%): Morning Baseline vs. Real-Time Dynamic Readiness
    let recoveryScore: Int
    let morningRecoveryScore: Int
    let realtimeRecoveryScore: Int
    let daytimeRecoveryDrainPct: Int
    let daytimeNapBonusPct: Int
    let recoveryZone: WhoopRecoveryZone
    let recoveryHeadline: String
    let recoveryDetail: String
    
    // 2. Day Strain (0.0 - 21.0 logarithmic scale)
    let dayStrain: Double
    let workoutStrain: Double
    let baselineLivingStrain: Double
    let daytimeActivityStrainAdded: Double
    let optimalStrainLow: Double
    let optimalStrainHigh: Double
    let strainStateLabel: String
    
    // 3. Sleep Performance & Sleep Coach
    let sleepPerformancePct: Int
    let actualSleepHours: Double
    let neededSleepHours: Double
    let baselineSleepHours: Double
    let strainAddedSleepMinutes: Int
    let sleepDebtMinutes: Int
    let recommendedBedtime100: String
    let recommendedBedtime85: String
    let wakeTimeText: String
    
    // 4. Autonomic Nervous System & Stress (0.0 - 3.0)
    let hrvToday: Int
    let hrvBaseline: Int
    let rhrToday: Int
    let rhrBaseline: Int
    let stressScore: Double
    let stressLevelLabel: String
    
    // 5. Daytime Activity, Naps, Watch Stress & Heart Rate Fluctuation
    let daytimeSteps: Int
    let daytimeActiveCalories: Int
    let napMinutes: Int
    let watchStressAvg: Int?
    let watchStressMax: Int?
    let hrMinToday: Int
    let hrMaxToday: Int
    let bodyBatteryCurrent: Int?
    let bodyBatteryMax: Int?
    let lastUpdatedText: String

    // 6. Healthspan & Biological Age
    let vo2Max: Double
    let biologicalAgeDelta: Double // Negative means younger than chronological age
    let paceOfAging: Double        // < 1.0 means slower aging rate
    let dataSourceLabel: String
    /// Inputs that fell back to defaults (e.g. "HRV", "静息心率", "睡眠"), shown as a disclosure in the UI
    let missingInputs: [String]
}

struct ProactiveCoachAlert: Identifiable, Equatable {
    let id: String
    let severity: String // "critical", "warning", "optimal", "info"
    let category: String // "恢复预警", "负荷监控", "睡眠处方", "习惯联动", "课表决策"
    let icon: String
    let title: String
    let message: String
    let metricTag: String
    let actionLabel: String
    let actionPrompt: String
}


