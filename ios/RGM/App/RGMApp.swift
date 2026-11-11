import SwiftUI

@main
struct RGMApp: App {
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var appState = AppState()
    @State private var isShowingCover: Bool = true
    
    var body: some Scene {
        WindowGroup {
            ZStack {
                MainTabView()
                    .environmentObject(appState)
                
                if isShowingCover {
                    AppCoverView()
                        .transition(.opacity)
                        .zIndex(999)
                }
            }
            .preferredColorScheme(appState.themeMode == .dark ? .dark : .light)
            .onAppear {
                // Show cover screen on startup and fade out smoothly
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) {
                    withAnimation(.easeInOut(duration: 0.5)) {
                        isShowingCover = false
                    }
                }
            }
            .onChange(of: scenePhase) { newPhase in
                if newPhase == .active {
                    Task {
                        await appState.onAppBecameActive()
                    }
                } else if newPhase == .background {
                    MorningBriefingManager.shared.scheduleBackgroundPrePushSync()
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .NSCalendarDayChanged)) { _ in
                Task {
                    await appState.onAppBecameActive(forceWatchSync: true)
                }
            }
        }
    }
}

// ════════════════════════════════════════════════════════════════════
// MARK: - App Cover / Splash Screen
// ════════════════════════════════════════════════════════════════════
struct AppCoverView: View {
    @State private var animateScale: Bool = false
    @State private var animateOpacity: Double = 0.0
    
    var body: some View {
        ZStack {
            // Background
            Theme.background.ignoresSafeArea()
            
            // Subtle Radial Gradient behind logo
            RadialGradient(
                gradient: Gradient(colors: [
                    Theme.primaryOrange.opacity(0.18),
                    Color.clear
                ]),
                center: .center,
                startRadius: 20,
                endRadius: 240
            )
            .ignoresSafeArea()
            
            VStack(spacing: 24) {
                Spacer()
                
                // Centered App Logo
                VStack(spacing: 16) {
                    Image("app_cover")
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: 180, height: 160)
                        .shadow(color: Theme.primaryOrange.opacity(0.3), radius: 20, x: 0, y: 8)
                    
                    VStack(spacing: 6) {
                        Text("科学耐力训练系统")
                            .font(.system(size: 16, weight: .bold))
                            .foregroundColor(Theme.textPrimary)
                            .tracking(2)
                        
                        Text("Renato Canova 周期训练法 · 智能配速矩阵")
                            .font(.system(size: 11, weight: .medium))
                            .foregroundColor(Theme.textMuted)
                            .tracking(1)
                    }
                }
                .scaleEffect(animateScale ? 1.0 : 0.92)
                .opacity(animateOpacity)
                
                Spacer()
                
                // Bottom Brand Badge
                VStack(spacing: 6) {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(Theme.accentGreen)
                            .frame(width: 6, height: 6)
                        Text("佳明 · 高驰官方数据直连服务")
                            .font(.system(size: 11))
                            .foregroundColor(Theme.textSecondary)
                    }
                    
                    Text("VANPOWER RUNNING GROUP MANAGEMENT © 2026")
                        .font(.system(size: 9, weight: .semibold, design: .monospaced))
                        .foregroundColor(Theme.textMuted.opacity(0.6))
                }
                .padding(.bottom, 36)
                .opacity(animateOpacity)
            }
        }
        .onAppear {
            withAnimation(.easeOut(duration: 0.6)) {
                animateScale = true
                animateOpacity = 1.0
            }
        }
    }
}
