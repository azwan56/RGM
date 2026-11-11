import SwiftUI
import UIKit

enum ThemeMode: String, CaseIterable, Identifiable {
    case dark = "dark" // 🌑 经典暗黑极客
    case volt = "volt" // ⚡ 经典竞技跑风 (荧光电绿 × 深炭灰 × 纯白底)
    
    var id: String { rawValue }
    
    var displayName: String {
        switch self {
        case .dark: return "经典暗黑极客"
        case .volt: return "经典竞技跑风"
        }
    }
    
    var badgeLabel: String {
        switch self {
        case .dark: return "🌑 经典暗黑极客"
        case .volt: return "⚡ 经典竞技跑风"
        }
    }
    
    var subtitle: String {
        switch self {
        case .dark: return "暗夜深黑底 × 烈焰竞速橙"
        case .volt: return "荧光电绿 × 深炭灰 × 纯白底"
        }
    }
}

enum Theme {
    private static let storageKey = "rgm_theme"
    
    static var current: ThemeMode = {
        if let saved = UserDefaults.standard.string(forKey: storageKey),
           let mode = ThemeMode(rawValue: saved) {
            return mode
        }
        return .volt
    }()
    
    static func setMode(_ mode: ThemeMode) {
        current = mode
        UserDefaults.standard.set(mode.rawValue, forKey: storageKey)
    }
    
    static var isLight: Bool {
        current == .volt
    }
    
    static var isVolt: Bool {
        current == .volt
    }
    
    // MARK: - Surface Hierarchy (Ported from miniapp/src/styles/theme.css)
    static var background: Color {
        switch current {
        case .dark: return Color(hex: "0A0A0C")
        case .volt: return Color(hex: "E8EAED")
        }
    }
    
    static var surface: Color {
        switch current {
        case .dark: return Color(hex: "141418")
        case .volt: return Color(hex: "FFFFFF")
        }
    }
    
    static var surfaceSecondary: Color {
        switch current {
        case .dark: return Color(hex: "1E1E24")
        case .volt: return Color(hex: "F4F5F7")
        }
    }
    
    static var surfaceTertiary: Color {
        switch current {
        case .dark: return Color(hex: "27272E")
        case .volt: return Color(hex: "E9ECEF")
        }
    }
    
    static var border: Color {
        switch current {
        case .dark: return Color(hex: "27272E")
        case .volt: return Color(hex: "E2E8F0")
        }
    }
    
    // MARK: - Brand & Semantic Colors
    /// Readable brand color for text, numbers, icons, and strokes on cards
    static var primaryOrange: Color {
        switch current {
        case .dark: return Color(hex: "FC4C02")
        case .volt: return Color(hex: "4D7C0F")
        }
    }
    
    /// Solid brand fill for buttons, active segmented tabs, and progress bars
    static var brandFill: Color {
        switch current {
        case .dark: return Color(hex: "FC4C02")
        case .volt: return Color(hex: "CCFF00")
        }
    }
    
    /// Gradient end color for brand buttons and progress bars
    static var brandGradientEnd: Color {
        switch current {
        case .dark: return Color(hex: "FF7A00")
        case .volt: return Color(hex: "B8E600")
        }
    }
    
    /// Foreground text/icon color on top of `brandFill`
    static var onBrand: Color {
        switch current {
        case .dark: return Color.white
        case .volt: return Color(hex: "111317")
        }
    }
    
    /// Soft brand tint for badges and highlights
    static var brandTint: Color {
        switch current {
        case .dark: return Color(hex: "FC4C02").opacity(0.15)
        case .volt: return Color(hex: "CCFF00").opacity(0.32)
        }
    }
    
    static var accentGreen: Color {
        switch current {
        case .dark: return Color(hex: "10B981")
        case .volt: return Color(hex: "166534")
        }
    }
    
    static var accentBlue: Color {
        switch current {
        case .dark: return Color(hex: "3B82F6")
        case .volt: return Color(hex: "0284C7")
        }
    }
    
    static var accentYellow: Color {
        switch current {
        case .dark: return Color(hex: "F59E0B")
        case .volt: return Color(hex: "B45309")
        }
    }
    
    static var accentRose: Color {
        switch current {
        case .dark: return Color(hex: "F43F5E")
        case .volt: return Color(hex: "DB2777")
        }
    }
    
    // MARK: - Typography Hierarchy
    static var textPrimary: Color {
        switch current {
        case .dark: return Color.white
        case .volt: return Color(hex: "111317")
        }
    }
    
    static var textSecondary: Color {
        switch current {
        case .dark: return Color(hex: "A1A1AA")
        case .volt: return Color(hex: "334155")
        }
    }
    
    static var textMuted: Color {
        switch current {
        case .dark: return Color(hex: "71717A")
        case .volt: return Color(hex: "4B5667")
        }
    }
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }

        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
