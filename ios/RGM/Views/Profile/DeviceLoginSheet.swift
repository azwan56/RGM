import SwiftUI
import UniformTypeIdentifiers

struct DeviceLoginSheet: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var state: AppState
    
    var initialBrand: String = "garmin"
    var onSuccess: ((String) -> Void)? = nil
    
    @State private var brand: String = "garmin"
    @State private var account: String = ""
    @State private var password: String = ""
    @State private var garminDomain: String = "garmin.cn"
    @State private var corosDomain: String = "teamcnapi.coros.com"
    
    // MFA / 2FA verification code state
    @State private var needsMFA: Bool = false
    @State private var mfaPrompt: String? = nil
    @State private var mfaCode: String = ""
    
    @State private var isLoading: Bool = false
    @State private var errorMessage: String?
    @State private var showFileImporter: Bool = false
    
    var body: some View {
        NavigationView {
            ZStack {
                Theme.background.ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: 18) {
                        // Header text
                        VStack(alignment: .leading, spacing: 6) {
                            Text(state.isLoggedIn ? "连接与绑定运动手表" : "运动手表连接与登录")
                                .font(.system(size: 20, weight: .bold))
                                .foregroundColor(Theme.textPrimary)
                            Text("支持佳明 (Garmin)、高驰 (COROS) 与 Apple Watch 跑步数据、心率流及 GPS 轨迹自动同步。")
                                .font(.system(size: 13))
                                .foregroundColor(Theme.textSecondary)
                                .lineSpacing(2)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        
                        // 3-Brand Selector
                        VStack(alignment: .leading, spacing: 8) {
                            Text("选择运动手表品牌")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundColor(Theme.textMuted)
                            
                            VStack(spacing: 10) {
                                HStack(spacing: 10) {
                                    brandTabButton(id: "garmin", title: "Garmin 佳明", badge: "云端自动同步", color: Color(hex: "007AC3"))
                                    brandTabButton(id: "coros", title: "COROS 高驰", badge: "云端自动同步", color: Color(hex: "E60012"))
                                }
                                brandTabButton(id: "apple_watch", title: "Apple Watch", badge: "Apple 健康原生自动同步", color: Theme.accentGreen)
                            }
                        }
                        
                        if brand == "garmin" || brand == "coros" {
                            cloudCredentialSection
                        } else if brand == "apple_watch" {
                            appleWatchSection
                        }
                        
                        if let err = errorMessage {
                            Text(err)
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(.red)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        
                        Spacer()
                    }
                    .padding(20)
                }
            }
            .navigationBarTitle("连接运动手表", displayMode: .inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("关闭") { dismiss() }
                        .foregroundColor(Theme.textSecondary)
                }
            }
            .onAppear {
                brand = (initialBrand == "huawei") ? "garmin" : initialBrand
                prefillForBrand()
            }
        }
    }
    
    private func brandTabButton(id: String, title: String, badge: String, color: Color) -> some View {
        let isSelected = (brand == id)
        let otherConnected = state.isLoggedIn ? state.connectedWatchBrand() : nil
        let isLockedByOther = (otherConnected != nil && otherConnected?.id != id)
        return Button(action: {
            if let other = otherConnected, other.id != id {
                errorMessage = "每个账号仅限连接一个运动手表，请先在个人页解绑【\(other.label)】后再切换。"
                return
            }
            withAnimation(.easeInOut(duration: 0.15)) {
                brand = id
                needsMFA = false
                mfaCode = ""
                errorMessage = nil
                prefillForBrand()
            }
        }) {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                        .font(.system(size: 13, weight: .bold))
                        .foregroundColor(isSelected ? .white : Theme.textPrimary)
                    Text(isLockedByOther ? "需先解绑当前手表" : badge)
                        .font(.system(size: 10, weight: .medium))
                        .foregroundColor(isSelected ? .white.opacity(0.85) : Theme.textMuted)
                }
                Spacer()
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.white)
                        .font(.system(size: 14))
                } else if isLockedByOther {
                    Image(systemName: "lock.fill")
                        .foregroundColor(Theme.textMuted)
                        .font(.system(size: 12))
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(isSelected ? color : Theme.surfaceSecondary)
            .cornerRadius(10)
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isSelected ? color : Theme.border, lineWidth: 1)
            )
            .opacity(isLockedByOther ? 0.55 : 1.0)
        }
        .buttonStyle(PlainButtonStyle())
    }
    
    // MARK: - Garmin & COROS Cloud Credentials Section
    private var cloudCredentialSection: some View {
        VStack(spacing: 16) {
            if brand == "garmin" {
                VStack(alignment: .leading, spacing: 6) {
                    Text("佳明服务器区域")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(Theme.textMuted)
                    Picker("服务器", selection: $garminDomain) {
                        Text("中国区 (garmin.cn)").tag("garmin.cn")
                        Text("国际区 (garmin.com)").tag("garmin.com")
                    }
                    .pickerStyle(SegmentedPickerStyle())
                }
            } else {
                VStack(alignment: .leading, spacing: 6) {
                    Text("高驰服务器区域")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(Theme.textMuted)
                    Picker("服务器", selection: $corosDomain) {
                        Text("中国区 (coros.com)").tag("teamcnapi.coros.com")
                        Text("国际区 (Global)").tag("teamapi.coros.com")
                    }
                    .pickerStyle(SegmentedPickerStyle())
                }
            }
            
            VStack(spacing: 12) {
                TextField(brand == "garmin" ? "佳明账号 (注册邮箱)" : "高驰账号 (手机号或邮箱)", text: $account)
                    .textContentType(.username)
                    .keyboardType(.emailAddress)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .padding(12)
                    .background(Theme.surfaceSecondary)
                    .cornerRadius(10)
                    .foregroundColor(Theme.textPrimary)
                
                SecureField("账号密码", text: $password)
                    .textContentType(.password)
                    .padding(12)
                    .background(Theme.surfaceSecondary)
                    .cornerRadius(10)
                    .foregroundColor(Theme.textPrimary)
                
                if needsMFA {
                    VStack(alignment: .leading, spacing: 8) {
                        if let prompt = mfaPrompt {
                            Text(prompt)
                                .font(.system(size: 12, weight: .medium))
                                .foregroundColor(Theme.primaryOrange)
                        }
                        TextField("请输入 6 位安全验证码 (邮箱/短信)", text: $mfaCode)
                            .keyboardType(.numberPad)
                            .font(.system(size: 15, weight: .bold, design: .monospaced))
                            .padding(12)
                            .background(Theme.surfaceSecondary)
                            .cornerRadius(10)
                            .overlay(
                                RoundedRectangle(cornerRadius: 10)
                                    .stroke(Theme.primaryOrange.opacity(0.6), lineWidth: 1)
                            )
                            .foregroundColor(Theme.textPrimary)
                    }
                    .padding(.top, 4)
                }
            }
            
            Button(action: submitLogin) {
                HStack(spacing: 8) {
                    if isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: Theme.onBrand))
                            .scaleEffect(0.85)
                    } else {
                        Image(systemName: "link.badge.plus")
                            .font(.system(size: 14, weight: .bold))
                    }
                    Text(buttonTitle)
                        .font(.system(size: 15, weight: .bold))
                }
                .foregroundColor(Theme.onBrand)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Theme.brandFill)
                .cornerRadius(12)
            }
            .disabled(isLoading || account.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || password.isEmpty || (needsMFA && mfaCode.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty))
        }
    }
    
    // MARK: - Apple Watch Direct HealthKit Section
    private var appleWatchSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 6) {
                    Image(systemName: "applewatch.watchface")
                        .foregroundColor(Theme.accentGreen)
                    Text("Apple Watch 原生直连说明")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(Theme.textPrimary)
                }
                
                Text("Apple Watch「体能训练」记录的所有户外/室内跑步数据（包括高精 GPS 路线轨迹 HKWorkoutRoute、逐秒心率流、步频、海拔爬升、最大摄氧量 VO2Max、HRV 与睡眠）均已直接保存在 iPhone 的「Apple 健康」中，无需输入任何账号密码即可一键直连。")
                    .font(.system(size: 12))
                    .foregroundColor(Theme.textSecondary)
                    .lineSpacing(3)
            }
            .padding(14)
            .background(Theme.surfaceSecondary)
            .cornerRadius(12)
            
            Button(action: {
                connectViaHealthKit(watchBrand: "apple_watch")
            }) {
                HStack(spacing: 8) {
                    if isLoading {
                        ProgressView().tint(.white).scaleEffect(0.85)
                        Text("正在读取并同步 Apple Watch 数据...")
                    } else {
                        Image(systemName: "applewatch.radiowaves.left.and.right")
                        Text("授权连接 Apple Watch 并同步跑步与 GPS 轨迹")
                    }
                }
                .font(.system(size: 14, weight: .bold))
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Theme.accentGreen)
                .cornerRadius(12)
            }
            .disabled(isLoading)
        }
    }
    
    private var buttonTitle: String {
        if isLoading {
            return "正在官方服务器验证并同步..."
        }
        if needsMFA {
            return "提交验证码并完成绑定"
        }
        return state.isLoggedIn ? "确认绑定并同步历史数据" : "确认登录并同步数据"
    }
    
    private func prefillForBrand() {
        if brand == "garmin" {
            if let email = state.currentUser?.garmin_email, !email.isEmpty {
                account = email
            }
            if let dom = state.currentUser?.garmin_domain, !dom.isEmpty {
                garminDomain = dom
            }
        } else if brand == "coros" {
            if let acc = state.currentUser?.coros_account, !acc.isEmpty {
                account = acc
            }
            if let dom = state.currentUser?.coros_domain, !dom.isEmpty {
                corosDomain = dom
            }
        }
    }
    
    private func connectViaHealthKit(watchBrand: String) {
        guard state.isLoggedIn else {
            errorMessage = "请先使用 Apple 账号登录后，再连接 Apple Watch"
            return
        }
        isLoading = true
        errorMessage = nil
        Task {
            let ok = await state.syncHealthKit(watchBrand: watchBrand)
            isLoading = false
            if ok {
                let notice = (state.syncNotice ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                let msg = notice.isEmpty ? "设备已连接并完成数据同步 ✓" : notice
                onSuccess?(msg)
                dismiss()
            } else {
                errorMessage = state.syncNotice ?? "同步失败"
            }
        }
    }
    
    private func submitLogin() {
        isLoading = true
        errorMessage = nil
        Task {
            do {
                let domain = brand == "garmin" ? garminDomain : corosDomain
                let trimmedAccount = account.trimmingCharacters(in: .whitespacesAndNewlines)
                let trimmedCode = mfaCode.trimmingCharacters(in: .whitespacesAndNewlines)
                let msg = try await state.bindWatch(
                    brand: brand,
                    account: trimmedAccount,
                    password: password,
                    domain: domain,
                    mfaCode: needsMFA && !trimmedCode.isEmpty ? trimmedCode : nil
                )
                onSuccess?(msg)
                dismiss()
            } catch let APIError.mfaRequired(prompt) {
                needsMFA = true
                mfaPrompt = prompt
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }
}
