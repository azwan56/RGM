import SwiftUI
import AuthenticationServices
import PhotosUI

enum ProfileActiveSheet: Identifiable {
    case deviceLogin(String)
    case manualHelp
    case editProfile
    
    var id: String {
        switch self {
        case .deviceLogin(let brand): return "deviceLogin_\(brand)"
        case .manualHelp: return "manualHelp"
        case .editProfile: return "editProfile"
        }
    }
}

struct ProfileView: View {
    @EnvironmentObject var state: AppState
    
    // Active Tab: "profile" vs "training"
    @State private var activeTab: String = "profile"
    
    // Obfuscation Eye Toggles
    @State private var showDob: Bool = false
    @State private var showRealName: Bool = false
    @State private var showPhone: Bool = false
    @State private var showIdCard: Bool = false
    
    // Form fields
    @State private var realName: String = ""
    @State private var phone: String = ""
    @State private var idCard: String = ""
    @State private var dob: String = ""
    @State private var gender: String = "male"
    
    // Biometrics & PBs
    @State private var vo2maxStr: String = "--"
    @State private var heightStr: String = "--"
    @State private var weightStr: String = "--"
    @State private var maxHrStr: String = "--"
    @State private var restHrStr: String = "--"
    @State private var yearsRunningStr: String = "--"
    
    @State private var marathonPbStr: String = "--"
    @State private var halfPbStr: String = "--"
    @State private var tenKPbStr: String = "--"
    @State private var fiveKPbStr: String = "--"
    
    // Mileage Goals
    @State private var targetDistance: Int = 200
    @State private var weeklyTarget: Int = 50
    @State private var monthlyTargets: [Int] = Array(repeating: 200, count: 12)
    
    // Modals
    @State private var activeSheet: ProfileActiveSheet? = nil
    @State private var selectedTrackActivity: ActivityItem? = nil
    @State private var toastMessage: String?
    @State private var showDeleteAccountAlert: Bool = false
    @State private var showCitationsSheet: Bool = false
    @State private var isDemoLoggingIn: Bool = false
    
    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            
            ScrollView {
                VStack(spacing: 16) {
                    // 1. User Header Card
                    profileCard
                        .padding(.top, 8)
                    
                    // 2. New User Manual Entry Banner
                    manualEntryBanner
                    
                    // 3. Dual Tab Switcher: 个人资料与账号 vs 训练档案与赛事
                    tabsNav
                    
                    // 4. Tab 1 or Tab 2 Content
                    if activeTab == "profile" {
                        profileTabContent
                    } else {
                        trainingTabContent
                    }
                    
                    // 5. Account Actions (Logout & Delete Account per Guideline 5.1.1(v))
                    if state.isLoggedIn {
                        VStack(spacing: 10) {
                            Button(action: {
                                state.logout()
                                syncFromState()
                                toastMessage = "已退出当前登录"
                            }) {
                                Text("退出登录")
                                    .font(.system(size: 14, weight: .bold))
                                    .foregroundColor(.orange)
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 13)
                                    .background(Theme.surface)
                                    .cornerRadius(12)
                                    .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
                            }
                            
                            Button(role: .destructive, action: {
                                showDeleteAccountAlert = true
                            }) {
                                HStack(spacing: 6) {
                                    Image(systemName: "trash.fill")
                                    Text("注销账号与删除全部数据 (Delete Account)")
                                }
                                .font(.system(size: 13, weight: .bold))
                                .foregroundColor(Color(hex: "F43F5E"))
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 13)
                                .background(Color(hex: "F43F5E").opacity(0.1))
                                .cornerRadius(12)
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color(hex: "F43F5E").opacity(0.3), lineWidth: 1))
                            }
                        }
                        .padding(.top, 8)
                    } else {
                        // Logged-out state with Demo Login for Reviewers & Users
                        VStack(spacing: 12) {
                            HStack(spacing: 8) {
                                Image(systemName: "person.crop.circle.badge.xmark")
                                    .foregroundColor(Theme.textMuted)
                                Text("当前未登录或账号已注销")
                                    .font(.system(size: 13, weight: .medium))
                                    .foregroundColor(Theme.textSecondary)
                            }
                            .padding(.top, 4)
                            
                            // Sign In with Apple (Native iOS)
                            SignInWithAppleButton(
                                onRequest: { request in
                                    request.requestedScopes = [.fullName, .email]
                                },
                                onCompletion: { result in
                                    switch result {
                                    case .success(let authResults):
                                        switch authResults.credential {
                                        case let appleIDCredential as ASAuthorizationAppleIDCredential:
                                            let userIdentifier = appleIDCredential.user
                                            let givenName = appleIDCredential.fullName?.givenName ?? ""
                                            let familyName = appleIDCredential.fullName?.familyName ?? ""
                                            let fullName = (familyName + givenName).trimmingCharacters(in: .whitespacesAndNewlines)
                                            let email = appleIDCredential.email
                                            let identityToken = appleIDCredential.identityToken.flatMap { String(data: $0, encoding: .utf8) }
                                            Task {
                                                do {
                                                    try await state.loginWithApple(
                                                        userId: userIdentifier,
                                                        identityToken: identityToken,
                                                        email: email,
                                                        fullName: fullName.isEmpty ? nil : fullName
                                                    )
                                                    syncFromState()
                                                    showToast("Apple 账号登录成功 ✓")
                                                } catch {
                                                    showToast("登录失败：\(error.localizedDescription)")
                                                }
                                            }
                                        default:
                                            showToast("登录失败：未获取到 Apple ID 凭证")
                                        }
                                    case .failure(let error):
                                        if let authError = error as? ASAuthorizationError, authError.code == .canceled {
                                            return
                                        }
                                        print("[ProfileView] Apple sign in failed: \(error)")
                                        showToast("Apple 登录失败：\(error.localizedDescription)")
                                    }
                                }
                            )
                            .signInWithAppleButtonStyle(Theme.isLight ? .black : .white)
                            .frame(height: 48)
                            .cornerRadius(12)
                            
                            Button(action: {
                                activeSheet = .deviceLogin("garmin")
                            }) {
                                HStack(spacing: 6) {
                                    Image(systemName: "applewatch.radiowaves.left.and.right")
                                    Text("使用佳明 Garmin / 高驰 COROS 账号登录")
                                }
                                .font(.system(size: 13, weight: .bold))
                                .foregroundColor(Theme.textPrimary)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Theme.surfaceSecondary)
                                .cornerRadius(12)
                                .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.primaryOrange.opacity(0.4), lineWidth: 1))
                            }
                            
                            Button(action: {
                                guard !isDemoLoggingIn else { return }
                                isDemoLoggingIn = true
                                Task {
                                    defer { isDemoLoggingIn = false }
                                    do {
                                        try await state.loginDemoAccount()
                                        syncFromState()
                                        showToast("已使用演示账号登录（数据均为模拟）")
                                    } catch {
                                        showToast("演示账号登录失败：\(error.localizedDescription)")
                                    }
                                }
                            }) {
                                HStack(spacing: 6) {
                                    if isDemoLoggingIn {
                                        ProgressView().tint(Theme.onBrand)
                                    } else {
                                        Image(systemName: "person.badge.shield.checkmark.fill")
                                    }
                                    Text("使用演示账号体验登录 (Sign in Demo Account)")
                                }
                                .font(.system(size: 13, weight: .bold))
                                .foregroundColor(Theme.onBrand)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                                .background(Theme.brandFill)
                                .cornerRadius(12)
                            }
                        }
                        .padding(16)
                        .background(Theme.surface)
                        .cornerRadius(12)
                        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
                        .padding(.top, 8)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 110)
            }
            .refreshable {
                await state.refreshData()
                syncFromState()
            }
            
            // Toast notification
            if let toast = toastMessage {
                VStack {
                    Spacer()
                    HStack(spacing: 8) {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(Theme.accentGreen)
                        Text(toast)
                            .font(.system(size: 13, weight: .semibold))
                            .foregroundColor(.white)
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color.black.opacity(0.85))
                    .cornerRadius(20)
                    .overlay(RoundedRectangle(cornerRadius: 20).stroke(Theme.border, lineWidth: 1))
                    .padding(.bottom, 100)
                }
                .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .sheet(item: $activeSheet) { item in
            switch item {
            case .deviceLogin(let brand):
                DeviceLoginSheet(initialBrand: brand, onSuccess: { msg in
                    syncFromState()
                    showToast(msg)
                })
                .environmentObject(state)
            case .manualHelp:
                ManualHelpSheet()
            case .editProfile:
                EditProfileSheet(onSaved: {
                    withAnimation {
                        toastMessage = "个人资料修改已保存 ✓"
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
                        withAnimation {
                            toastMessage = nil
                        }
                    }
                })
                .environmentObject(state)
            }
        }
        .sheet(isPresented: $showCitationsSheet) {
            ScientificCitationsSheet()
        }
        .sheet(item: $selectedTrackActivity) { act in
            GpsTrackSheet(activity: act)
        }
        .alert(isPresented: $showDeleteAccountAlert) {
            Alert(
                title: Text("注销并永久删除账号"),
                message: Text("确定要注销并永久删除此账号吗？\n\n此操作将彻底删除您的个人资料、跑步活动记录及所有云端数据，且不可撤销恢复。"),
                primaryButton: .destructive(Text("确认注销")) {
                    Task {
                        await state.deleteAccount()
                        syncFromState()
                        toastMessage = "账号及全部数据已成功永久注销"
                    }
                },
                secondaryButton: .cancel(Text("取消"))
            )
        }
        .onAppear {
            syncFromState()
        }
        .onChange(of: state.fullProfile?.id) { _ in
            syncFromState()
        }
        .onChange(of: state.userGoal) { _ in
            syncFromState()
        }
    }
    
    // MARK: - Synchronize Form with AppState
    private func syncFromState() {
        // Always overwrite every field so data from a previous account never lingers.
        let p = state.fullProfile
        
        realName = p?.real_name ?? ""
        phone = p?.phone ?? ""
        idCard = p?.id_card ?? ""
        dob = p?.date_of_birth ?? ""
        gender = (p?.gender?.isEmpty == false) ? p!.gender! : "male"
        
        vo2maxStr = p?.vo2max.map { String(format: "%.1f", $0) } ?? "--"
        heightStr = p?.height_cm.map { "\(Int($0))" } ?? "--"
        weightStr = p?.weight_kg.map { "\(Int($0))" } ?? "--"
        maxHrStr = p?.max_heart_rate.map { "\($0)" } ?? "--"
        restHrStr = p?.resting_heart_rate.map { "\($0)" } ?? "--"
        yearsRunningStr = p?.years_running.map { "\($0)" } ?? "--"
        
        marathonPbStr = p?.marathon_pb.map { formatPb($0) } ?? "--"
        halfPbStr = p?.half_pb.map { formatPb($0) } ?? "--"
        tenKPbStr = p?.ten_k_pb.map { formatPb($0) } ?? "--"
        fiveKPbStr = p?.five_k_pb.map { formatPb($0) } ?? "--"
        
        if let g = state.userGoal {
            let baseMonth = Int((g.target_distance ?? state.dashboard.monthTarget).rounded())
            targetDistance = baseMonth > 0 ? baseMonth : 200
            let baseWeek = Int((g.weekly_target ?? state.dashboard.weeklyProgress?.target_week_km ?? Double(targetDistance) / 4.0).rounded())
            weeklyTarget = baseWeek > 0 ? baseWeek : 50
            monthlyTargets = g.monthlyTargetsInt
        } else {
            let baseMonth = Int(state.dashboard.monthTarget.rounded())
            targetDistance = baseMonth > 0 ? baseMonth : 200
            let baseWeek = Int((state.dashboard.weeklyProgress?.target_week_km ?? 50.0).rounded())
            weeklyTarget = baseWeek > 0 ? baseWeek : 50
            monthlyTargets = Array(repeating: targetDistance, count: 12)
        }
    }
    
    private func formatPb(_ seconds: Int) -> String {
        let h = seconds / 3600
        let m = (seconds % 3600) / 60
        let s = seconds % 60
        if h > 0 {
            return String(format: "%d:%02d:%02d", h, m, s)
        } else {
            return String(format: "%02d:%02d", m, s)
        }
    }
    
    // MARK: - 1. Profile Header Card
    private var profileCard: some View {
        Button(action: {
            activeSheet = .editProfile
        }) {
            HStack(spacing: 14) {
                ZStack(alignment: .bottomTrailing) {
                    if let avatar = state.fullProfile?.avatar_url ?? state.currentUser?.avatar_url, let url = URL(string: avatar) {
                        AsyncImage(url: url) { phase in
                            switch phase {
                            case .success(let img):
                                img.resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: 58, height: 58)
                                    .clipShape(Circle())
                            default:
                                defaultAvatar
                            }
                        }
                    } else {
                        defaultAvatar
                    }
                    
                    Circle()
                        .fill(Theme.primaryOrange)
                        .frame(width: 20, height: 20)
                        .overlay(Text("📷").font(.system(size: 10)))
                }
                
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 8) {
                        Text(state.fullProfile?.display_name ?? state.currentUser?.displayName ?? "跑者")
                            .font(.system(size: 18, weight: .bold))
                            .foregroundColor(Theme.textPrimary)
                        
                        Text("✏️ 修改资料")
                            .font(.system(size: 10, weight: .medium))
                            .foregroundColor(Theme.primaryOrange)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Theme.primaryOrange.opacity(0.12))
                            .cornerRadius(6)
                    }
                    
                    if let uid = state.currentUser?.id {
                        Text("ID: \(uid) · 点击修改昵称与头像 ›")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundColor(Theme.textMuted)
                    } else {
                        Text("登录后开启独立跑步档案与数据管理")
                            .font(.system(size: 11))
                            .foregroundColor(Theme.textMuted)
                    }
                }
                Spacer()
            }
            .padding(16)
            .background(Theme.surface)
            .cornerRadius(16)
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(Theme.border, lineWidth: 1))
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    private var defaultAvatar: some View {
        ZStack {
            Circle()
                .fill(Theme.surfaceSecondary)
                .frame(width: 58, height: 58)
            Text("🏃").font(.system(size: 26))
        }
    }
    
    // MARK: - 2. Manual Entry Banner
    private var manualEntryBanner: some View {
        Button(action: {
            activeSheet = .manualHelp
        }) {
            HStack(spacing: 12) {
                Text("📖").font(.system(size: 22))
                VStack(alignment: .leading, spacing: 2) {
                    Text("新用户入门与操作手册")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text("Apple 健康直读 · 隐私本地存储 · Canova AI 教练")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Theme.textMuted)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .background(LinearGradient(colors: [Theme.isLight ? Theme.surfaceSecondary : Color(hex: "231F1C"), Theme.surface], startPoint: .leading, endPoint: .trailing))
            .cornerRadius(12)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    // MARK: - 3. Tabs Navigation
    private var tabsNav: some View {
        HStack(spacing: 10) {
            tabNavButton(id: "profile", title: "手表连接与账号", icon: "⌚")
            tabNavButton(id: "training", title: "训练档案与赛事", icon: "🏃")
        }
    }
    
    private func tabNavButton(id: String, title: String, icon: String) -> some View {
        let isSel = activeTab == id
        return Button(action: {
            withAnimation(.easeInOut(duration: 0.15)) {
                activeTab = id
            }
        }) {
            HStack(spacing: 6) {
                Text(icon).font(.system(size: 13))
                Text(title).font(.system(size: 13, weight: isSel ? .bold : .medium))
            }
            .foregroundColor(isSel ? (Theme.isLight ? Theme.textPrimary : Theme.primaryOrange) : Theme.textMuted)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 11)
            .background(isSel ? Theme.surface : Theme.surfaceSecondary.opacity(0.5))
            .cornerRadius(10)
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isSel ? Theme.primaryOrange.opacity(0.45) : Theme.border, lineWidth: 1)
            )
        }
    }
    
    // ══════════════════════════════════════════════════════════════
    // TAB 1: 手表连接与账号
    // ══════════════════════════════════════════════════════════════
    private var profileTabContent: some View {
        VStack(spacing: 16) {
            WatchDirectSyncCardView(
                onTapDeviceLogin: { brand in
                    activeSheet = .deviceLogin(brand)
                },
                onShowToast: { msg in
                    syncFromState()
                    showToast(msg)
                }
            )
            
            MorningBriefingSettingsCard()
            
            LocalDataPrivacyCardView(onClearData: {
                StorageManager.shared.clear()
                showToast("已清除本地运动数据缓存")
            })
        }
    }
    
    // ══════════════════════════════════════════════════════════════
    // TAB 2: 训练档案与赛事
    // ══════════════════════════════════════════════════════════════
    private var trainingTabContent: some View {
        VStack(spacing: 16) {
            PbSectionCardView(
                marathonPb: marathonPbStr,
                halfPb: halfPbStr,
                tenKPb: tenKPbStr,
                fiveKPb: fiveKPbStr,
                onImportGarmin: {
                    Task {
                        await state.importGarminPB()
                        syncFromState()
                        showToast("已成功从 Garmin 导入最新 PB 记录！")
                    }
                }
            )
            BiometricsSectionCardView(
                vo2max: vo2maxStr,
                restHr: restHrStr,
                maxHr: maxHrStr,
                yearsRunning: yearsRunningStr,
                height: heightStr,
                weight: weightStr,
                onSyncWatches: {
                    Task {
                        await state.syncDeviceBiometrics()
                        syncFromState()
                        showToast("已成功从运动手表同步生理指标！")
                    }
                }
            )
            MileageGoalCardView(
                targetDistance: $targetDistance,
                weeklyTarget: $weeklyTarget,
                monthlyTargets: $monthlyTargets
            )
            saveTrainingButton
            RacePlansCardView(
                races: state.userRaces,
                onToast: { msg in
                    showToast(msg)
                }
            )
            monthlyWorkoutsSection
        }
    }
    
    private var saveTrainingButton: some View {
        Button(action: {
            Task {
                do {
                    try await state.saveUserGoal(
                        targetDistance: targetDistance,
                        weeklyTarget: weeklyTarget,
                        monthlyTargets: monthlyTargets
                    )
                    showToast("训练目标与月度跑量计划已保存 ✓")
                } catch {
                    showToast("保存失败: \(error.localizedDescription)")
                }
            }
        }) {
            HStack {
                if state.isSavingProfile {
                    ProgressView()
                        .tint(Theme.onBrand)
                        .scaleEffect(0.85)
                } else {
                    Text("🎯")
                }
                Text(state.isSavingProfile ? "正在保存训练目标..." : "保存训练目标与生理参数")
                    .font(.system(size: 14, weight: .bold))
            }
            .foregroundColor(Theme.onBrand)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                LinearGradient(
                    colors: [Theme.brandFill, Theme.brandGradientEnd],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .cornerRadius(12)
        }
        .disabled(state.isSavingProfile)
    }
    
    private func showToast(_ msg: String) {
        withAnimation { toastMessage = msg }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
            withAnimation { toastMessage = nil }
        }
    }
    
    // MARK: - Monthly Workouts Section (当月运动记录)
    private var monthlyWorkoutsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                HStack(spacing: 6) {
                    Text("当月运动记录")
                        .font(.system(size: 16, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Text("当月")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Theme.brandTint)
                        .cornerRadius(4)
                }
                Spacer()
                Text("共 \(state.dashboard.runCount) 次打卡 · \(String(format: "%.1f", state.dashboard.monthMileage)) km")
                    .font(.system(size: 11))
                    .foregroundColor(Theme.textMuted)
            }
            
            if state.dashboard.recentActivities.isEmpty {
                emptyWorkoutsView
            } else {
                ForEach(state.dashboard.recentActivities) { act in
                    ActivityRowView(activity: act, onTapTrack: {
                        selectedTrackActivity = act
                    })
                }
            }
        }
    }
    
    private var emptyWorkoutsView: some View {
        VStack(spacing: 8) {
            Image(systemName: "figure.run.circle")
                .font(.system(size: 36))
                .foregroundColor(Theme.textMuted)
            Text("暂无跑步活动，点击上方手表连接同步最新记录")
                .font(.system(size: 13))
                .foregroundColor(Theme.textMuted)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 30)
        .background(Theme.surface)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
    }
}

// ════════════════════════════════════════════════════════════════════
// REUSABLE SUB-VIEWS & CARDS (Modular, Fast Compile)
// ════════════════════════════════════════════════════════════════════

struct SelectableChip: View {
    let text: String
    let isSelected: Bool
    let activeColor: Color
    let action: () -> Void
    
    init(_ text: String, isSelected: Bool, activeColor: Color = Theme.brandFill, action: @escaping () -> Void) {
        self.text = text
        self.isSelected = isSelected
        self.activeColor = activeColor
        self.action = action
    }
    
    var body: some View {
        Button(action: action) {
            Text(text)
                .font(.system(size: 11, weight: isSelected ? .bold : .regular))
                .foregroundColor(isSelected ? Theme.onBrand : Theme.textSecondary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(isSelected ? activeColor : Theme.surfaceSecondary)
                .cornerRadius(6)
        }
    }
}

struct WeeklyChip: View {
    let km: Int
    let isSelected: Bool
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            Text("\(km)k")
                .font(.system(size: 11, weight: isSelected ? .bold : .regular))
                .foregroundColor(isSelected ? .white : Theme.textSecondary)
                .padding(.horizontal, 8)
                .padding(.vertical, 5)
                .background(isSelected ? Theme.accentGreen : Theme.surfaceSecondary)
                .cornerRadius(6)
        }
    }
}
// MARK: - Sensitive Personal Info Card View
struct SensitivePersonalInfoCardView: View {
    @Binding var showDob: Bool
    @Binding var showRealName: Bool
    @Binding var showPhone: Bool
    @Binding var showIdCard: Bool
    @Binding var realName: String
    @Binding var phone: String
    @Binding var idCard: String
    @Binding var dob: String
    @Binding var gender: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                HStack(spacing: 6) {
                    Text("🔒").font(.system(size: 14))
                    Text("个人生理档案与基本信息")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                }
                Spacer()
                Text("AES-256 加密保护")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(Theme.accentGreen)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(Theme.accentGreen.opacity(0.15))
                    .cornerRadius(6)
            }
            
            Text("生理性别、出生日期与身体参数用于 Canova AI 模型测算个性化储备心率区间 (Karvonen) 与最大摄氧量 (VO2max) 跑力。")
                .font(.system(size: 11))
                .foregroundColor(Theme.textMuted)
                .lineSpacing(3)
            
            // DOB
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("出生日期 (Date of Birth) *")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.textPrimary)
                    Text("必填项")
                        .font(.system(size: 9))
                        .foregroundColor(Theme.primaryOrange)
                    Text("🔒 AES-256 加密")
                        .font(.system(size: 9))
                        .foregroundColor(Theme.accentGreen)
                    Spacer()
                    Text("56 岁 · 1970年 · 大师组")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(Theme.primaryOrange)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Theme.primaryOrange.opacity(0.12))
                        .cornerRadius(6)
                }
                
                HStack {
                    Text(showDob ? dob : (dob.isEmpty ? "请选择出生年月日" : "****-**-**"))
                        .font(.system(size: 13, design: .monospaced))
                        .foregroundColor(Theme.textPrimary)
                    Spacer()
                    Button(action: { showDob.toggle() }) {
                        Text(showDob ? "👁️" : "🙈").font(.system(size: 14))
                    }
                }
                .padding(10)
                .background(Theme.surfaceSecondary)
                .cornerRadius(8)
            }
            
            // Real Name
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("真实姓名 *").font(.system(size: 11, weight: .semibold)).foregroundColor(Theme.textPrimary)
                    Text("必填项").font(.system(size: 9)).foregroundColor(Theme.primaryOrange)
                    Text("🔒 加密存储").font(.system(size: 9)).foregroundColor(Theme.accentGreen)
                }
                
                HStack {
                    if showRealName {
                        TextField("跑者姓名 / 昵称", text: $realName)
                            .font(.system(size: 13))
                            .foregroundColor(Theme.textPrimary)
                    } else {
                        SecureField("跑者姓名 / 昵称", text: $realName)
                            .font(.system(size: 13))
                            .foregroundColor(Theme.textPrimary)
                    }
                    Button(action: { showRealName.toggle() }) {
                        Text(showRealName ? "👁️" : "🙈").font(.system(size: 14))
                    }
                }
                .padding(10)
                .background(Theme.surfaceSecondary)
                .cornerRadius(8)
            }
            
            // Phone
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("联系手机").font(.system(size: 11, weight: .semibold)).foregroundColor(Theme.textPrimary)
                    Text("🔒 保密").font(.system(size: 9)).foregroundColor(Theme.textMuted)
                }
                
                HStack {
                    if showPhone {
                        TextField("紧急联络手机", text: $phone)
                            .font(.system(size: 13, design: .monospaced))
                            .foregroundColor(Theme.textPrimary)
                    } else {
                        SecureField("紧急联络手机", text: $phone)
                            .font(.system(size: 13, design: .monospaced))
                            .foregroundColor(Theme.textPrimary)
                    }
                    Button(action: { showPhone.toggle() }) {
                        Text(showPhone ? "👁️" : "🙈").font(.system(size: 14))
                    }
                }
                .padding(10)
                .background(Theme.surfaceSecondary)
                .cornerRadius(8)
            }
            
            // ID Card
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("身份证号码 / 证件号 (选填)").font(.system(size: 11, weight: .semibold)).foregroundColor(Theme.textPrimary)
                    Text("🔒 密文存储").font(.system(size: 9)).foregroundColor(Theme.textMuted)
                }
                
                HStack {
                    if showIdCard {
                        TextField("身份证号 / 证件号 (选填)", text: $idCard)
                            .font(.system(size: 13, design: .monospaced))
                            .foregroundColor(Theme.textPrimary)
                    } else {
                        SecureField("身份证号 / 证件号 (选填)", text: $idCard)
                            .font(.system(size: 13, design: .monospaced))
                            .foregroundColor(Theme.textPrimary)
                    }
                    Button(action: { showIdCard.toggle() }) {
                        Text(showIdCard ? "👁️" : "🙈").font(.system(size: 14))
                    }
                }
                .padding(10)
                .background(Theme.surfaceSecondary)
                .cornerRadius(8)
            }
            
            // Gender
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("生理性别 *").font(.system(size: 11, weight: .semibold)).foregroundColor(Theme.textPrimary)
                    Text("必填项").font(.system(size: 9)).foregroundColor(Theme.primaryOrange)
                }
                
                HStack(spacing: 12) {
                    SelectableChip("♂ 男 (Male)", isSelected: gender == "male") {
                        gender = "male"
                    }
                    SelectableChip("♀ 女 (Female)", isSelected: gender == "female") {
                        gender = "female"
                    }
                }
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
}
// MARK: - Watch Direct Sync Card View (Garmin / COROS / Apple Watch)
struct WatchDirectSyncCardView: View {
    @EnvironmentObject var state: AppState
    @State private var isUnbindingGarmin: Bool = false
    @State private var isUnbindingCoros: Bool = false
    @State private var isUnbindingAppleWatch: Bool = false
    let onTapDeviceLogin: (String) -> Void
    let onShowToast: (String) -> Void
    
    private var isGarminConnected: Bool {
        state.fullProfile?.garmin_connected ?? state.currentUser?.garmin_connected ?? false
    }
    
    private var garminEmail: String {
        state.fullProfile?.garmin_email ?? state.currentUser?.garmin_email ?? ""
    }
    
    private var garminDomainLabel: String {
        let dom = state.fullProfile?.garmin_domain ?? state.currentUser?.garmin_domain ?? "garmin.cn"
        return dom == "garmin.com" ? "国际区 garmin.com" : "中国区 garmin.cn"
    }
    
    private var isCorosConnected: Bool {
        state.fullProfile?.coros_connected ?? state.currentUser?.coros_connected ?? false
    }
    
    private var corosAccount: String {
        state.fullProfile?.coros_account ?? state.currentUser?.coros_account ?? ""
    }
    
    private var corosDomainLabel: String {
        let dom = state.fullProfile?.coros_domain ?? state.currentUser?.coros_domain ?? "teamcnapi.coros.com"
        return dom.contains("teamcnapi") ? "中国区 coros.com" : "国际区 coros.com"
    }
    
    private var isAppleWatchConnected: Bool {
        state.fullProfile?.apple_watch_connected ?? state.currentUser?.apple_watch_connected ?? false
    }
    
    private var connectedWatch: (id: String, label: String)? {
        state.connectedWatchBrand()
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                HStack(spacing: 6) {
                    Text("⌚").font(.system(size: 15))
                    Text("运动手表连接与数据同步")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                }
                Spacer()
                Text("单账号单手表直连")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(Theme.primaryOrange)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Theme.primaryOrange.opacity(0.12))
                    .cornerRadius(4)
            }
            
            // Cloud Sync & Exclusivity Notice
            HStack(alignment: .top, spacing: 6) {
                Image(systemName: "shield.checkered")
                    .foregroundColor(Theme.primaryOrange)
                    .font(.system(size: 12))
                Text("每个账号仅连接一个运动手表，避免多渠道重复导入跑步记录。如需切换其他品牌手表，请先点击当前手表的「解绑」按钮。")
                    .font(.system(size: 11))
                    .foregroundColor(Theme.textMuted)
                    .lineSpacing(2)
            }
            .padding(10)
            .background(Theme.surfaceSecondary.opacity(0.4))
            .cornerRadius(8)
            
            // 1. Garmin Section
            let otherForGarmin = (connectedWatch != nil && connectedWatch?.id != "garmin") ? connectedWatch : nil
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    HStack(spacing: 6) {
                        Text("Garmin")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color(hex: "007AC3"))
                            .cornerRadius(4)
                        Text("佳明 Garmin Connect 云端直连")
                            .font(.system(size: 13, weight: .bold))
                            .foregroundColor(Theme.textPrimary)
                    }
                    Spacer()
                    Text(isGarminConnected ? "已连接云端 ✓" : (otherForGarmin != nil ? "已绑定其他手表" : "未连接"))
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(isGarminConnected ? Theme.accentGreen : Theme.textMuted)
                }
                
                if isGarminConnected && !garminEmail.isEmpty {
                    Text("已绑定：\(garminEmail) (\(garminDomainLabel))")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textSecondary)
                } else {
                    Text("支持中国区 (garmin.cn) 与国际区 (garmin.com) 账号及邮箱两步验证。")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                }
                
                HStack(spacing: 8) {
                    if let other = otherForGarmin {
                        Button(action: {
                            onShowToast("每个账号仅限连接一个运动手表，请先解绑【\(other.label)】")
                        }) {
                            Text("已连接\(other.label)（解绑后可切换）")
                                .font(.system(size: 11, weight: .medium))
                                .foregroundColor(Theme.textMuted)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 7)
                                .background(Theme.surfaceSecondary)
                                .cornerRadius(6)
                        }
                    } else {
                        Button(action: {
                            onTapDeviceLogin("garmin")
                        }) {
                            Text(isGarminConnected ? "重新授权 / 改密" : "绑定佳明 Garmin 账号")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundColor(isGarminConnected ? Theme.textPrimary : .white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 7)
                                .background(isGarminConnected ? Theme.surfaceSecondary : Color(hex: "007AC3"))
                                .cornerRadius(6)
                        }
                    }
                    
                    if isGarminConnected {
                        Button(action: {
                            guard !isUnbindingGarmin else { return }
                            isUnbindingGarmin = true
                            Task {
                                defer { isUnbindingGarmin = false }
                                do {
                                    _ = try await state.unbindWatch(brand: "garmin")
                                    onShowToast("已解绑 Garmin 账号")
                                } catch {
                                    onShowToast("解绑失败：\(error.localizedDescription)")
                                }
                            }
                        }) {
                            Text(isUnbindingGarmin ? "解绑中..." : "解绑")
                                .font(.system(size: 11, weight: .medium))
                                .foregroundColor(Color(hex: "F43F5E"))
                                .padding(.horizontal, 10)
                                .padding(.vertical, 7)
                                .background(Color(hex: "F43F5E").opacity(0.12))
                                .cornerRadius(6)
                        }
                    }
                }
            }
            .padding(12)
            .background(Theme.surfaceSecondary.opacity(0.5))
            .cornerRadius(10)
            .opacity(otherForGarmin != nil ? 0.62 : 1.0)
            
            // 2. COROS Section
            let otherForCoros = (connectedWatch != nil && connectedWatch?.id != "coros") ? connectedWatch : nil
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    HStack(spacing: 6) {
                        Text("COROS")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color(hex: "E60012"))
                            .cornerRadius(4)
                        Text("高驰 COROS 官方云端直连")
                            .font(.system(size: 13, weight: .bold))
                            .foregroundColor(Theme.textPrimary)
                    }
                    Spacer()
                    Text(isCorosConnected ? "已连接云端 ✓" : (otherForCoros != nil ? "已绑定其他手表" : "未连接"))
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(isCorosConnected ? Theme.accentGreen : Theme.textMuted)
                }
                
                if isCorosConnected && !corosAccount.isEmpty {
                    Text("已绑定：\(corosAccount) (\(corosDomainLabel))")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textSecondary)
                } else {
                    Text("自动通过高驰 Training Hub 云端接口同步跑步记录与训练负荷。")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                }
                
                HStack(spacing: 8) {
                    if let other = otherForCoros {
                        Button(action: {
                            onShowToast("每个账号仅限连接一个运动手表，请先解绑【\(other.label)】")
                        }) {
                            Text("已连接\(other.label)（解绑后可切换）")
                                .font(.system(size: 11, weight: .medium))
                                .foregroundColor(Theme.textMuted)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 7)
                                .background(Theme.surfaceSecondary)
                                .cornerRadius(6)
                        }
                    } else {
                        Button(action: {
                            onTapDeviceLogin("coros")
                        }) {
                            Text(isCorosConnected ? "重新授权 / 改密" : "绑定高驰 COROS 账号")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundColor(isCorosConnected ? Theme.textPrimary : .white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 7)
                                .background(isCorosConnected ? Theme.surfaceSecondary : Color(hex: "E60012"))
                                .cornerRadius(6)
                        }
                    }
                    
                    if isCorosConnected {
                        Button(action: {
                            guard !isUnbindingCoros else { return }
                            isUnbindingCoros = true
                            Task {
                                defer { isUnbindingCoros = false }
                                do {
                                    _ = try await state.unbindWatch(brand: "coros")
                                    onShowToast("已解绑 COROS 账号")
                                } catch {
                                    onShowToast("解绑失败：\(error.localizedDescription)")
                                }
                            }
                        }) {
                            Text(isUnbindingCoros ? "解绑中..." : "解绑")
                                .font(.system(size: 11, weight: .medium))
                                .foregroundColor(Color(hex: "F43F5E"))
                                .padding(.horizontal, 10)
                                .padding(.vertical, 7)
                                .background(Color(hex: "F43F5E").opacity(0.12))
                                .cornerRadius(6)
                        }
                    }
                }
            }
            .padding(12)
            .background(Theme.surfaceSecondary.opacity(0.5))
            .cornerRadius(10)
            .opacity(otherForCoros != nil ? 0.62 : 1.0)
            
            // 3. Apple Watch Section
            let otherForAW = (connectedWatch != nil && connectedWatch?.id != "apple_watch") ? connectedWatch : nil
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    HStack(spacing: 6) {
                        Text("Apple Watch")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Theme.accentGreen)
                            .cornerRadius(4)
                        Text("苹果手表 HealthKit 原生直连")
                            .font(.system(size: 13, weight: .bold))
                            .foregroundColor(Theme.textPrimary)
                    }
                    Spacer()
                    Text(isAppleWatchConnected ? "已连接直读 ✓" : (otherForAW != nil ? "已绑定其他手表" : "未连接"))
                        .font(.system(size: 11, weight: .bold))
                        .foregroundColor(isAppleWatchConnected ? Theme.accentGreen : Theme.textMuted)
                }
                
                Text(isAppleWatchConnected
                     ? "已开启 Apple Watch 体能训练直读（自动同步完整 GPS 轨迹、心率、步频与 HRV/睡眠）。"
                     : "直接从 iPhone 健康读取 Apple Watch 跑步记录（含完整 GPS 轨迹、步频、心率与最大摄氧量）。")
                    .font(.system(size: 11))
                    .foregroundColor(isAppleWatchConnected ? Theme.textSecondary : Theme.textMuted)
                
                HStack(spacing: 8) {
                    if let other = otherForAW {
                        Button(action: {
                            onShowToast("每个账号仅限连接一个运动手表，请先解绑【\(other.label)】")
                        }) {
                            Text("已连接\(other.label)（解绑后可切换）")
                                .font(.system(size: 11, weight: .medium))
                                .foregroundColor(Theme.textMuted)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 7)
                                .background(Theme.surfaceSecondary)
                                .cornerRadius(6)
                        }
                    } else {
                        Button(action: {
                            Task {
                                let ok = await state.syncHealthKit(watchBrand: "apple_watch")
                                let notice = (state.syncNotice ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                                if ok {
                                    onShowToast(notice.isEmpty ? "Apple Watch 已连接并同步成功 ✓" : notice)
                                } else if !notice.isEmpty {
                                    onShowToast(notice)
                                } else {
                                    onTapDeviceLogin("apple_watch")
                                }
                            }
                        }) {
                            Text(isAppleWatchConnected ? "立即同步 Apple Watch" : "一键连接 Apple Watch")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundColor(isAppleWatchConnected ? Theme.textPrimary : .white)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 7)
                                .background(isAppleWatchConnected ? Theme.surfaceSecondary : Theme.accentGreen)
                                .cornerRadius(6)
                        }
                    }
                    
                    if isAppleWatchConnected {
                        Button(action: {
                            guard !isUnbindingAppleWatch else { return }
                            isUnbindingAppleWatch = true
                            Task {
                                defer { isUnbindingAppleWatch = false }
                                do {
                                    let msg = try await state.unbindWatch(brand: "apple_watch")
                                    onShowToast(msg)
                                } catch {
                                    onShowToast("解绑失败：\(error.localizedDescription)")
                                }
                            }
                        }) {
                            Text(isUnbindingAppleWatch ? "解绑中..." : "解绑")
                                .font(.system(size: 11, weight: .medium))
                                .foregroundColor(Color(hex: "F43F5E"))
                                .padding(.horizontal, 10)
                                .padding(.vertical, 7)
                                .background(Color(hex: "F43F5E").opacity(0.12))
                                .cornerRadius(6)
                        }
                    }
                }
            }
            .padding(12)
            .background(Theme.surfaceSecondary.opacity(0.5))
            .cornerRadius(10)
            .opacity(otherForAW != nil ? 0.62 : 1.0)
            
            // Unified Sync Action Button when any watch is connected
            if isGarminConnected || isCorosConnected || isAppleWatchConnected {
                if let notice = state.syncNotice, !notice.isEmpty {
                    HStack(spacing: 6) {
                        Image(systemName: "info.circle.fill")
                            .font(.system(size: 11))
                            .foregroundColor(Theme.accentGreen)
                        Text(notice)
                            .font(.system(size: 11, weight: .medium))
                            .foregroundColor(Theme.textSecondary)
                    }
                    .padding(.horizontal, 4)
                }
                
                Button(action: {
                    guard !state.isSyncing else { return }
                    Task {
                        if isGarminConnected || isCorosConnected {
                            await state.syncWatches()
                        } else if isAppleWatchConnected {
                            _ = await state.syncHealthKit(watchBrand: "apple_watch")
                        }
                        if let notice = state.syncNotice, !notice.isEmpty {
                            onShowToast(notice)
                        }
                    }
                }) {
                    HStack(spacing: 8) {
                        if state.isSyncing {
                            ProgressView()
                                .tint(Theme.onBrand)
                                .scaleEffect(0.8)
                            Text("正在同步最新跑步记录...")
                        } else {
                            Image(systemName: "arrow.triangle.2.circlepath.icloud.fill")
                            Text("同步最新跑步记录")
                        }
                    }
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(Theme.onBrand)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 11)
                    .background(Theme.brandFill)
                    .cornerRadius(10)
                }
                .disabled(state.isSyncing)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
}

// MARK: - Privacy Statement Card View
// MARK: - HealthKit Sync Card View
struct HealthKitSyncCardView: View {
    @EnvironmentObject var state: AppState
    @State private var isSyncing: Bool = false
    @State private var syncStatus: String? = nil
    let onSyncSuccess: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: "heart.text.square.fill")
                        .foregroundColor(Theme.primaryOrange)
                        .font(.system(size: 16))
                    Text("Apple 健康 (HealthKit) 直读")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                }
                Spacer()
                Text("无需配对")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(Theme.accentGreen)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(Theme.accentGreen.opacity(0.15))
                    .cornerRadius(6)
            }
            
            Text("从 iPhone 的「健康」App 读取跑步记录（含心率、爬升、GPS 轨迹）以及静息心率、HRV、睡眠数据，加密上传至 RGM 服务器用于训练负荷计算与 AI 教练分析，不会用于广告或分享给第三方。")
                .font(.system(size: 11))
                .foregroundColor(Theme.textMuted)
                .lineSpacing(3)
            
            HStack(spacing: 8) {
                HStack(spacing: 4) {
                    Image(systemName: "lock.shield.fill")
                        .foregroundColor(Theme.accentGreen)
                        .font(.system(size: 12))
                    Text("加密传输")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(Theme.textSecondary)
                }
                Text("•").foregroundColor(Theme.textMuted)
                HStack(spacing: 4) {
                    Image(systemName: "antenna.radiowaves.left.and.right.slash")
                        .foregroundColor(Theme.primaryOrange)
                        .font(.system(size: 12))
                    Text("无蓝牙硬件配对")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(Theme.textSecondary)
                }
                Text("•").foregroundColor(Theme.textMuted)
                HStack(spacing: 4) {
                    Image(systemName: "bolt.fill")
                        .foregroundColor(Theme.accentYellow)
                        .font(.system(size: 12))
                    Text("即刻计算")
                        .font(.system(size: 11, weight: .medium))
                        .foregroundColor(Theme.textSecondary)
                }
            }
            .padding(.vertical, 4)
            
            if let status = syncStatus {
                Text(status)
                    .font(.system(size: 11))
                    .foregroundColor(Theme.accentGreen)
                    .padding(.vertical, 2)
            }
            
            Button(action: {
                Task {
                    isSyncing = true
                    syncStatus = "正在读取并上传 Apple 健康数据..."
                    let ok = await state.syncHealthKit()
                    syncStatus = state.syncNotice
                    if ok { onSyncSuccess() }
                    isSyncing = false
                }
            }) {
                HStack {
                    if isSyncing {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: Theme.onBrand))
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "arrow.triangle.2.circlepath")
                            .font(.system(size: 13, weight: .bold))
                    }
                    Text(isSyncing ? "正在同步最新跑步记录..." : "立即从 Apple 健康同步跑步数据")
                        .font(.system(size: 13, weight: .bold))
                }
                .foregroundColor(Theme.onBrand)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 11)
                .background(Theme.brandFill)
                .cornerRadius(10)
            }
            .disabled(isSyncing)
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
}

// MARK: - Local Data & Privacy Card View
struct LocalDataPrivacyCardView: View {
    let onClearData: () -> Void
    @State private var showClearAlert: Bool = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: "shield.lefthalf.filled")
                        .foregroundColor(Theme.accentGreen)
                        .font(.system(size: 14))
                    Text("端侧计算与数据隐私保障")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                }
                Spacer()
                Text("Local-First")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(Theme.accentGreen)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Theme.accentGreen.opacity(0.12))
                    .cornerRadius(4)
            }
            
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .top, spacing: 8) {
                    Text("📱").font(.system(size: 13))
                    VStack(alignment: .leading, spacing: 1) {
                        Text("本地优先：运动数据完全留在您的手机").font(.system(size: 11, weight: .bold)).foregroundColor(Theme.textPrimary)
                        Text("您的跑步心率、GPS 轨迹、步频步幅等个人隐私生理数据直接存储在本地沙盒，由手机端直接驱动 Canova AI 动力学分析，不进行未经授权的云端扩散。").font(.system(size: 10)).foregroundColor(Theme.textMuted).lineSpacing(2)
                    }
                }
                
                HStack(alignment: .top, spacing: 8) {
                    Text("🗑️").font(.system(size: 13))
                    VStack(alignment: .leading, spacing: 1) {
                        Text("随时自主清除与掌控").font(.system(size: 11, weight: .bold)).foregroundColor(Theme.textPrimary)
                        Text("您可以随时一键清空本地训练数据缓存，或注销您的账号。").font(.system(size: 10)).foregroundColor(Theme.textMuted).lineSpacing(2)
                    }
                }
            }
            
            Button(action: {
                showClearAlert = true
            }) {
                HStack(spacing: 4) {
                    Image(systemName: "trash")
                        .font(.system(size: 11))
                    Text("清除本地运动数据缓存")
                        .font(.system(size: 11, weight: .medium))
                }
                .foregroundColor(Theme.textMuted)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Theme.surfaceSecondary)
                .cornerRadius(6)
            }
            .alert(isPresented: $showClearAlert) {
                Alert(
                    title: Text("确认清空本地运动缓存？"),
                    message: Text("此操作将清除保存在本机上的跑步运动缓存，您可以随时重新从 Apple 健康同步。"),
                    primaryButton: .destructive(Text("确定清除")) {
                        onClearData()
                    },
                    secondaryButton: .cancel(Text("取消"))
                )
            }
        }
        .padding(14)
        .background(Theme.surface)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
    }
}

struct PrivacyStatementCardView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("🛡️ 个人隐私与数据安全保障")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Spacer()
                Text("AES-256")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundColor(Theme.accentGreen)
            }
            
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .top, spacing: 8) {
                    Text("🔒").font(.system(size: 13))
                    VStack(alignment: .leading, spacing: 1) {
                        Text("敏感隐私 AES-256 高强度密文存储").font(.system(size: 11, weight: .bold)).foregroundColor(Theme.textPrimary)
                        Text("真实姓名、身份证号、出生日期及手机号均在数据库底层采用 AES-256-GCM 密文存储。").font(.system(size: 10)).foregroundColor(Theme.textMuted).lineSpacing(2)
                    }
                }
                HStack(alignment: .top, spacing: 8) {
                    Text("👁️").font(.system(size: 13))
                    VStack(alignment: .leading, spacing: 1) {
                        Text("大群体名册严格自动脱敏").font(.system(size: 11, weight: .bold)).foregroundColor(Theme.textPrimary)
                        Text("在团队名册中，非管理员跑友仅可见脱敏姓名与年龄组别，身份证号对普通成员完全隐蔽。").font(.system(size: 10)).foregroundColor(Theme.textMuted).lineSpacing(2)
                    }
                }
            }
        }
        .padding(14)
        .background(Theme.surface)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
    }
}

// MARK: - PB Section Card View
struct PbSectionCardView: View {
    let marathonPb: String
    let halfPb: String
    let tenKPb: String
    let fiveKPb: String
    let onImportGarmin: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                HStack(spacing: 6) {
                    Text("⚡").font(.system(size: 14))
                    Text("个人最佳成绩 (PB)").font(.system(size: 14, weight: .bold)).foregroundColor(Theme.textPrimary)
                }
                Spacer()
                Button(action: onImportGarmin) {
                    Text("从 Garmin 导入")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.primaryOrange)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Theme.primaryOrange.opacity(0.12))
                        .cornerRadius(6)
                }
            }
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                pbItem(label: "全马 (42.195k)", val: marathonPb)
                pbItem(label: "半马 (21.0975k)", val: halfPb)
                pbItem(label: "10公里", val: tenKPb)
                pbItem(label: "5公里", val: fiveKPb)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private func pbItem(label: String, val: String) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(label).font(.system(size: 10)).foregroundColor(Theme.textMuted)
            Text(val).font(.system(size: 18, weight: .bold, design: .rounded)).foregroundColor(Theme.primaryOrange)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Theme.surfaceSecondary)
        .cornerRadius(8)
    }
}

// MARK: - Biometrics Section Card View
struct BiometricsSectionCardView: View {
    let vo2max: String
    let restHr: String
    let maxHr: String
    let yearsRunning: String
    let height: String
    let weight: String
    let onSyncWatches: () -> Void
    
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                HStack(spacing: 6) {
                    Text("💓").font(.system(size: 14))
                    Text("运动体能与生理指标").font(.system(size: 14, weight: .bold)).foregroundColor(Theme.textPrimary)
                }
                Spacer()
                Button(action: onSyncWatches) {
                    Text("从手表同步指标")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.accentGreen)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Theme.accentGreen.opacity(0.12))
                        .cornerRadius(6)
                }
            }
            
            Text("Canova 教练根据静息心率与最大摄氧量 (VO2Max) 智能自适应训练配速区间与超量恢复。")
                .font(.system(size: 11))
                .foregroundColor(Theme.textMuted)
                .lineSpacing(2)
            
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                bioTile(label: "最大摄氧量 (VO2Max)", val: vo2max, unit: "ml/kg/min", tip: "⚡ 依据 PB 测算")
                bioTile(label: "静息心率 (Rest HR)", val: restHr, unit: "bpm", tip: "清晨静息基线")
                bioTile(label: "最大心率 (Max HR)", val: maxHr, unit: "bpm", tip: "极限负荷基线")
                bioTile(label: "跑步年限", val: yearsRunning, unit: "年", tip: "17年耐力积淀")
                bioTile(label: "跑者身高", val: height, unit: "cm", tip: "")
                bioTile(label: "跑者体重", val: weight, unit: "kg", tip: "")
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private func bioTile(label: String, val: String, unit: String, tip: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(label).font(.system(size: 10)).foregroundColor(Theme.textMuted)
                Spacer()
                if !tip.isEmpty {
                    Text(tip).font(.system(size: 8)).foregroundColor(Theme.primaryOrange)
                }
            }
            HStack(alignment: .lastTextBaseline, spacing: 2) {
                Text(val).font(.system(size: 17, weight: .bold, design: .rounded)).foregroundColor(Theme.textPrimary)
                if !unit.isEmpty {
                    Text(unit).font(.system(size: 9)).foregroundColor(Theme.textMuted)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Theme.surfaceSecondary)
        .cornerRadius(8)
    }
}

// MARK: - Mileage Goal Card View
struct MileageGoalCardView: View {
    @Binding var targetDistance: Int
    @Binding var weeklyTarget: Int
    @Binding var monthlyTargets: [Int]
    
    @State private var selectedMonth: Int? = nil
    
    private let quickMonths = [100, 150, 200, 250, 300, 350, 400]
    private let quickWeeks = [30, 40, 50, 60, 70, 80, 100]
    
    private var currentCalendarMonth: Int {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "Asia/Shanghai") ?? .current
        return cal.component(.month, from: Date())
    }
    
    private var isAllMonthsUniform: Bool {
        guard monthlyTargets.count == 12 else { return true }
        return monthlyTargets.allSatisfy { $0 == targetDistance }
    }
    
    private var yearlyTotalKm: Int {
        if monthlyTargets.count == 12 {
            return monthlyTargets.reduce(0, +)
        }
        return targetDistance * 12
    }
    
    private func monthlyValue(for month: Int) -> Int {
        let idx = month - 1
        if idx >= 0 && idx < monthlyTargets.count {
            return monthlyTargets[idx]
        }
        return targetDistance
    }
    
    private func setAllMonths(_ km: Int) {
        let clamped = max(20, min(1000, km))
        targetDistance = clamped
        monthlyTargets = Array(repeating: clamped, count: 12)
    }
    
    private func setMonth(_ month: Int, km: Int) {
        let clamped = max(0, min(1000, km))
        if monthlyTargets.count < 12 {
            monthlyTargets = Array(repeating: targetDistance, count: 12)
        }
        let idx = month - 1
        if idx >= 0 && idx < 12 {
            monthlyTargets[idx] = clamped
        }
        if month == currentCalendarMonth {
            targetDistance = clamped
        }
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                HStack(spacing: 6) {
                    Text("🎯").font(.system(size: 14))
                    Text("个人跑量目标规划 (2026)").font(.system(size: 14, weight: .bold)).foregroundColor(Theme.textPrimary)
                }
                Spacer()
                Text(isAllMonthsUniform ? "全年统一: \(targetDistance) km/月" : "年总计 \(yearlyTotalKm) km · 当月 \(monthlyValue(for: currentCalendarMonth)) km")
                    .font(.system(size: 10, weight: .semibold))
                    .foregroundColor(Theme.primaryOrange)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(Theme.primaryOrange.opacity(0.12))
                    .cornerRadius(6)
            }
            
            Text("设定您个人的月跑量计划。既可通过下方快捷档位一键设定全年统一月目标，也可点击任意月份单独微调备赛周期跑量。")
                .font(.system(size: 11))
                .foregroundColor(Theme.textMuted)
                .lineSpacing(2)
            
            // 1. 全年统一月跑量快捷设定与步进器
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("📅 常规月跑量计划 (全年基准)")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.textPrimary)
                    Spacer()
                    HStack(spacing: 6) {
                        Button(action: {
                            setAllMonths(targetDistance - 10)
                        }) {
                            Image(systemName: "minus")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(Theme.textPrimary)
                                .frame(width: 22, height: 22)
                                .background(Theme.surfaceSecondary)
                                .cornerRadius(6)
                        }
                        .buttonStyle(PlainButtonStyle())
                        
                        Text("\(targetDistance) km / 月")
                            .font(.system(size: 12, weight: .bold, design: .rounded))
                            .foregroundColor(Theme.primaryOrange)
                            .frame(minWidth: 68, alignment: .center)
                        
                        Button(action: {
                            setAllMonths(targetDistance + 10)
                        }) {
                            Image(systemName: "plus")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(Theme.textPrimary)
                                .frame(width: 22, height: 22)
                                .background(Theme.surfaceSecondary)
                                .cornerRadius(6)
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
                
                HStack(spacing: 6) {
                    ForEach(quickMonths, id: \.self) { km in
                        Button(action: {
                            setAllMonths(km)
                        }) {
                            Text("\(km)k")
                                .font(.system(size: 11, weight: (isAllMonthsUniform && targetDistance == km) ? .bold : .regular))
                                .foregroundColor((isAllMonthsUniform && targetDistance == km) ? .white : Theme.textSecondary)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 6)
                                .background((isAllMonthsUniform && targetDistance == km) ? Theme.primaryOrange : Theme.surfaceSecondary)
                                .cornerRadius(6)
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
            }
            
            // 2. 12个月份跑量细化网格（点击月份可单独调整）
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("🗓️ 各月跑量细化目标 (点击月份可单独调整)")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundColor(Theme.textPrimary)
                    Spacer()
                    if !isAllMonthsUniform {
                        Button(action: {
                            setAllMonths(targetDistance)
                            selectedMonth = nil
                        }) {
                            Text("重置为全年统一")
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundColor(Theme.primaryOrange)
                        }
                        .buttonStyle(PlainButtonStyle())
                    } else {
                        Text(selectedMonth == nil ? "点选月份微调" : "正在调整 \(selectedMonth!)月")
                            .font(.system(size: 10))
                            .foregroundColor(Theme.textMuted)
                    }
                }
                
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 6), spacing: 6) {
                    ForEach(1...12, id: \.self) { m in
                        let val = monthlyValue(for: m)
                        let isSelected = (selectedMonth == m)
                        let isCurMonth = (m == currentCalendarMonth)
                        let isCustom = (val != targetDistance)
                        
                        Button(action: {
                            withAnimation(.easeInOut(duration: 0.15)) {
                                selectedMonth = (selectedMonth == m) ? nil : m
                            }
                        }) {
                            VStack(spacing: 2) {
                                HStack(spacing: 2) {
                                    Text("\(m)月")
                                        .font(.system(size: 9, weight: isCurMonth ? .bold : .regular))
                                        .foregroundColor(isSelected ? Theme.primaryOrange : (isCurMonth ? Theme.textPrimary : Theme.textMuted))
                                    if isCurMonth {
                                        Circle()
                                            .fill(Theme.primaryOrange)
                                            .frame(width: 4, height: 4)
                                    }
                                }
                                Text("\(val)")
                                    .font(.system(size: 12, weight: .bold, design: .rounded))
                                    .foregroundColor(isSelected || isCustom ? Theme.primaryOrange : Theme.textPrimary)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 6)
                            .background(isSelected ? Theme.primaryOrange.opacity(0.15) : Theme.surfaceSecondary)
                            .cornerRadius(6)
                            .overlay(
                                RoundedRectangle(cornerRadius: 6)
                                    .stroke(isSelected ? Theme.primaryOrange : (isCurMonth ? Theme.primaryOrange.opacity(0.35) : Color.clear), lineWidth: 1)
                            )
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
                
                // 单月跑量精细调节面板
                if let m = selectedMonth {
                    let currentVal = monthlyValue(for: m)
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("正在调整 \(m)月 目标跑量")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundColor(Theme.primaryOrange)
                            Spacer()
                            HStack(spacing: 6) {
                                ForEach([-20, -10, 10, 20], id: \.self) { delta in
                                    Button(action: {
                                        setMonth(m, km: currentVal + delta)
                                    }) {
                                        Text(delta > 0 ? "+\(delta)" : "\(delta)")
                                            .font(.system(size: 10, weight: .bold, design: .rounded))
                                            .foregroundColor(Theme.textPrimary)
                                            .padding(.horizontal, 7)
                                            .padding(.vertical, 4)
                                            .background(Theme.surface)
                                            .cornerRadius(5)
                                            .overlay(RoundedRectangle(cornerRadius: 5).stroke(Theme.border, lineWidth: 1))
                                    }
                                    .buttonStyle(PlainButtonStyle())
                                }
                                Button(action: {
                                    withAnimation(.easeInOut(duration: 0.15)) {
                                        selectedMonth = nil
                                    }
                                }) {
                                    Text("完成")
                                        .font(.system(size: 10, weight: .bold))
                                        .foregroundColor(.white)
                                        .padding(.horizontal, 8)
                                        .padding(.vertical, 4)
                                        .background(Theme.primaryOrange)
                                        .cornerRadius(5)
                                }
                                .buttonStyle(PlainButtonStyle())
                            }
                        }
                        
                        HStack(spacing: 6) {
                            ForEach(quickMonths, id: \.self) { km in
                                Button(action: {
                                    setMonth(m, km: km)
                                }) {
                                    Text("\(km)k")
                                        .font(.system(size: 10, weight: currentVal == km ? .bold : .regular))
                                        .foregroundColor(currentVal == km ? .white : Theme.textSecondary)
                                        .frame(maxWidth: .infinity)
                                        .padding(.vertical, 5)
                                        .background(currentVal == km ? Theme.primaryOrange : Theme.surface)
                                        .cornerRadius(5)
                                }
                                .buttonStyle(PlainButtonStyle())
                            }
                        }
                    }
                    .padding(10)
                    .background(Theme.surfaceSecondary.opacity(0.85))
                    .cornerRadius(8)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.primaryOrange.opacity(0.35), lineWidth: 1))
                }
            }
            
            // 3. 常规周跑量计划
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Text("🏃 常规周跑量计划").font(.system(size: 11, weight: .semibold)).foregroundColor(Theme.textPrimary)
                    Spacer()
                    HStack(spacing: 6) {
                        Button(action: {
                            weeklyTarget = max(10, weeklyTarget - 5)
                        }) {
                            Image(systemName: "minus")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(Theme.textPrimary)
                                .frame(width: 22, height: 22)
                                .background(Theme.surfaceSecondary)
                                .cornerRadius(6)
                        }
                        .buttonStyle(PlainButtonStyle())
                        
                        Text("\(weeklyTarget) km / 周")
                            .font(.system(size: 11, weight: .bold, design: .rounded))
                            .foregroundColor(Theme.accentGreen)
                            .frame(minWidth: 64, alignment: .center)
                        
                        Button(action: {
                            weeklyTarget = min(300, weeklyTarget + 5)
                        }) {
                            Image(systemName: "plus")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundColor(Theme.textPrimary)
                                .frame(width: 22, height: 22)
                                .background(Theme.surfaceSecondary)
                                .cornerRadius(6)
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
                
                HStack(spacing: 8) {
                    ForEach(quickWeeks, id: \.self) { km in
                        WeeklyChip(km: km, isSelected: weeklyTarget == km) {
                            weeklyTarget = km
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
}

// MARK: - Race Plans Card View & Editor Models

enum RaceIntelConstants {
    static let raceLevelOptions = [
        "世界白金标", "国际金标", "IAAF 银标", "IAAF 铜标", "国内 A 类认证", "普通大众认证", "品牌邀请赛"
    ]
    static let courseProfileOptions = [
        "极速平坦 (破 PB 首选)", "轻微起伏", "中等坡度", "丘陵赛道", "多爬升挑战赛道"
    ]
    static let courseSurfaceOptions = [
        "柏油路", "石板路", "混合路面（柏油+石板）", "碎石路"
    ]
    static let difficultyOptions = [
        "入门级", "进阶级", "精英级", "极限级"
    ]
    static let trailTerrainOptions = [
        "山地跑道", "高原草甸", "丛林密林", "岩石峭壁", "沙漠戈壁", "混合地形"
    ]
    static let climateZoneOptions = [
        "温带大陆性", "亚热带季风", "高寒高原", "热带季风", "温带海洋性"
    ]
    
    static func isTrail(_ raceType: String?) -> Bool {
        guard let rt = raceType?.lowercased() else { return false }
        return rt.contains("trail") || rt.contains("ultra") || rt.contains("越野") || rt.contains("山地")
    }
}

struct RaceEditorData: Identifiable {
    let id: String
    let race: RaceItem?
}

struct RacePlansCardView: View {
    @EnvironmentObject var state: AppState
    let races: [RaceItem]
    var onToast: ((String) -> Void)? = nil
    
    @State private var activeRaceEditor: RaceEditorData? = nil
    @State private var expandedRaceInfo: [String: Bool] = [:]
    @State private var raceInfoDrafts: [String: RaceInfoData] = [:]
    @State private var searchingRaceInfo: [String: Bool] = [:]
    @State private var savingRaceInfo: [String: Bool] = [:]
    @State private var raceToDelete: RaceItem? = nil
    @State private var showDeleteRaceAlert: Bool = false
    
    var effectiveRaces: [RaceItem] {
        races
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                HStack(spacing: 6) {
                    Text("🏁").font(.system(size: 14))
                    Text("比赛计划与倒计时").font(.system(size: 14, weight: .bold)).foregroundColor(Theme.textPrimary)
                }
                Spacer()
                Button(action: {
                    activeRaceEditor = RaceEditorData(id: "new_\(Date().timeIntervalSince1970)", race: nil)
                }) {
                    HStack(spacing: 4) {
                        Image(systemName: "plus")
                            .font(.system(size: 10, weight: .bold))
                        Text("添加比赛")
                            .font(.system(size: 11, weight: .semibold))
                    }
                    .foregroundColor(Theme.primaryOrange)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(Theme.primaryOrange.opacity(0.12))
                    .cornerRadius(6)
                }
            }
            
            if effectiveRaces.isEmpty {
                VStack(spacing: 10) {
                    Text("暂无比赛计划，点击下方按钮开始规划备战吧！")
                        .font(.system(size: 12))
                        .foregroundColor(Theme.textMuted)
                    Button(action: {
                        activeRaceEditor = RaceEditorData(id: "new_\(Date().timeIntervalSince1970)", race: nil)
                    }) {
                        Text("+ 立即添加第一场比赛")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundColor(Theme.primaryOrange)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                            .background(Theme.primaryOrange.opacity(0.12))
                            .cornerRadius(8)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.vertical, 16)
            }
            
            ForEach(effectiveRaces) { r in
                raceCardItem(r)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
        .sheet(item: $activeRaceEditor) { editorData in
            RaceEditorSheet(
                initialRace: editorData.race,
                onSave: {
                    onToast?(editorData.race == nil ? "比赛计划已添加 🎉" : "比赛计划已更新 ✓")
                },
                onDelete: {
                    onToast?("比赛计划已删除 🗑️")
                }
            )
            .environmentObject(state)
        }
        .alert("删除比赛计划", isPresented: $showDeleteRaceAlert) {
            Button("取消", role: .cancel) { raceToDelete = nil }
            Button("删除", role: .destructive) {
                if let target = raceToDelete {
                    Task {
                        try? await state.deleteRace(raceId: target.id)
                        onToast?("赛事已删除 🗑️")
                    }
                }
                raceToDelete = nil
            }
        } message: {
            Text("确定要删除「\(raceToDelete?.name ?? "")」吗？")
        }
    }
    
    @ViewBuilder
    private func raceCardItem(_ r: RaceItem) -> some View {
        let isCompleted = (r.status == "completed" || r.is_completed == true)
        let daysLeft = r.days_left ?? calculateDaysLeft(r.race_date)
        let isExpanded = expandedRaceInfo[r.id] ?? false
        let currentInfo = raceInfoDrafts[r.id] ?? r.race_info ?? RaceInfoData()
        let hasInfo = currentInfo.hasAnyValue
        let isSearching = searchingRaceInfo[r.id] ?? false
        let isSaving = savingRaceInfo[r.id] ?? false
        let isTrail = RaceIntelConstants.isTrail(r.race_type)
        
        VStack(alignment: .leading, spacing: 10) {
            // 1. Top Row: Name + Priority Tag + Countdown/Completed Badge + Quick Edit/Delete Pills
            HStack(alignment: .top, spacing: 8) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 6) {
                        Text(r.name)
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(Theme.textPrimary)
                            .lineLimit(1)
                        
                        let isA = (r.priority == 1)
                        let isB = (r.priority == 2)
                        Text(isA ? "A 标" : (isB ? "B 标" : "C 标"))
                            .font(.system(size: 9, weight: .bold))
                            .foregroundColor(isA ? Color(hex: "F43F5E") : (isB ? Theme.accentYellow : Theme.accentBlue))
                            .padding(.horizontal, 5)
                            .padding(.vertical, 2)
                            .background((isA ? Color(hex: "F43F5E") : (isB ? Theme.accentYellow : Theme.accentBlue)).opacity(0.15))
                            .cornerRadius(4)
                    }
                    
                    // 2. Meta Row
                    HStack(spacing: 8) {
                        if let type = r.race_type {
                            Text(formatRaceType(type))
                                .font(.system(size: 10, weight: .medium))
                                .foregroundColor(Theme.primaryOrange)
                                .padding(.horizontal, 5)
                                .padding(.vertical, 1.5)
                                .background(Theme.primaryOrange.opacity(0.1))
                                .cornerRadius(4)
                        }
                        if let date = r.race_date {
                            Text(String(date.prefix(10)))
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundColor(Theme.textMuted)
                        }
                        if let target = r.target_time, !target.isEmpty {
                            Text("目标: \(target)")
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundColor(Theme.textSecondary)
                        }
                        if let finish = r.finish_time, !finish.isEmpty {
                            Text("完赛: \(finish)")
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .foregroundColor(Theme.accentGreen)
                        }
                    }
                }
                
                Spacer(minLength: 4)
                
                HStack(spacing: 6) {
                    if isCompleted {
                        Text("🏅 已完赛")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(Theme.accentGreen)
                            .padding(.horizontal, 7)
                            .padding(.vertical, 3.5)
                            .background(Theme.accentGreen.opacity(0.15))
                            .cornerRadius(6)
                    } else {
                        Text("\(daysLeft) 天\(daysLeft < 30 ? " 冲刺" : "")")
                            .font(.system(size: 10, weight: .bold, design: .rounded))
                            .foregroundColor(daysLeft < 30 ? Color(hex: "F43F5E") : Theme.primaryOrange)
                            .padding(.horizontal, 7)
                            .padding(.vertical, 3.5)
                            .background((daysLeft < 30 ? Color(hex: "F43F5E") : Theme.primaryOrange).opacity(0.14))
                            .cornerRadius(6)
                    }
                    
                    Button(action: {
                        activeRaceEditor = RaceEditorData(id: r.id, race: r)
                    }) {
                        Text(isCompleted ? "🏅 记录" : "✏️ 编辑")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundColor(Theme.textPrimary)
                            .padding(.horizontal, 7)
                            .padding(.vertical, 3.5)
                            .background(Theme.surface)
                            .cornerRadius(6)
                            .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.border, lineWidth: 1))
                    }
                    .buttonStyle(PlainButtonStyle())
                    
                    Button(action: {
                        raceToDelete = r
                        showDeleteRaceAlert = true
                    }) {
                        Text("🗑️")
                            .font(.system(size: 10))
                            .padding(.horizontal, 6)
                            .padding(.vertical, 3.5)
                            .background(Theme.surface)
                            .cornerRadius(6)
                            .overlay(RoundedRectangle(cornerRadius: 6).stroke(Theme.border, lineWidth: 1))
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
            
            // 3. Completed Race Summary Banner or Past Race Tip
            if isCompleted {
                VStack(alignment: .leading, spacing: 6) {
                    HStack(spacing: 8) {
                        Text(r.performance_badge ?? "顺利完赛 🏅")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(Theme.accentGreen)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Theme.accentGreen.opacity(0.15))
                            .cornerRadius(4)
                        if let diffStr = r.diff_str, !diffStr.isEmpty {
                            Text("比目标 \(diffStr)")
                                .font(.system(size: 10, weight: .medium, design: .monospaced))
                                .foregroundColor(Theme.textSecondary)
                        }
                    }
                    if let notes = r.finish_notes, !notes.isEmpty {
                        Text("“\(notes)”")
                            .font(.system(size: 11))
                            .foregroundColor(Theme.textSecondary)
                            .italic()
                    }
                    if let photos = r.photos, !photos.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(photos, id: \.self) { urlStr in
                                    if let u = URL(string: urlStr) {
                                        AsyncImage(url: u) { phase in
                                            if case .success(let img) = phase {
                                                img.resizable()
                                                    .scaledToFill()
                                                    .frame(width: 54, height: 54)
                                                    .clipShape(RoundedRectangle(cornerRadius: 6))
                                            } else {
                                                RoundedRectangle(cornerRadius: 6)
                                                    .fill(Theme.surface)
                                                    .frame(width: 54, height: 54)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Theme.accentGreen.opacity(0.06))
                .cornerRadius(8)
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.accentGreen.opacity(0.25), lineWidth: 1))
            } else if r.is_past == true {
                Button(action: {
                    activeRaceEditor = RaceEditorData(id: r.id, race: r)
                }) {
                    HStack {
                        Text("⚠️ 比赛日已过，点击标记完赛与填报成绩 ➔")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(Theme.accentYellow)
                        Spacer()
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(Theme.accentYellow.opacity(0.12))
                    .cornerRadius(8)
                }
                .buttonStyle(PlainButtonStyle())
            }
            
            // 4. Quick Priority Tier Switcher (定位调整: A标 / B标 / C标)
            HStack(spacing: 8) {
                Text("定位调整:")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundColor(Theme.textMuted)
                
                HStack(spacing: 6) {
                    ForEach([
                        (1, "A 标 (核心)", Color(hex: "F43F5E")),
                        (2, "B 标 (代练)", Theme.accentYellow),
                        (3, "C 标 (拉练)", Theme.accentBlue)
                    ], id: \.0) { tier, label, color in
                        let isActive = (r.priority ?? 2) == tier
                        Button(action: {
                            Task {
                                try? await state.updateRacePriority(raceId: r.id, priority: tier)
                                onToast?("已更新赛事定位为 \(label)")
                            }
                        }) {
                            Text(label)
                                .font(.system(size: 10, weight: isActive ? .bold : .regular))
                                .foregroundColor(isActive ? color : Theme.textSecondary)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(isActive ? color.opacity(0.15) : Theme.surface)
                                .cornerRadius(5)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 5)
                                        .stroke(isActive ? color.opacity(0.5) : Theme.border, lineWidth: 1)
                                )
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
                Spacer()
            }
            
            // 5. Quick Summary Chips when Race Intelligence is populated
            if hasInfo && !isExpanded {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        if let dist = currentInfo.race_distance_km, dist > 0 {
                            intelSummaryChip("📏 \(String(format: dist.truncatingRemainder(dividingBy: 1) == 0 ? "%.0f" : "%.1f", dist))km")
                        }
                        if let gain = currentInfo.elevation_gain_m ?? currentInfo.net_elevation_gain_m, gain > 0 {
                            intelSummaryChip("⛰️ D+ \(Int(gain))m")
                        }
                        if let alt = currentInfo.max_altitude_m, alt > 0 {
                            intelSummaryChip("🏔️ 最高 \(Int(alt))m")
                        }
                        if let diff = currentInfo.difficulty_level, !diff.isEmpty {
                            intelSummaryChip("🔥 \(diff)")
                        }
                        if let terrain = currentInfo.terrain_type, !terrain.isEmpty {
                            intelSummaryChip("🌲 \(terrain)")
                        }
                        if let lvl = currentInfo.race_level, !lvl.isEmpty {
                            intelSummaryChip("🏅 \(lvl)")
                        }
                        if let prof = currentInfo.course_profile, !prof.isEmpty {
                            intelSummaryChip("🛣️ \(prof)")
                        }
                        if let temp = currentInfo.avg_temp_c {
                            intelSummaryChip("🌤️ \(Int(temp))℃")
                        }
                    }
                }
            }
            
            // 6. Race Intelligence Collapsible Header & One-Tap Auto-Fill Button
            HStack(spacing: 8) {
                Button(action: {
                    withAnimation(.easeInOut(duration: 0.18)) {
                        if raceInfoDrafts[r.id] == nil {
                            raceInfoDrafts[r.id] = r.race_info ?? RaceInfoData()
                        }
                        expandedRaceInfo[r.id] = !isExpanded
                    }
                }) {
                    HStack(spacing: 4) {
                        Text(hasInfo ? "📋 赛事情报已填写 (点击\(isExpanded ? "收起" : "展开/编辑"))" : "📋 赛事情报未填 (点击展开)")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(hasInfo ? Theme.textPrimary : Theme.textSecondary)
                        Spacer()
                        Text(isExpanded ? "▲" : "▼")
                            .font(.system(size: 9))
                            .foregroundColor(Theme.textMuted)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(Theme.surface)
                    .cornerRadius(7)
                    .overlay(RoundedRectangle(cornerRadius: 7).stroke(Theme.border, lineWidth: 1))
                }
                .buttonStyle(PlainButtonStyle())
                
                Button(action: {
                    handleAutoFetchCardRaceInfo(r)
                }) {
                    HStack(spacing: 4) {
                        if isSearching {
                            ProgressView()
                                .scaleEffect(0.65)
                                .tint(Theme.primaryOrange)
                        } else {
                            Text("⚡")
                                .font(.system(size: 10))
                        }
                        Text(isSearching ? "检索中..." : "自动填情报")
                            .font(.system(size: 10, weight: .bold))
                    }
                    .foregroundColor(Theme.primaryOrange)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(Theme.primaryOrange.opacity(0.14))
                    .cornerRadius(7)
                    .overlay(RoundedRectangle(cornerRadius: 7).stroke(Theme.primaryOrange.opacity(0.35), lineWidth: 1))
                }
                .buttonStyle(PlainButtonStyle())
                .disabled(isSearching)
            }
            
            // 7. Expanded Race Intelligence Inline Form
            if isExpanded {
                RaceIntelFormView(
                    isTrail: isTrail,
                    info: Binding(
                        get: { raceInfoDrafts[r.id] ?? r.race_info ?? RaceInfoData() },
                        set: { raceInfoDrafts[r.id] = $0 }
                    ),
                    isSaving: isSaving,
                    showSaveButton: true,
                    onSave: {
                        handleSaveCardRaceInfo(r)
                    }
                )
            }
        }
        .padding(12)
        .background(Theme.surfaceSecondary)
        .cornerRadius(10)
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.border, lineWidth: 1))
    }
    
    private func intelSummaryChip(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 10, weight: .medium))
            .foregroundColor(Theme.textSecondary)
            .padding(.horizontal, 7)
            .padding(.vertical, 3)
            .background(Theme.surface)
            .cornerRadius(5)
            .overlay(RoundedRectangle(cornerRadius: 5).stroke(Theme.border, lineWidth: 0.8))
    }
    
    private func handleAutoFetchCardRaceInfo(_ r: RaceItem) {
        searchingRaceInfo[r.id] = true
        Task {
            do {
                let res = try await state.lookupRaceIntel(
                    raceName: r.name,
                    raceType: r.race_type,
                    targetTime: r.target_time,
                    raceDate: r.race_date,
                    raceId: r.id
                )
                if res.success == true, let fetched = res.race_info {
                    raceInfoDrafts[r.id] = fetched
                    withAnimation {
                        expandedRaceInfo[r.id] = true
                    }
                    onToast?("已自动同步官方赛事情报 ✓")
                } else {
                    withAnimation {
                        expandedRaceInfo[r.id] = true
                    }
                    onToast?(res.message ?? "未能检索到，请手动填写")
                }
            } catch {
                onToast?("检索失败，可展开手动填写")
            }
            searchingRaceInfo[r.id] = false
        }
    }
    
    private func handleSaveCardRaceInfo(_ r: RaceItem) {
        let info = raceInfoDrafts[r.id] ?? r.race_info ?? RaceInfoData()
        savingRaceInfo[r.id] = true
        Task {
            do {
                try await state.saveRaceInfo(raceId: r.id, raceInfo: info)
                onToast?("赛事情报已保存 ✓")
            } catch {
                onToast?("保存赛事情报失败，请重试")
            }
            savingRaceInfo[r.id] = false
        }
    }
    
    private func formatRaceType(_ raw: String) -> String {
        switch raw.lowercased() {
        case "trail": return "越野跑"
        case "road": return "路跑马拉松"
        case "half": return "半程马拉松"
        case "triathlon": return "铁人三项"
        case "ultra": return "极限耐力越野"
        default: return raw
        }
    }
    
    private func calculateDaysLeft(_ dateStr: String?) -> Int {
        guard let s = dateStr, s.count >= 10 else { return 30 }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        if let targetDate = formatter.date(from: String(s.prefix(10))) {
            let diff = Calendar.current.dateComponents([.day], from: Date(), to: targetDate).day ?? 30
            return max(0, diff)
        }
        return 30
    }
}

// MARK: - Reusable Race Intelligence Editor Form (Trail / Road / Weather & Scale)

struct RaceIntelFormView: View {
    let isTrail: Bool
    @Binding var info: RaceInfoData
    var isSaving: Bool = false
    var showSaveButton: Bool = false
    var onSave: (() -> Void)? = nil
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("💡 支持手动编辑或上方「⚡自动填情报」一键检索官方规程，Canova AI 教练将据此定制海拔/坡度/补给与配速策略")
                .font(.system(size: 10))
                .foregroundColor(Theme.textMuted)
                .lineSpacing(2)
            
            if isTrail {
                // ── 越野赛专属字段 ──
                Text("🏔️ 越野赛情报")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(Theme.primaryOrange)
                
                HStack(spacing: 8) {
                    doubleField(title: "报名赛程 (km)", placeholder: "如 50 / 100", value: $info.race_distance_km)
                    doubleField(title: "累计爬升 D+ (m)", placeholder: "如 2800", value: $info.elevation_gain_m)
                }
                HStack(spacing: 8) {
                    doubleField(title: "累计下降 D- (m)", placeholder: "如 2600", value: $info.elevation_loss_m)
                    doubleField(title: "最高海拔 (m)", placeholder: "如 1918", value: $info.max_altitude_m)
                }
                HStack(spacing: 8) {
                    menuField(title: "难度等级", options: RaceIntelConstants.difficultyOptions, selection: $info.difficulty_level)
                    menuField(title: "地形类型", options: RaceIntelConstants.trailTerrainOptions, selection: $info.terrain_type)
                }
                menuField(title: "气候带", options: RaceIntelConstants.climateZoneOptions, selection: $info.climate_zone)
                textField(title: "强制装备要求", placeholder: "如: 头灯、1.5L水、急救毯、防风冲锋衣", text: $info.mandatory_gear)
                textField(title: "关门时间说明", placeholder: "如: 总关门 20小时，中途补给站 6个", text: $info.cutoff_notes)
            } else {
                // ── 公路赛专属字段 ──
                Text("🏅 公路赛客观情报")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundColor(Theme.primaryOrange)
                
                HStack(spacing: 8) {
                    menuField(title: "赛事等级", options: RaceIntelConstants.raceLevelOptions, selection: $info.race_level)
                    menuField(title: "赛道特点", options: RaceIntelConstants.courseProfileOptions, selection: $info.course_profile)
                }
                HStack(spacing: 8) {
                    menuField(title: "路面材质", options: RaceIntelConstants.courseSurfaceOptions, selection: $info.course_surface)
                    doubleField(title: "报名赛程 (km)", placeholder: "如 42.195 / 21.1", value: $info.race_distance_km)
                }
                HStack(spacing: 8) {
                    doubleField(
                        title: "累计爬升 D+ (m)",
                        placeholder: "如 50",
                        value: Binding(
                            get: { info.elevation_gain_m ?? info.net_elevation_gain_m },
                            set: {
                                info.elevation_gain_m = $0
                                info.net_elevation_gain_m = $0
                            }
                        )
                    )
                    doubleField(title: "累计下降 D- (m)", placeholder: "如 50", value: $info.elevation_loss_m)
                }
                textField(title: "关门时间说明", placeholder: "如: 全马6小时15分", text: $info.cutoff_notes)
            }
            
            // ── 通用天气与规模字段 ──
            Text("🌤️ 天气 & 规模")
                .font(.system(size: 11, weight: .bold))
                .foregroundColor(Theme.primaryOrange)
                .padding(.top, 4)
            
            HStack(spacing: 8) {
                doubleField(title: "历史平均气温 (℃)", placeholder: "如 12", value: $info.avg_temp_c)
                if !isTrail {
                    doubleField(title: "历史平均湿度 (%)", placeholder: "如 65", value: $info.humidity_pct)
                } else {
                    intField(title: "大致参赛人数", placeholder: "如 3500", value: $info.typical_participants)
                }
            }
            if !isTrail {
                intField(title: "大致参赛人数", placeholder: "如 30000", value: $info.typical_participants)
            }
            textField(title: "天气情况备注", placeholder: "如: 秋季举办，通常干燥清凉", text: $info.weather_notes)
            textField(title: "其他赛道备注", placeholder: "其他补充说明（如核心爬升段、补给策略等）", text: $info.custom_notes)
            
            if showSaveButton {
                Button(action: {
                    onSave?()
                }) {
                    HStack {
                        if isSaving {
                            ProgressView()
                                .scaleEffect(0.75)
                                .tint(.white)
                        }
                        Text(isSaving ? "正在保存..." : "保存赛事情报")
                            .font(.system(size: 12, weight: .bold))
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 10)
                    .background(Theme.primaryOrange)
                    .cornerRadius(8)
                }
                .buttonStyle(PlainButtonStyle())
                .disabled(isSaving)
                .padding(.top, 2)
            }
        }
        .padding(12)
        .background(Theme.surface)
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.border, lineWidth: 1))
    }
    
    private func doubleField(title: String, placeholder: String, value: Binding<Double?>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(Theme.textMuted)
            TextField(
                placeholder,
                text: Binding(
                    get: {
                        guard let v = value.wrappedValue else { return "" }
                        return v.truncatingRemainder(dividingBy: 1) == 0 ? String(format: "%.0f", v) : String(v)
                    },
                    set: { str in
                        let trimmed = str.trimmingCharacters(in: .whitespacesAndNewlines)
                        value.wrappedValue = trimmed.isEmpty ? nil : Double(trimmed)
                    }
                )
            )
            .keyboardType(.decimalPad)
            .font(.system(size: 12, design: .rounded))
            .foregroundColor(Theme.textPrimary)
            .padding(.horizontal, 9)
            .padding(.vertical, 7)
            .background(Theme.surfaceSecondary)
            .cornerRadius(6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
    
    private func intField(title: String, placeholder: String, value: Binding<Int?>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(Theme.textMuted)
            TextField(
                placeholder,
                text: Binding(
                    get: {
                        guard let v = value.wrappedValue else { return "" }
                        return "\(v)"
                    },
                    set: { str in
                        let trimmed = str.trimmingCharacters(in: .whitespacesAndNewlines)
                        value.wrappedValue = trimmed.isEmpty ? nil : Int(trimmed)
                    }
                )
            )
            .keyboardType(.numberPad)
            .font(.system(size: 12, design: .rounded))
            .foregroundColor(Theme.textPrimary)
            .padding(.horizontal, 9)
            .padding(.vertical, 7)
            .background(Theme.surfaceSecondary)
            .cornerRadius(6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
    
    private func textField(title: String, placeholder: String, text: Binding<String?>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(Theme.textMuted)
            TextField(
                placeholder,
                text: Binding(
                    get: { text.wrappedValue ?? "" },
                    set: { text.wrappedValue = $0.isEmpty ? nil : $0 }
                )
            )
            .font(.system(size: 12))
            .foregroundColor(Theme.textPrimary)
            .padding(.horizontal, 9)
            .padding(.vertical, 7)
            .background(Theme.surfaceSecondary)
            .cornerRadius(6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
    
    private func menuField(title: String, options: [String], selection: Binding<String?>) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(Theme.textMuted)
            Menu {
                Button("未选择") {
                    selection.wrappedValue = nil
                }
                ForEach(options, id: \.self) { opt in
                    Button(opt) {
                        selection.wrappedValue = opt
                    }
                }
            } label: {
                HStack {
                    Text(selection.wrappedValue ?? "请选择")
                        .font(.system(size: 12))
                        .foregroundColor((selection.wrappedValue?.isEmpty == false) ? Theme.textPrimary : Theme.textMuted)
                        .lineLimit(1)
                    Spacer()
                    Image(systemName: "chevron.down")
                        .font(.system(size: 9, weight: .semibold))
                        .foregroundColor(Theme.textMuted)
                }
                .padding(.horizontal, 9)
                .padding(.vertical, 7)
                .background(Theme.surfaceSecondary)
                .cornerRadius(6)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Race Editor Sheet (Add & Edit)

struct RaceEditorSheet: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) var dismiss
    
    let initialRace: RaceItem?
    var onSave: (() -> Void)? = nil
    var onDelete: (() -> Void)? = nil
    
    @State private var raceId: String = ""
    @State private var name: String = ""
    @State private var raceType: String = "trail"
    @State private var raceDate: Date = Date()
    @State private var targetTime: String = "03:30:00"
    @State private var priority: Int = 1
    @State private var isCompleted: Bool = false
    @State private var finishTime: String = ""
    @State private var finishNotes: String = ""
    @State private var photos: [String] = []
    @State private var raceInfo: RaceInfoData = RaceInfoData()
    @State private var expandRaceInfo: Bool = true
    
    @State private var isSearchingIntel: Bool = false
    @State private var isMatchingActivity: Bool = false
    @State private var isUploadingPhoto: Bool = false
    @State private var selectedPhotoItem: PhotosPickerItem? = nil
    @State private var isSaving: Bool = false
    @State private var isDeleting: Bool = false
    @State private var showDeleteAlert: Bool = false
    @State private var statusNotice: String? = nil
    @State private var errorMessage: String? = nil
    
    private let raceTypes: [(id: String, name: String, icon: String)] = [
        ("trail", "越野跑", "⛰️"),
        ("road", "路跑全马", "🏃"),
        ("half", "半程马拉松", "⚡"),
        ("10k", "10K 路跑", "🔥"),
        ("triathlon", "铁人三项", "🏊"),
        ("ultra", "百公里极限越野", "🏔️")
    ]
    
    private let quickTargets = ["03:00:00", "03:15:00", "03:30:00", "03:45:00", "04:00:00", "07:30:00", "09:00:00", "14:30:00", "24:00:00"]
    
    var isEditMode: Bool {
        initialRace != nil
    }
    
    private var calculatedDiff: (isFaster: Bool, badge: String, diffText: String)? {
        guard !finishTime.isEmpty, !targetTime.isEmpty,
              let tSec = parseTimeToSeconds(targetTime),
              let fSec = parseTimeToSeconds(finishTime) else {
            return nil
        }
        let diff = fSec - tSec
        if diff < 0 {
            return (true, "超额达标 🎉", "-\(formatSecondsToTime(abs(diff)))")
        } else if diff == 0 {
            return (true, "精准达标 🎯", "精准达标")
        } else {
            return (false, "顺利完赛 🏅", "+\(formatSecondsToTime(diff))")
        }
    }
    
    var body: some View {
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: 16) {
                        if let notice = statusNotice {
                            HStack(spacing: 6) {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundColor(Theme.accentGreen)
                                Text(notice)
                                    .font(.system(size: 12, weight: .semibold))
                                    .foregroundColor(Theme.accentGreen)
                                Spacer()
                            }
                            .padding(10)
                            .background(Theme.accentGreen.opacity(0.12))
                            .cornerRadius(10)
                        }
                        
                        // 1. Basic Info Card (with ⚡ 自动填情报)
                        basicInfoCard
                        
                        // 2. Race Priority Tier (A/B/C)
                        priorityCard
                        
                        // 3. Status & Results Card (with ⚡ 从手表记录一键提取 & 完赛照片上传)
                        statusCard
                        
                        // 4. Objective Race Intelligence Card (越野赛 / 公路赛客观情报 + 天气与规模)
                        raceIntelCard
                        
                        // Error message
                        if let err = errorMessage {
                            HStack(spacing: 6) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(Color(hex: "F43F5E"))
                                Text(err)
                                    .font(.system(size: 12))
                                    .foregroundColor(Color(hex: "F43F5E"))
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 4)
                        }
                        
                        // 5. Delete Button (Edit mode only)
                        if isEditMode {
                            deleteButton
                        }
                    }
                    .padding(16)
                    .padding(.bottom, 40)
                }
            }
            .navigationTitle(isEditMode ? "编辑比赛计划" : "添加新比赛计划")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("取消") {
                        dismiss()
                    }
                    .foregroundColor(Theme.textMuted)
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: handleSave) {
                        if isSaving {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: Theme.primaryOrange))
                        } else {
                            Text("保存")
                                .font(.system(size: 15, weight: .bold))
                                .foregroundColor(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? Theme.textMuted : Theme.primaryOrange)
                        }
                    }
                    .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSaving)
                }
            }
            .alert("确认删除比赛", isPresented: $showDeleteAlert) {
                Button("取消", role: .cancel) {}
                Button("确认删除", role: .destructive) {
                    handleDelete()
                }
            } message: {
                Text("确定要删除比赛【\(name.isEmpty ? (initialRace?.name ?? "此赛事") : name)】吗？删除后将无法恢复。")
            }
        }
        .onAppear {
            setupInitialData()
        }
        .onChange(of: selectedPhotoItem) { newItem in
            guard let item = newItem else { return }
            Task {
                await handleUploadSelectedPhoto(item)
            }
        }
    }
    
    private func setupInitialData() {
        if let r = initialRace {
            raceId = r.id
            name = r.name
            raceType = r.race_type ?? "trail"
            targetTime = r.target_time ?? "03:30:00"
            priority = r.priority ?? 1
            isCompleted = (r.status == "completed" || r.is_completed == true)
            finishTime = r.finish_time ?? ""
            finishNotes = r.finish_notes ?? ""
            photos = r.photos ?? (r.photo_url.map { $0.isEmpty ? [] : [$0] } ?? [])
            raceInfo = r.race_info ?? RaceInfoData()
            if let dateStr = r.race_date, dateStr.count >= 10 {
                let formatter = DateFormatter()
                formatter.dateFormat = "yyyy-MM-dd"
                if let d = formatter.date(from: String(dateStr.prefix(10))) {
                    raceDate = d
                }
            }
        } else {
            raceId = "race_\(Int(Date().timeIntervalSince1970))"
            name = ""
            raceType = "trail"
            targetTime = "03:30:00"
            priority = 1
            isCompleted = false
            finishTime = ""
            finishNotes = ""
            photos = []
            raceInfo = RaceInfoData()
            raceDate = Calendar.current.date(byAdding: .day, value: 45, to: Date()) ?? Date()
        }
    }
    
    // MARK: - Form Sections
    
    private var basicInfoCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("📋 赛事基本信息")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Spacer()
            }
            
            // Name + Auto Fetch Intelligence Button
            VStack(alignment: .leading, spacing: 6) {
                Text("比赛名称 (支持一键检索官方赛道情报)")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Theme.textSecondary)
                HStack(spacing: 8) {
                    TextField("如: 无锡马拉松 / 武功山越野赛 / 崇礼168", text: $name)
                        .font(.system(size: 14))
                        .padding(11)
                        .background(Theme.surfaceSecondary)
                        .cornerRadius(10)
                        .foregroundColor(Theme.textPrimary)
                    
                    Button(action: handleModalAutoFetchIntel) {
                        HStack(spacing: 4) {
                            if isSearchingIntel {
                                ProgressView()
                                    .scaleEffect(0.7)
                                    .tint(.white)
                            } else {
                                Text("⚡")
                                    .font(.system(size: 11))
                            }
                            Text(isSearchingIntel ? "检索中" : "自动填情报")
                                .font(.system(size: 11, weight: .bold))
                        }
                        .foregroundColor(.white)
                        .padding(.horizontal, 11)
                        .padding(.vertical, 11)
                        .background(Theme.primaryOrange)
                        .cornerRadius(10)
                    }
                    .disabled(isSearchingIntel)
                }
            }
            
            // Type Chips
            VStack(alignment: .leading, spacing: 6) {
                Text("比赛类型")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Theme.textSecondary)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(raceTypes, id: \.id) { t in
                            let isSel = raceType == t.id || (t.id == "trail" && RaceIntelConstants.isTrail(raceType) && raceType != "ultra")
                            Button(action: {
                                raceType = t.id
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            }) {
                                HStack(spacing: 4) {
                                    Text(t.icon)
                                    Text(t.name)
                                        .font(.system(size: 12, weight: isSel ? .bold : .medium))
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 8)
                                .background(isSel ? Theme.brandFill : Theme.surfaceSecondary)
                                .foregroundColor(isSel ? Theme.onBrand : Theme.textSecondary)
                                .cornerRadius(8)
                            }
                        }
                    }
                }
            }
            
            // Date Picker
            VStack(alignment: .leading, spacing: 6) {
                Text("比赛日期")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Theme.textSecondary)
                HStack {
                    DatePicker("比赛日期", selection: $raceDate, displayedComponents: .date)
                        .datePickerStyle(.compact)
                        .labelsHidden()
                        .colorScheme(Theme.isLight ? .light : .dark)
                    
                    Spacer()
                    
                    let formatter = DateFormatter()
                    let _ = formatter.dateFormat = "yyyy-MM-dd"
                    Text(formatter.string(from: raceDate))
                        .font(.system(size: 13, weight: .semibold, design: .monospaced))
                        .foregroundColor(Theme.primaryOrange)
                }
                .padding(10)
                .background(Theme.surfaceSecondary)
                .cornerRadius(10)
            }
            
            // Target Time
            VStack(alignment: .leading, spacing: 6) {
                Text("目标完赛时间 (HH:MM:SS)")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(Theme.textSecondary)
                TextField("例如：03:30:00 或 08:00:00", text: $targetTime)
                    .font(.system(size: 14, design: .monospaced))
                    .padding(12)
                    .background(Theme.surfaceSecondary)
                    .cornerRadius(10)
                    .foregroundColor(Theme.textPrimary)
                
                // Quick Target Chips
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(quickTargets, id: \.self) { qt in
                            Button(action: {
                                targetTime = qt
                                UIImpactFeedbackGenerator(style: .light).impactOccurred()
                            }) {
                                Text(qt)
                                    .font(.system(size: 11, design: .monospaced))
                                    .foregroundColor(targetTime == qt ? Theme.primaryOrange : Theme.textMuted)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(targetTime == qt ? Theme.primaryOrange.opacity(0.15) : Theme.surfaceSecondary)
                                    .cornerRadius(6)
                            }
                        }
                    }
                }
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private var priorityCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("🎯 赛事定位分级 (Canova A/B/C)")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Spacer()
            }
            
            HStack(spacing: 8) {
                ForEach([
                    (1, "A 标 (核心突破)", Color(hex: "F43F5E")),
                    (2, "B 标 (以赛代练)", Theme.accentYellow),
                    (3, "C 标 (模拟拉练)", Theme.accentBlue)
                ], id: \.0) { tier, label, color in
                    let isSel = priority == tier
                    Button(action: {
                        priority = tier
                        UIImpactFeedbackGenerator(style: .light).impactOccurred()
                    }) {
                        Text(label)
                            .font(.system(size: 11, weight: isSel ? .bold : .medium))
                            .foregroundColor(isSel ? .white : Theme.textSecondary)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 10)
                            .background(isSel ? color : Theme.surfaceSecondary)
                            .cornerRadius(8)
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("🏁 赛事状态与完赛回填")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundColor(Theme.textPrimary)
                Spacer()
            }
            
            HStack(spacing: 8) {
                Button(action: { isCompleted = false }) {
                    Text("🟢 备战中 (Upcoming)")
                        .font(.system(size: 12, weight: !isCompleted ? .bold : .medium))
                        .foregroundColor(!isCompleted ? .white : Theme.textSecondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(!isCompleted ? Theme.primaryOrange : Theme.surfaceSecondary)
                        .cornerRadius(8)
                }
                .buttonStyle(PlainButtonStyle())
                
                Button(action: { isCompleted = true }) {
                    Text("🏅 已完赛 (Completed)")
                        .font(.system(size: 12, weight: isCompleted ? .bold : .medium))
                        .foregroundColor(isCompleted ? .white : Theme.textSecondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(isCompleted ? Theme.accentGreen : Theme.surfaceSecondary)
                        .cornerRadius(8)
                }
                .buttonStyle(PlainButtonStyle())
            }
            
            if isCompleted {
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("🏅 完赛成绩与记录回填")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundColor(Theme.accentGreen)
                        Spacer()
                        Button(action: handleMatchWatchActivity) {
                            HStack(spacing: 4) {
                                if isMatchingActivity {
                                    ProgressView()
                                        .scaleEffect(0.65)
                                        .tint(Theme.accentGreen)
                                } else {
                                    Text("⚡")
                                        .font(.system(size: 10))
                                }
                                Text(isMatchingActivity ? "正在匹配..." : "从手表记录一键提取")
                                    .font(.system(size: 10, weight: .bold))
                            }
                            .foregroundColor(Theme.accentGreen)
                            .padding(.horizontal, 9)
                            .padding(.vertical, 5)
                            .background(Theme.accentGreen.opacity(0.15))
                            .cornerRadius(6)
                        }
                        .buttonStyle(PlainButtonStyle())
                        .disabled(isMatchingActivity)
                    }
                    
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text("实际完成时间 (HH:MM:SS)")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(Theme.textSecondary)
                            Spacer()
                            if let diff = calculatedDiff {
                                Text("\(diff.badge) \(diff.diffText)")
                                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                                    .foregroundColor(diff.isFaster ? Theme.accentGreen : Theme.primaryOrange)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background((diff.isFaster ? Theme.accentGreen : Theme.primaryOrange).opacity(0.14))
                                    .cornerRadius(4)
                            }
                        }
                        TextField("如: 3:24:15 或 08:12:00", text: $finishTime)
                            .font(.system(size: 14, design: .monospaced))
                            .padding(12)
                            .background(Theme.surfaceSecondary)
                            .cornerRadius(10)
                            .foregroundColor(Theme.textPrimary)
                    }
                    
                    VStack(alignment: .leading, spacing: 6) {
                        Text("完赛心得 / 感言")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(Theme.textSecondary)
                        TextField("如: 补给充分，下坡控速理想，超额达成目标！", text: $finishNotes)
                            .font(.system(size: 13))
                            .padding(12)
                            .background(Theme.surfaceSecondary)
                            .cornerRadius(10)
                            .foregroundColor(Theme.textPrimary)
                    }
                    
                    // Finisher Photos Section
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("完赛照片 / 证书 / 奖牌")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(Theme.textSecondary)
                            Spacer()
                            PhotosPicker(selection: $selectedPhotoItem, matching: .images) {
                                HStack(spacing: 4) {
                                    if isUploadingPhoto {
                                        ProgressView()
                                            .scaleEffect(0.65)
                                            .tint(Theme.primaryOrange)
                                    } else {
                                        Text("📷")
                                            .font(.system(size: 10))
                                    }
                                    Text(isUploadingPhoto ? "上传中..." : "上传照片")
                                        .font(.system(size: 11, weight: .bold))
                                }
                                .foregroundColor(Theme.primaryOrange)
                                .padding(.horizontal, 9)
                                .padding(.vertical, 5)
                                .background(Theme.primaryOrange.opacity(0.14))
                                .cornerRadius(6)
                            }
                            .disabled(isUploadingPhoto)
                        }
                        
                        if !photos.isEmpty {
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 10) {
                                    ForEach(photos, id: \.self) { pUrl in
                                        ZStack(alignment: .topTrailing) {
                                            if let u = URL(string: pUrl) {
                                                AsyncImage(url: u) { phase in
                                                    if case .success(let img) = phase {
                                                        img.resizable()
                                                            .scaledToFill()
                                                            .frame(width: 68, height: 68)
                                                            .clipShape(RoundedRectangle(cornerRadius: 8))
                                                    } else {
                                                        RoundedRectangle(cornerRadius: 8)
                                                            .fill(Theme.surfaceSecondary)
                                                            .frame(width: 68, height: 68)
                                                    }
                                                }
                                            }
                                            Button(action: {
                                                handleRemovePhoto(pUrl)
                                            }) {
                                                Image(systemName: "xmark.circle.fill")
                                                    .font(.system(size: 16))
                                                    .foregroundColor(.red)
                                                    .background(Circle().fill(Color.white))
                                            }
                                            .offset(x: 4, y: -4)
                                        }
                                    }
                                }
                                .padding(.vertical, 4)
                            }
                        } else {
                            Text("暂无照片，点击右上方「📷 上传照片」添加成绩证书、奖牌或冲线照")
                                .font(.system(size: 11))
                                .foregroundColor(Theme.textMuted)
                                .padding(10)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(Theme.surfaceSecondary)
                                .cornerRadius(8)
                        }
                    }
                }
                .padding(.top, 4)
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private var raceIntelCard: some View {
        let isTrail = RaceIntelConstants.isTrail(raceType)
        return VStack(alignment: .leading, spacing: 12) {
            Button(action: {
                withAnimation(.easeInOut(duration: 0.18)) {
                    expandRaceInfo.toggle()
                }
            }) {
                HStack {
                    Text("📋 \(isTrail ? "越野赛客观情报" : "公路赛客观情报") \(raceInfo.hasAnyValue ? "(已填录)" : "(点击填写)")")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                    Spacer()
                    Text(expandRaceInfo ? "▲" : "▼")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                }
            }
            .buttonStyle(PlainButtonStyle())
            
            if expandRaceInfo {
                RaceIntelFormView(
                    isTrail: isTrail,
                    info: $raceInfo,
                    showSaveButton: false
                )
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    private var deleteButton: some View {
        Button(action: {
            showDeleteAlert = true
        }) {
            HStack {
                if isDeleting {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .red))
                        .padding(.trailing, 6)
                }
                Image(systemName: "trash.fill")
                Text(isDeleting ? "正在删除..." : "删除此比赛计划")
                    .font(.system(size: 14, weight: .bold))
            }
            .foregroundColor(.red)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(Color.red.opacity(0.1))
            .cornerRadius(12)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.red.opacity(0.3), lineWidth: 1))
        }
        .disabled(isDeleting)
    }
    
    // MARK: - Actions
    
    private func handleModalAutoFetchIntel() {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            errorMessage = "请先输入比赛名称"
            return
        }
        errorMessage = nil
        isSearchingIntel = true
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let dateStr = formatter.string(from: raceDate)
        
        Task {
            do {
                let res = try await state.lookupRaceIntel(
                    raceName: trimmed,
                    raceType: raceType,
                    targetTime: targetTime,
                    raceDate: dateStr,
                    raceId: initialRace?.id
                )
                if res.success == true, let fetched = res.race_info {
                    raceInfo = fetched
                    if res.race_category == "trail" && !RaceIntelConstants.isTrail(raceType) {
                        raceType = "trail"
                    } else if res.race_category == "road" && RaceIntelConstants.isTrail(raceType) {
                        raceType = "road"
                    }
                    expandRaceInfo = true
                    statusNotice = "已自动填充官方赛事情报 ✓"
                } else {
                    errorMessage = res.message ?? "未检索到该赛事官方情报，请在下方手动填写"
                    expandRaceInfo = true
                }
            } catch {
                errorMessage = "检索失败，可手动填写赛事情报"
                expandRaceInfo = true
            }
            isSearchingIntel = false
        }
    }
    
    private func handleMatchWatchActivity() {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let dateStr = formatter.string(from: raceDate)
        isMatchingActivity = true
        errorMessage = nil
        
        Task {
            do {
                let res = try await state.matchRaceActivity(raceId: raceId, raceDate: dateStr)
                if res.matched == true, let act = res.activity {
                    isCompleted = true
                    if let ft = act.formatted_time, !ft.isEmpty {
                        finishTime = ft
                    }
                    if finishNotes.isEmpty {
                        let distStr = act.distance_km.map { String(format: "%.1fkm", $0) } ?? ""
                        let paceStr = act.avg_pace_str.map { ", 配速 \($0)" } ?? ""
                        finishNotes = "匹配手表记录【\(act.name ?? "跑步")】(\(distStr)\(paceStr))"
                    }
                    statusNotice = "已匹配手表完赛记录: \(act.formatted_time ?? "") ✓"
                } else {
                    errorMessage = res.message ?? "未在比赛日(±1天)找到匹配的手表运动记录"
                }
            } catch {
                errorMessage = "匹配失败: \(error.localizedDescription)"
            }
            isMatchingActivity = false
        }
    }
    
    private func handleUploadSelectedPhoto(_ item: PhotosPickerItem) async {
        isUploadingPhoto = true
        errorMessage = nil
        defer {
            isUploadingPhoto = false
            selectedPhotoItem = nil
        }
        do {
            guard let data = try await item.loadTransferable(type: Data.self) else { return }
            let compressed: Data
            if let uiImg = UIImage(data: data), let jpeg = uiImg.jpegData(compressionQuality: 0.72) {
                compressed = jpeg
            } else {
                compressed = data
            }
            let res = try await state.uploadRacePhoto(raceId: raceId, imageData: compressed)
            if !res.photos.isEmpty {
                photos = res.photos
            } else if let url = res.photoUrl, !url.isEmpty, !photos.contains(url) {
                photos.append(url)
            }
            statusNotice = "完赛照片上传成功 📸"
        } catch {
            errorMessage = "上传照片失败: \(error.localizedDescription)"
        }
    }
    
    private func handleRemovePhoto(_ url: String) {
        photos.removeAll { $0 == url }
        if isEditMode, !raceId.isEmpty {
            Task {
                _ = try? await state.deleteRacePhoto(raceId: raceId, photoUrl: url)
            }
        }
    }
    
    private func handleSave() {
        let trimmedName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedName.isEmpty else { return }
        
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let dateStr = formatter.string(from: raceDate)
        
        var payload: [String: Any] = [
            "name": trimmedName,
            "race_type": raceType,
            "race_date": dateStr,
            "target_time": targetTime.trimmingCharacters(in: .whitespacesAndNewlines),
            "priority": priority,
            "status": isCompleted ? "completed" : "upcoming",
            "race_info": raceInfo.toDictionary()
        ]
        
        if !raceId.isEmpty {
            payload["id"] = raceId
        }
        
        if isCompleted {
            let ft = finishTime.trimmingCharacters(in: .whitespacesAndNewlines)
            if !ft.isEmpty {
                payload["finish_time"] = ft
            }
            let fn = finishNotes.trimmingCharacters(in: .whitespacesAndNewlines)
            if !fn.isEmpty {
                payload["finish_notes"] = fn
            }
            if !photos.isEmpty {
                payload["photos"] = photos
                payload["photo_url"] = photos.first
            }
        }
        
        isSaving = true
        errorMessage = nil
        
        Task {
            do {
                try await state.saveRace(payload)
                UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                onSave?()
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
                isSaving = false
            }
        }
    }
    
    private func handleDelete() {
        guard let rId = initialRace?.id else { return }
        isDeleting = true
        Task {
            do {
                try await state.deleteRace(raceId: rId)
                UIImpactFeedbackGenerator(style: .medium).impactOccurred()
                onDelete?()
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
                isDeleting = false
            }
        }
    }
    
    private func parseTimeToSeconds(_ tStr: String) -> Int? {
        let parts = tStr.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: ":").compactMap { Int($0) }
        if parts.count == 3 {
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        } else if parts.count == 2 {
            return parts[0] * 60 + parts[1]
        }
        return nil
    }
    
    private func formatSecondsToTime(_ sec: Int) -> String {
        let h = sec / 3600
        let m = (sec % 3600) / 60
        let s = sec % 60
        if h > 0 {
            return String(format: "%d:%02d:%02d", h, m, s)
        }
        return String(format: "%02d:%02d", m, s)
    }
}

// MARK: - Manual Help Sheet View
struct ManualHelpSheet: View {
    @Environment(\.presentationMode) var presentationMode
    
    var body: some View {
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()
                
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("📖 新用户入门与操作手册")
                            .font(.system(size: 18, weight: .bold))
                            .foregroundColor(Theme.textPrimary)
                        
                        helpSection(
                            title: "1. 运动手表连接与跑步数据同步",
                            desc: "在【手表连接与账号】中选择您佩戴的运动手表（佳明 Garmin、高驰 COROS 或 Apple Watch）完成连接后，点击【同步最新跑步记录】即可自动同步跑步记录、心率、步频与完整 GPS 路线轨迹。"
                        )
                        
                        helpSection(
                            title: "2. 数据安全与隐私",
                            desc: "授权后，跑步记录与静息心率、HRV、睡眠等健康数据经加密传输保存至 RGM 服务器，仅用于计算您的训练负荷 (Banister CTL/ATL/TSB)、跑力预测与 AI 教练分析，不会用于广告，也不会分享给任何第三方。您可随时在【我的】中注销账号，所有数据将被永久删除。"
                        )
                        
                        helpSection(
                            title: "3. 科学依据与医学免责声明",
                            desc: "基于世界名帅 Renato Canova 专项化耐力训练理论，结合 Daniels 跑力模型 (VDOT) 提供个性化训练分析。所有运动与生理健康指标均附有权威医学与运动生理学学术文献索引（可随时查阅《科学依据与引用文献》）。"
                        )
                        
                        helpSection(
                            title: "4. 个人跑量与赛事目标设定",
                            desc: "在【训练档案与赛事】中可设定您的周跑量/月跑量目标、更新历史个人最佳成绩 (PB)，并添加即将参与的马拉松或越野赛目标。"
                        )
                    }
                    .padding(20)
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("完成") {
                        presentationMode.wrappedValue.dismiss()
                    }
                    .foregroundColor(Theme.primaryOrange)
                }
            }
        }
    }
    
    private func helpSection(title: String, desc: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(Theme.primaryOrange)
            Text(desc)
                .font(.system(size: 12))
                .foregroundColor(Theme.textSecondary)
                .lineSpacing(4)
        }
        .padding(14)
        .background(Theme.surface)
        .cornerRadius(12)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
    }
}

// MARK: - Edit Profile Sheet
struct EditProfileSheet: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) var dismiss
    
    var onSaved: (() -> Void)? = nil
    
    @State private var displayName: String = ""
    @State private var avatarUrl: String = ""
    @State private var gender: String = "male"
    @State private var dob: String = "1990-01-01"
    @State private var yearsRunningStr: String = "3"
    @State private var heightStr: String = "175"
    @State private var weightStr: String = "65"
    @State private var bio: String = ""
    
    @State private var isCustomAvatarUrl: Bool = false
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    
    // Preset athletic avatars
    private let presetAvatars: [(title: String, url: String)] = [
        ("速度飞人", "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?w=150&auto=format&fit=crop&q=80"),
        ("马拉松者", "https://images.unsplash.com/photo-1530549387789-4c1017266635?w=150&auto=format&fit=crop&q=80"),
        ("越野健将", "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=150&auto=format&fit=crop&q=80"),
        ("晨跑先锋", "https://images.unsplash.com/photo-1486218119243-13883505764c?w=150&auto=format&fit=crop&q=80"),
        ("夜跑星芒", "https://images.unsplash.com/photo-1502680390469-be75c86b636f?w=150&auto=format&fit=crop&q=80"),
        ("耐力领航", "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80")
    ]
    
    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            
            VStack(spacing: 0) {
                // Header Bar
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("✏️ 修改跑者资料")
                            .font(.system(size: 18, weight: .bold))
                            .foregroundColor(Theme.textPrimary)
                        Text("更新跑者昵称、头像与基本运动档案")
                            .font(.system(size: 12))
                            .foregroundColor(Theme.textMuted)
                    }
                    Spacer()
                    Button(action: { dismiss() }) {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 24))
                            .foregroundColor(Theme.textMuted)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 20)
                .padding(.bottom, 12)
                
                ScrollView {
                    VStack(spacing: 18) {
                        // 1. Avatar Section
                        avatarSection
                        
                        // 2. Basic Info Card
                        basicInfoCard
                        
                        // 3. Athletic Profile Card
                        athleticProfileCard
                        
                        // Error message
                        if let err = errorMessage {
                            HStack(spacing: 6) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .foregroundColor(Color(hex: "F43F5E"))
                                Text(err)
                                    .font(.system(size: 12))
                                    .foregroundColor(Color(hex: "F43F5E"))
                            }
                            .padding(.horizontal, 4)
                        }
                        
                        // Save Button
                        saveButton
                            .padding(.top, 4)
                            .padding(.bottom, 30)
                    }
                    .padding(.horizontal, 20)
                }
            }
        }
        .onAppear {
            initData()
        }
    }
    
    private func initData() {
        let p = state.fullProfile
        displayName = p?.display_name ?? state.currentUser?.displayName ?? ""
        avatarUrl = p?.avatar_url ?? state.currentUser?.avatar_url ?? ""
        gender = p?.gender ?? "male"
        dob = p?.date_of_birth ?? "1990-01-01"
        if let yrs = p?.years_running {
            yearsRunningStr = "\(yrs)"
        }
        if let h = p?.height_cm {
            heightStr = String(format: "%.0f", h)
        }
        if let w = p?.weight_kg {
            weightStr = String(format: "%.0f", w)
        }
        bio = p?.bio ?? ""
        
        // Check if current avatar is one of the presets
        if !avatarUrl.isEmpty && !presetAvatars.contains(where: { $0.url == avatarUrl }) {
            isCustomAvatarUrl = true
        }
    }
    
    // MARK: - Avatar Section
    private var avatarSection: some View {
        VStack(spacing: 14) {
            // Large Avatar Preview
            ZStack {
                Circle()
                    .fill(Theme.surfaceSecondary)
                    .frame(width: 80, height: 80)
                
                if let url = URL(string: avatarUrl), !avatarUrl.isEmpty {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let img):
                            img.resizable()
                                .aspectRatio(contentMode: .fill)
                                .frame(width: 80, height: 80)
                                .clipShape(Circle())
                        default:
                            Text("🏃").font(.system(size: 38))
                        }
                    }
                } else {
                    Text("🏃").font(.system(size: 38))
                }
            }
            .overlay(Circle().stroke(Theme.primaryOrange, lineWidth: 2))
            .shadow(color: Theme.primaryOrange.opacity(0.2), radius: 6, x: 0, y: 2)
            
            Text("选择跑者头像")
                .font(.system(size: 13, weight: .semibold))
                .foregroundColor(Theme.textPrimary)
            
            // Preset Avatars Row
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(presetAvatars, id: \.url) { item in
                        Button(action: {
                            avatarUrl = item.url
                            isCustomAvatarUrl = false
                        }) {
                            VStack(spacing: 4) {
                                ZStack {
                                    Circle()
                                        .fill(Theme.surfaceSecondary)
                                        .frame(width: 50, height: 50)
                                    
                                    if let url = URL(string: item.url) {
                                        AsyncImage(url: url) { phase in
                                            switch phase {
                                            case .success(let img):
                                                img.resizable()
                                                    .aspectRatio(contentMode: .fill)
                                                    .frame(width: 50, height: 50)
                                                    .clipShape(Circle())
                                            default:
                                                Text("🏃").font(.system(size: 22))
                                            }
                                        }
                                    }
                                }
                                .overlay(
                                    Circle()
                                        .stroke(avatarUrl == item.url ? Theme.primaryOrange : Color.clear, lineWidth: 2.5)
                                )
                                
                                Text(item.title)
                                    .font(.system(size: 10))
                                    .foregroundColor(avatarUrl == item.url ? Theme.primaryOrange : Theme.textMuted)
                            }
                        }
                        .buttonStyle(PlainButtonStyle())
                    }
                }
                .padding(.horizontal, 2)
            }
            
            // Custom Avatar Toggle & URL input
            VStack(alignment: .leading, spacing: 6) {
                Button(action: {
                    withAnimation {
                        isCustomAvatarUrl.toggle()
                    }
                }) {
                    HStack(spacing: 6) {
                        Image(systemName: isCustomAvatarUrl ? "link.circle.fill" : "link.circle")
                            .foregroundColor(Theme.primaryOrange)
                        Text(isCustomAvatarUrl ? "收起自定义图片链接" : "输入自定义头像图片链接 (URL)")
                            .font(.system(size: 11, weight: .medium))
                            .foregroundColor(Theme.primaryOrange)
                    }
                }
                
                if isCustomAvatarUrl {
                    HStack {
                        TextField("https://example.com/avatar.jpg", text: $avatarUrl)
                            .font(.system(size: 12, design: .monospaced))
                            .foregroundColor(Theme.textPrimary)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                        
                        if !avatarUrl.isEmpty {
                            Button(action: { avatarUrl = "" }) {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundColor(Theme.textMuted)
                            }
                        }
                    }
                    .padding(10)
                    .background(Theme.surfaceSecondary)
                    .cornerRadius(8)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.border, lineWidth: 1))
                }
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    // MARK: - Basic Info Card
    private var basicInfoCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("基础信息")
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(Theme.textPrimary)
            
            // Display Name
            VStack(alignment: .leading, spacing: 6) {
                Text("跑者昵称")
                    .font(.system(size: 12))
                    .foregroundColor(Theme.textMuted)
                
                TextField("请输入跑者昵称", text: $displayName)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(Theme.textPrimary)
                    .padding(12)
                    .background(Theme.surfaceSecondary)
                    .cornerRadius(10)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.border, lineWidth: 1))
            }
            
            // Gender
            VStack(alignment: .leading, spacing: 6) {
                Text("性别")
                    .font(.system(size: 12))
                    .foregroundColor(Theme.textMuted)
                
                HStack(spacing: 12) {
                    Button(action: { gender = "male" }) {
                        HStack(spacing: 6) {
                            Image(systemName: gender == "male" ? "checkmark.circle.fill" : "circle")
                                .foregroundColor(gender == "male" ? Theme.primaryOrange : Theme.textMuted)
                            Text("男 (Male)")
                                .font(.system(size: 13, weight: .medium))
                                .foregroundColor(gender == "male" ? Theme.textPrimary : Theme.textMuted)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(gender == "male" ? Theme.primaryOrange.opacity(0.12) : Theme.surfaceSecondary)
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(gender == "male" ? Theme.primaryOrange : Theme.border, lineWidth: 1))
                    }
                    .buttonStyle(PlainButtonStyle())
                    
                    Button(action: { gender = "female" }) {
                        HStack(spacing: 6) {
                            Image(systemName: gender == "female" ? "checkmark.circle.fill" : "circle")
                                .foregroundColor(gender == "female" ? Theme.primaryOrange : Theme.textMuted)
                            Text("女 (Female)")
                                .font(.system(size: 13, weight: .medium))
                                .foregroundColor(gender == "female" ? Theme.textPrimary : Theme.textMuted)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(gender == "female" ? Theme.primaryOrange.opacity(0.12) : Theme.surfaceSecondary)
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(gender == "female" ? Theme.primaryOrange : Theme.border, lineWidth: 1))
                    }
                    .buttonStyle(PlainButtonStyle())
                }
            }
            
            // Bio
            VStack(alignment: .leading, spacing: 6) {
                Text("跑者宣言 / 个性签名")
                    .font(.system(size: 12))
                    .foregroundColor(Theme.textMuted)
                
                TextField("如：跑无止境，每一次迈步都是超越", text: $bio)
                    .font(.system(size: 13))
                    .foregroundColor(Theme.textPrimary)
                    .padding(12)
                    .background(Theme.surfaceSecondary)
                    .cornerRadius(10)
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.border, lineWidth: 1))
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    // MARK: - Athletic Profile Card
    private var athleticProfileCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("运动与身体档案")
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(Theme.textPrimary)
            
            // Date of birth & Years running
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("出生日期 (YYYY-MM-DD)")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                    
                    TextField("1990-01-01", text: $dob)
                        .font(.system(size: 13, design: .monospaced))
                        .foregroundColor(Theme.textPrimary)
                        .keyboardType(.numbersAndPunctuation)
                        .padding(10)
                        .background(Theme.surfaceSecondary)
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.border, lineWidth: 1))
                }
                
                VStack(alignment: .leading, spacing: 6) {
                    Text("跑龄 (年)")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                    
                    TextField("3", text: $yearsRunningStr)
                        .font(.system(size: 13, design: .monospaced))
                        .foregroundColor(Theme.textPrimary)
                        .keyboardType(.numberPad)
                        .padding(10)
                        .background(Theme.surfaceSecondary)
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.border, lineWidth: 1))
                }
            }
            
            // Height & Weight
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("身高 (cm)")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                    
                    TextField("175", text: $heightStr)
                        .font(.system(size: 13, design: .monospaced))
                        .foregroundColor(Theme.textPrimary)
                        .keyboardType(.decimalPad)
                        .padding(10)
                        .background(Theme.surfaceSecondary)
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.border, lineWidth: 1))
                }
                
                VStack(alignment: .leading, spacing: 6) {
                    Text("体重 (kg)")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.textMuted)
                    
                    TextField("65", text: $weightStr)
                        .font(.system(size: 13, design: .monospaced))
                        .foregroundColor(Theme.textPrimary)
                        .keyboardType(.decimalPad)
                        .padding(10)
                        .background(Theme.surfaceSecondary)
                        .cornerRadius(8)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.border, lineWidth: 1))
                }
            }
        }
        .padding(16)
        .background(Theme.surface)
        .cornerRadius(14)
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.border, lineWidth: 1))
    }
    
    // MARK: - Save Button
    private var saveButton: some View {
        Button(action: handleSave) {
            HStack {
                if isLoading {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: Theme.onBrand))
                        .padding(.trailing, 6)
                }
                Text(isLoading ? "正在保存中..." : "保存修改")
                    .font(.system(size: 15, weight: .bold))
            }
            .foregroundColor(displayName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? .white : Theme.onBrand)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(displayName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? Color.gray.opacity(0.4) : Theme.brandFill)
            .cornerRadius(12)
        }
        .disabled(displayName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)
    }
    
    private func handleSave() {
        let name = displayName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else {
            errorMessage = "跑者昵称不能为空"
            return
        }
        
        isLoading = true
        errorMessage = nil
        
        var dict: [String: Any] = [
            "display_name": name,
            "gender": gender,
            "date_of_birth": dob,
            "bio": bio.trimmingCharacters(in: .whitespacesAndNewlines)
        ]
        let trimmedAvatar = avatarUrl.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedAvatar.isEmpty {
            dict["avatar_url"] = trimmedAvatar
        }
        if let yr = Int(yearsRunningStr.trimmingCharacters(in: .whitespacesAndNewlines)) {
            dict["years_running"] = yr
        }
        if let h = Double(heightStr.trimmingCharacters(in: .whitespacesAndNewlines)) {
            dict["height_cm"] = h
        }
        if let w = Double(weightStr.trimmingCharacters(in: .whitespacesAndNewlines)) {
            dict["weight_kg"] = w
        }
        
        Task {
            do {
                try await state.updateFullProfile(dict)
                await state.refreshData()
                onSaved?()
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }
}


