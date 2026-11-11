import SwiftUI
import UIKit

struct MainTabView: View {
    @EnvironmentObject var state: AppState
    
    init() {
        Self.applyTabBarAppearance(mode: Theme.current)
    }
    
    static func applyTabBarAppearance(mode: ThemeMode) {
        let appearance = UITabBarAppearance()
        appearance.configureWithDefaultBackground()
        
        let itemAppearance = UITabBarItemAppearance()
        if mode == .dark {
            appearance.backgroundColor = UIColor(Color(hex: "121214")).withAlphaComponent(0.95)
            let normalColor = UIColor(white: 0.55, alpha: 1.0)
            let selectedColor = UIColor(red: 252/255, green: 76/255, blue: 2/255, alpha: 1.0)
            itemAppearance.normal.iconColor = normalColor
            itemAppearance.normal.titleTextAttributes = [
                .foregroundColor: normalColor,
                .font: UIFont.systemFont(ofSize: 10, weight: .medium)
            ]
            itemAppearance.selected.iconColor = selectedColor
            itemAppearance.selected.titleTextAttributes = [
                .foregroundColor: selectedColor,
                .font: UIFont.systemFont(ofSize: 10, weight: .bold)
            ]
        } else {
            // Bright themes: Volt (经典竞技跑风) & Trail (户外越野风)
            appearance.backgroundColor = UIColor.white.withAlphaComponent(0.96)
            let normalColor = UIColor(Color(hex: "4B5667"))
            let selectedColor = mode == .volt
                ? UIColor(Color(hex: "111317"))
                : UIColor(Color(hex: "9A3412"))
            itemAppearance.normal.iconColor = normalColor
            itemAppearance.normal.titleTextAttributes = [
                .foregroundColor: normalColor,
                .font: UIFont.systemFont(ofSize: 10, weight: .medium)
            ]
            itemAppearance.selected.iconColor = selectedColor
            itemAppearance.selected.titleTextAttributes = [
                .foregroundColor: selectedColor,
                .font: UIFont.systemFont(ofSize: 10, weight: .heavy)
            ]
        }
        
        appearance.stackedLayoutAppearance = itemAppearance
        appearance.inlineLayoutAppearance = itemAppearance
        appearance.compactInlineLayoutAppearance = itemAppearance
        
        UITabBar.appearance().standardAppearance = appearance
        if #available(iOS 15.0, *) {
            UITabBar.appearance().scrollEdgeAppearance = appearance
        }
        
        // Immediately refresh any mounted UITabBar instances
        for scene in UIApplication.shared.connectedScenes {
            guard let windowScene = scene as? UIWindowScene else { continue }
            for window in windowScene.windows {
                updateTabBars(in: window, appearance: appearance)
            }
        }
    }
    
    private static func updateTabBars(in view: UIView, appearance: UITabBarAppearance) {
        if let tabBar = view as? UITabBar {
            tabBar.standardAppearance = appearance
            if #available(iOS 15.0, *) {
                tabBar.scrollEdgeAppearance = appearance
            }
        }
        for subview in view.subviews {
            updateTabBars(in: subview, appearance: appearance)
        }
    }
    
    var body: some View {
        TabView(selection: $state.selectedTab) {
            DashboardView()
                .tabItem {
                    Image(systemName: "gauge.with.dots.needle.bottom.50percent")
                    Text("看板")
                }
                .tag(0)
            
            // Tag 4 keeps existing selectedTab jumps (2 = 深度分析, 3 = 我的) valid
            RecoveryView()
                .tabItem {
                    Image(systemName: "heart.circle.fill")
                    Text("恢复")
                }
                .tag(4)
            
            CoachView()
                .tabItem {
                    Image(systemName: "brain.head.profile")
                    Text("AI教练")
                }
                .tag(1)
            
            AnalysisView()
                .tabItem {
                    Image(systemName: "chart.xyaxis.line")
                    Text("深度分析")
                }
                .tag(2)
            
            ProfileView()
                .tabItem {
                    Image(systemName: "person.crop.circle.fill")
                    Text("我的")
                }
                .tag(3)
        }
        .id(state.themeMode)
        .accentColor(state.themeMode == .volt ? Color(hex: "111317") : Theme.primaryOrange)
        .onChange(of: state.themeMode) { newMode in
            Self.applyTabBarAppearance(mode: newMode)
        }
        .task {
            await state.refreshData()
        }
    }
}
