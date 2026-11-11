import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case serverError(String)
    case mfaRequired(String)
    case unauthorized
    case decodingError
    
    var errorDescription: String? {
        switch self {
        case .invalidURL: return "无效的请求地址"
        case .serverError(let msg): return msg
        case .mfaRequired(let msg): return msg
        case .unauthorized: return "登录已失效，请重新登录"
        case .decodingError: return "数据解析失败"
        }
    }
}

class APIService {
    static let shared = APIService()
    
    // Production backend domain matching Web & Mini-Program
    let baseURL = "https://rgm.vanpower.net"
    
    private init() {}
    
    private func request<T: Decodable>(
        path: String,
        method: String = "GET",
        body: [String: Any]? = nil,
        timeout: TimeInterval = 30
    ) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }
        
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.timeoutInterval = timeout
        req.cachePolicy = .reloadIgnoringLocalCacheData
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let token = StorageManager.shared.token, !token.isEmpty {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        if let body = body {
            req.httpBody = try JSONSerialization.data(withJSONObject: body)
        }
        
        let (data, response) = try await URLSession.shared.data(for: req)
        
        guard let httpRes = response as? HTTPURLResponse else {
            throw APIError.serverError("网络响应异常")
        }
        
        if httpRes.statusCode == 401 {
            StorageManager.shared.clear()
            throw APIError.unauthorized
        }
        
        guard (200...299).contains(httpRes.statusCode) else {
            if let errObj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let detail = errObj["detail"] as? String ?? errObj["message"] as? String {
                throw APIError.serverError(detail)
            }
            throw APIError.serverError("请求失败 (\(httpRes.statusCode))")
        }
        
        do {
            return try JSONDecoder().decode(T.self, from: data)
        } catch {
            print("[APIService] Decoding error for \(path): \(error)")
            throw APIError.decodingError
        }
    }
    
    // MARK: - Auth
    
    func appleLogin(appleUserId: String, identityToken: String?, email: String?, fullName: String?) async throws -> UserProfile {
        var body: [String: Any] = [
            "apple_user_id": appleUserId,
            "client_uuid": StorageManager.shared.clientUUID
        ]
        if let it = identityToken { body["identity_token"] = it }
        if let em = email { body["email"] = em }
        if let fn = fullName { body["full_name"] = fn }
        
        let res: AuthResponse = try await request(path: "/api/auth/apple/login", method: "POST", body: body)
        guard let uid = res.uid, let token = res.token else {
            throw APIError.serverError(res.message ?? "登录失败")
        }
        StorageManager.shared.token = token
        
        let profile = UserProfile(
            id: uid,
            display_name: res.display_name ?? "Apple跑者",
            avatar_url: res.avatar_url,
            phone: nil,
            garmin_connected: res.garmin_connected ?? false,
            garmin_email: res.garmin_email,
            garmin_domain: res.garmin_domain ?? "garmin.cn",
            coros_connected: res.coros_connected ?? false,
            coros_account: res.coros_account,
            coros_domain: res.coros_domain ?? "teamcnapi.coros.com"
        )
        StorageManager.shared.saveUser(profile)
        return profile
    }
    
    /// Demo account for App Store reviewers: signs into a dedicated synthetic account (no real user data).
    func demoLogin() async throws -> UserProfile {
        let res: AuthResponse = try await request(path: "/api/auth/demo-login", method: "POST", body: [:])
        guard let uid = res.uid, let token = res.token else {
            throw APIError.serverError(res.message ?? "演示登录失败")
        }
        StorageManager.shared.token = token
        
        let profile = UserProfile(
            id: uid,
            display_name: res.display_name ?? "演示跑者",
            avatar_url: res.avatar_url,
            phone: nil,
            garmin_connected: false,
            garmin_email: nil,
            garmin_domain: "garmin.cn",
            coros_connected: false,
            coros_account: nil,
            coros_domain: "teamcnapi.coros.com"
        )
        StorageManager.shared.saveUser(profile)
        return profile
    }
    
    /// Binds Garmin or COROS cloud account to the current runner (or logs in directly if not logged in).
    /// Supports 2FA/MFA verification codes.
    func bindOrLoginDevice(
        uid: String?,
        brand: String,
        account: String,
        password: String,
        domain: String,
        mfaCode: String? = nil
    ) async throws -> (UserProfile, String?) {
        let path: String
        var body: [String: Any]
        
        if let uid = uid, !uid.isEmpty, uid != "u_demo_runner" {
            if brand == "garmin" {
                path = "/api/auth/garmin/bind"
                body = [
                    "uid": uid,
                    "email": account,
                    "password": password,
                    "domain": domain
                ]
                if let code = mfaCode, !code.isEmpty {
                    body["mfa_code"] = code
                }
            } else {
                path = "/api/auth/coros/bind"
                body = [
                    "uid": uid,
                    "account": account,
                    "password": password,
                    "domain": domain
                ]
                if let code = mfaCode, !code.isEmpty {
                    body["code"] = code
                    body["mfa_code"] = code
                }
            }
        } else {
            path = "/api/auth/device-login"
            body = [
                "brand": brand,
                "account": account,
                "password": password,
                "domain": domain,
                "client_uuid": StorageManager.shared.clientUUID
            ]
            if let code = mfaCode, !code.isEmpty {
                body["mfa_code"] = code
                body["code"] = code
            }
        }
        
        let res: AuthResponse = try await request(path: path, method: "POST", body: body, timeout: 60)
        if res.needs_mfa == true || res.needs_2fa == true {
            throw APIError.mfaRequired(res.message ?? "官方服务器已发送 6 位安全验证码，请输入验证码完成绑定")
        }
        guard let resolvedUid = res.uid, let token = res.token else {
            throw APIError.serverError(res.message ?? "设备验证未完成")
        }
        StorageManager.shared.token = token
        
        let profile = UserProfile(
            id: resolvedUid,
            display_name: res.display_name ?? (brand == "garmin" ? "佳明跑者" : "高驰跑者"),
            avatar_url: res.avatar_url,
            phone: nil,
            garmin_connected: res.garmin_connected ?? (brand == "garmin"),
            garmin_email: res.garmin_email ?? (brand == "garmin" ? account : nil),
            garmin_domain: res.garmin_domain ?? (brand == "garmin" ? domain : "garmin.cn"),
            coros_connected: res.coros_connected ?? (brand == "coros"),
            coros_account: res.coros_account ?? (brand == "coros" ? account : nil),
            coros_domain: res.coros_domain ?? (brand == "coros" ? domain : "teamcnapi.coros.com"),
            apple_watch_connected: res.apple_watch_connected,
            huawei_connected: res.huawei_connected,
            huawei_account: res.huawei_account
        )
        StorageManager.shared.saveUser(profile)
        return (profile, res.message)
    }
    
    func bindHealthWatch(uid: String, brand: String, account: String? = nil) async throws -> String {
        let path = (brand == "apple_watch") ? "/api/auth/apple-watch/bind" : "/api/auth/huawei/bind"
        var body: [String: Any] = ["uid": uid]
        if let account = account, !account.isEmpty {
            body["account"] = account
        }
        let res: AuthResponse = try await request(path: path, method: "POST", body: body)
        return res.message ?? "设备已连接"
    }
    
    func unbindDevice(uid: String, brand: String) async throws -> String {
        struct UnbindResponse: Codable {
            let success: Bool?
            let message: String?
        }
        let path: String
        switch brand {
        case "garmin":
            path = "/api/auth/garmin/unbind"
        case "coros":
            path = "/api/auth/coros/unbind"
        case "apple_watch":
            path = "/api/auth/apple-watch/unbind"
        default:
            path = "/api/auth/huawei/unbind"
        }
        let res: UnbindResponse = try await request(path: path, method: "POST", body: ["uid": uid])
        return res.message ?? "已解除绑定"
    }
    
    // MARK: - Dashboard (Unified MiniApp & Web Endpoint)
    
    func fetchDashboard(uid: String) async throws -> DashboardResponse {
        return try await request(path: "/api/miniapp/dashboard/\(uid)")
    }
    
    // MARK: - Sync
    
    func triggerSync(uid: String) async throws -> String {
        struct SyncResponse: Codable {
            let message: String?
            let success: Bool?
            let error: String?
        }
        let res: SyncResponse = try await request(
            path: "/api/sync/trigger",
            method: "POST",
            body: ["uid": uid]
        )
        if res.success == false {
            throw APIError.serverError(res.error ?? "手表同步未完成")
        }
        return res.message ?? "同步请求已送达，跑步记录正在入库..."
    }
    
    // MARK: - Clubs & Leaderboard
    
    func fetchMyClubs(uid: String) async throws -> [ClubItem] {
        let res: MyClubsResponse = try await request(path: "/api/team/my-clubs/\(uid)")
        return res.clubs ?? []
    }
    
    func fetchClubLeaderboard(clubId: String, uid: String) async throws -> [LeaderboardEntry] {
        let res: LeaderboardResponse = try await request(path: "/api/team/\(clubId)/leaderboard?user_id=\(uid)")
        return res.leaderboard ?? []
    }
    
    func joinClubByInvite(uid: String, inviteCode: String) async throws -> String {
        struct JoinResponse: Codable {
            let message: String?
            let club: ClubItem?
        }
        let res: JoinResponse = try await request(
            path: "/api/team/join",
            method: "POST",
            body: [
                "user_id": uid,
                "invite_code": inviteCode.trimmingCharacters(in: .whitespacesAndNewlines).uppercased(),
                "privacy_consent": true
            ]
        )
        return res.message ?? "成功加入跑团！"
    }
    
    // MARK: - Account Deletion (App Store Guideline 5.1.1(v))
    
    func deleteAccount(uid: String) async throws -> Bool {
        struct DeleteAccResponse: Codable {
            let success: Bool?
            let message: String?
        }
        let res: DeleteAccResponse = try await request(
            path: "/api/profile/\(uid)/delete-account",
            method: "POST"
        )
        return res.success ?? true
    }
    
    // MARK: - Canova AI Coach
    
    func askCanovaCoach(message: String, uid: String? = nil) async throws -> String {
        struct CoachResponse: Codable {
            let reply: String?
            let answer: String?
        }
        var body: [String: Any] = ["message": message]
        if let uid = uid {
            body["uid"] = uid
        }
        let res: CoachResponse = try await request(path: "/api/coach/chat", method: "POST", body: body)
        var text = (res.reply ?? res.answer ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        
        // If backend returned a JSON string inside reply, extract the friendly text
        if text.hasPrefix("{") && text.contains("summary") {
            if let data = text.data(using: .utf8),
               let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                let summary = obj["summary"] as? String ?? ""
                let fitness = obj["fitness_status"] as? String ?? ""
                let suggestions = (obj["key_suggestions"] as? [String])?.map { "• \($0)" }.joined(separator: "\n") ?? ""
                var combined = summary
                if !fitness.isEmpty { combined += "\n\n" + fitness }
                if !suggestions.isEmpty { combined += "\n\n战术建议：\n" + suggestions }
                return combined.isEmpty ? text : combined
            }
        }
        return text.isEmpty ? "教练正在分析您的训练负荷..." : text
    }
    
    // MARK: - Science & Health
    
    func fetchScienceMetrics(uid: String) async throws -> ScienceMetricsResponse {
        return try await request(path: "/api/science/metrics/\(uid)")
    }
    
    func fetchHealthTrend(uid: String) async throws -> [HealthTrendPoint] {
        let res: HealthTrendResponse = try await request(path: "/api/science/health-trend/\(uid)")
        return res.trend ?? []
    }
    
    // MARK: - Team Feed & Social Interactions
    
    func fetchClubFeed(clubId: String, uid: String) async throws -> [FeedItem] {
        let res: FeedResponse = try await request(path: "/api/team/\(clubId)/feed?user_id=\(uid)")
        return res.feed ?? []
    }
    
    func toggleActivityLike(activityId: String, uid: String) async throws -> (liked: Bool, count: Int) {
        struct LikeResponse: Codable {
            let liked: Bool
            let likes_count: Int
        }
        let res: LikeResponse = try await request(
            path: "/api/team/activities/\(activityId)/like",
            method: "POST",
            body: ["user_id": uid]
        )
        return (res.liked, res.likes_count)
    }
    
    func postActivityComment(activityId: String, uid: String, content: String, authorName: String, authorAvatar: String?) async throws -> FeedComment {
        struct CommentResponse: Codable {
            let message: String?
            let comment: FeedComment
        }
        var body: [String: Any] = [
            "user_id": uid,
            "content": content,
            "author_name": authorName
        ]
        if let av = authorAvatar, !av.isEmpty {
            body["author_avatar"] = av
        }
        let res: CommentResponse = try await request(
            path: "/api/team/activities/\(activityId)/comments",
            method: "POST",
            body: body
        )
        return res.comment
    }
    
    func deleteActivityComment(activityId: String, commentId: String, uid: String) async throws {
        struct DeleteResponse: Codable {
            let success: Bool?
            let message: String?
        }
        let _: DeleteResponse = try await request(
            path: "/api/team/activities/\(activityId)/comments/\(commentId)?user_id=\(uid)",
            method: "DELETE"
        )
    }
    
    // MARK: - Coach Plan & Latest Analysis
    
    func fetchCoachPlan(uid: String) async throws -> ActivePlanData? {
        let res: CoachPlanResponse = try await request(path: "/api/coach/plan/user/\(uid)")
        return res.active_plan
    }
    
    func fetchCoachAnalysis(uid: String) async throws -> CoachAnalysisResponse {
        return try await request(path: "/api/coach/latest/\(uid)")
    }
    
    func triggerCoachAnalysis(uid: String) async throws -> CoachAnalysisResponse {
        return try await request(path: "/api/coach/analysis", method: "POST", body: ["uid": uid])
    }
    
    // MARK: - GPS Track & Elevation
    
    /// Uploads Apple HealthKit workouts (with GPS route / HR / cadence) and daily health metrics to the server.
    func uploadHealthKit(uid: String, workouts: [[String: Any]], dailyHealth: [[String: Any]], watchBrand: String? = nil) async throws -> HealthKitImportResponse {
        var body: [String: Any] = ["uid": uid, "workouts": workouts, "daily_health": dailyHealth]
        if let watchBrand = watchBrand, !watchBrand.isEmpty {
            body["watch_brand"] = watchBrand
        }
        return try await request(path: "/api/sync/healthkit", method: "POST", body: body, timeout: 90)
    }
    
    /// Uploads a GPX or TCX track file exported from Huawei Health or Apple Watch.
    func importTrackFile(uid: String, filename: String, contentBase64: String, sourceBrand: String = "huawei") async throws -> TrackFileImportResponse {
        let body: [String: Any] = [
            "uid": uid,
            "filename": filename,
            "content_base64": contentBase64,
            "source_brand": sourceBrand
        ]
        return try await request(path: "/api/sync/import-track-file", method: "POST", body: body, timeout: 90)
    }
    
    func fetchActivityTrack(actId: String) async throws -> ActivityTrackResponse {
        return try await request(path: "/api/miniapp/activities/\(actId)/track")
    }
    
    // MARK: - Full Profile & Organization
    
    func fetchFullProfile(uid: String) async throws -> FullProfileResponse {
        return try await request(path: "/api/profile/\(uid)")
    }
    
    func fetchUserOrgs(uid: String) async throws -> [UserOrgItem] {
        let res: UserOrgsResponse = try await request(path: "/api/org/my-orgs/\(uid)")
        return res.organizations ?? []
    }
    
    func updateProfile(uid: String, data: [String: Any]) async throws -> FullProfileResponse {
        return try await request(path: "/api/profile/\(uid)", method: "PUT", body: data)
    }
    
    func syncDeviceProfile(uid: String) async throws -> FullProfileResponse {
        return try await request(path: "/api/profile/\(uid)/sync-device-profile", method: "POST")
    }
    
    func importGarminPB(uid: String) async throws -> FullProfileResponse {
        return try await request(path: "/api/profile/\(uid)/import-garmin-pb", method: "POST")
    }
    
    func updateUserGoal(uid: String, targetDistance: Int, weeklyTarget: Int, monthlyTargets: [Int], year: Int = 2026) async throws -> UserGoalData? {
        struct UpdateGoalResponse: Codable {
            let message: String?
            let data: UserGoalData?
        }
        let body: [String: Any] = [
            "year": year,
            "period_type": "monthly",
            "target_distance": Double(targetDistance),
            "weekly_target": Double(weeklyTarget),
            "monthly_targets": monthlyTargets
        ]
        let res: UpdateGoalResponse = try await request(
            path: "/api/profile/\(uid)/goal",
            method: "PUT",
            body: body
        )
        return res.data
    }
    
    // MARK: - Race Plans Management
    
    func saveRacePlan(uid: String, raceData: [String: Any]) async throws -> [RaceItem] {
        struct SaveRaceResponse: Codable {
            let message: String?
            let id: String?
            let races: [RaceItem]?
        }
        let res: SaveRaceResponse = try await request(
            path: "/api/profile/\(uid)/races",
            method: "POST",
            body: raceData
        )
        return res.races ?? []
    }
    
    func deleteRacePlan(uid: String, raceId: String) async throws -> [RaceItem] {
        struct DeleteRaceResponse: Codable {
            let message: String?
            let races: [RaceItem]?
        }
        let encodedId = raceId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? raceId
        let res: DeleteRaceResponse = try await request(
            path: "/api/profile/\(uid)/races/\(encodedId)",
            method: "DELETE"
        )
        return res.races ?? []
    }
    
    func lookupRaceIntelligence(
        uid: String?,
        raceName: String,
        raceType: String?,
        targetTime: String?,
        raceDate: String?,
        raceId: String?
    ) async throws -> RaceIntelLookupResponse {
        var body: [String: Any] = ["race_name": raceName]
        if let uid = uid, !uid.isEmpty { body["user_id"] = uid }
        if let rt = raceType, !rt.isEmpty { body["race_type"] = rt }
        if let tt = targetTime, !tt.isEmpty { body["target_time"] = tt }
        if let rd = raceDate, !rd.isEmpty { body["race_date"] = rd }
        if let rid = raceId, !rid.isEmpty { body["race_id"] = rid }
        return try await request(
            path: "/api/profile/race-intel-lookup",
            method: "POST",
            body: body,
            timeout: 45
        )
    }
    
    func updateRaceInfo(uid: String, raceId: String, raceInfo: [String: Any]) async throws -> [RaceItem] {
        struct UpdateRaceInfoResponse: Codable {
            let message: String?
            let races: [RaceItem]?
        }
        let encodedId = raceId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? raceId
        let res: UpdateRaceInfoResponse = try await request(
            path: "/api/profile/\(uid)/races/\(encodedId)/info",
            method: "PATCH",
            body: ["race_info": raceInfo]
        )
        return res.races ?? []
    }
    
    func updateRacePriority(uid: String, raceId: String, priority: Int) async throws -> [RaceItem] {
        struct UpdatePriorityResponse: Codable {
            let message: String?
            let races: [RaceItem]?
        }
        let encodedId = raceId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? raceId
        let res: UpdatePriorityResponse = try await request(
            path: "/api/profile/\(uid)/races/\(encodedId)/priority",
            method: "POST",
            body: ["priority": priority]
        )
        return res.races ?? []
    }
    
    func fetchMatchedRaceActivity(uid: String, raceId: String, raceDate: String) async throws -> MatchedRaceActivityResponse {
        let encodedId = (raceId.isEmpty ? "temp" : raceId).addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? "temp"
        let encodedDate = raceDate.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? raceDate
        return try await request(
            path: "/api/profile/\(uid)/races/\(encodedId)/matched-activity?race_date=\(encodedDate)"
        )
    }
    
    func uploadRacePhotoBase64(uid: String, raceId: String, imageBase64: String, ext: String = ".jpg") async throws -> (photoUrl: String?, photos: [String], races: [RaceItem]?) {
        struct UploadPhotoResponse: Codable {
            let photo_url: String?
            let photos: [String]?
            let message: String?
            let races: [RaceItem]?
        }
        let encodedId = (raceId.isEmpty ? "race_\(Int(Date().timeIntervalSince1970))" : raceId).addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? raceId
        let res: UploadPhotoResponse = try await request(
            path: "/api/profile/\(uid)/races/\(encodedId)/photo-base64",
            method: "POST",
            body: ["image_base64": imageBase64, "ext": ext],
            timeout: 60
        )
        return (res.photo_url, res.photos ?? [], res.races)
    }
    
    func deleteRacePhoto(uid: String, raceId: String, photoUrl: String) async throws -> (photos: [String], races: [RaceItem]?) {
        struct DeletePhotoResponse: Codable {
            let message: String?
            let photos: [String]?
            let races: [RaceItem]?
        }
        let encodedId = raceId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? raceId
        let res: DeletePhotoResponse = try await request(
            path: "/api/profile/\(uid)/races/\(encodedId)/photo",
            method: "DELETE",
            body: ["photo_url": photoUrl]
        )
        return (res.photos ?? [], res.races)
    }
    
    // MARK: - Club Reports, Cockpit & Events
    
    func fetchClubPeriodicReport(clubId: String, operatorUid: String, periodType: String = "week", year: Int? = nil, periodIndex: Int? = nil) async throws -> ClubPeriodicReport {
        var queryItems = [
            "operator_uid=\(operatorUid)",
            "period_type=\(periodType)"
        ]
        if let y = year { queryItems.append("year=\(y)") }
        if let p = periodIndex { queryItems.append("period_index=\(p)") }
        let queryString = queryItems.joined(separator: "&")
        return try await request(path: "/api/team/\(clubId)/reports?\(queryString)")
    }
    
    func fetchCoachCockpit(clubId: String, operatorUid: String) async throws -> CoachCockpitData {
        return try await request(path: "/api/team/\(clubId)/coach-cockpit?operator_uid=\(operatorUid)")
    }
    
    func fetchClubEvents(clubId: String) async throws -> [ClubEvent] {
        let res: ClubEventsResponse = try await request(path: "/api/team/\(clubId)/events")
        return res.events ?? []
    }
    
    func createClubEvent(clubId: String, title: String, eventType: String, startDate: String, endDate: String, targetKm: Double, rules: String, operatorUid: String) async throws {
        let body: [String: Any] = [
            "operator_uid": operatorUid,
            "title": title,
            "event_type": eventType,
            "start_date": startDate,
            "end_date": endDate,
            "target_km": targetKm,
            "rules": rules
        ]
        struct EventCreateResponse: Codable {
            let message: String?
            let event_id: String?
        }
        let _: EventCreateResponse = try await request(path: "/api/team/\(clubId)/events", method: "POST", body: body)
    }
    
    func deleteClubEvent(clubId: String, eventId: String) async throws {
        struct DeleteEventResponse: Codable {
            let message: String?
        }
        let _: DeleteEventResponse = try await request(path: "/api/team/\(clubId)/events/\(eventId)", method: "DELETE")
    }
    
    func updateClubJoinRule(clubId: String, joinMode: String, inviteCode: String?, operatorUid: String) async throws {
        var body: [String: Any] = [
            "operator_uid": operatorUid,
            "join_mode": joinMode
        ]
        if let code = inviteCode { body["invite_code"] = code }
        struct JoinRuleResponse: Codable {
            let message: String?
        }
        let _: JoinRuleResponse = try await request(path: "/api/team/\(clubId)/join-rule", method: "PATCH", body: body)
    }
}

