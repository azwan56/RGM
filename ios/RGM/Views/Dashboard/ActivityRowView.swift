import SwiftUI

struct ActivityRowView: View {
    let activity: ActivityItem
    var onTapTrack: (() -> Void)? = nil
    
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Header: Name + Elevation Gain + Date
            HStack {
                HStack(spacing: 6) {
                    Image(systemName: "figure.run")
                        .foregroundColor(Theme.primaryOrange)
                        .font(.system(size: 14, weight: .bold))
                    Text(activity.name)
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundColor(Theme.textPrimary)
                    
                    if let elev = activity.elevation_gain_meters, elev > 0 {
                        Text("⛰️ +\(Int(elev))m")
                            .font(.system(size: 10))
                            .foregroundColor(Theme.textMuted)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 2)
                            .background(Theme.surfaceSecondary)
                            .cornerRadius(4)
                    }
                }
                Spacer()
                Text(formattedDate(activity.start_time))
                    .font(.system(size: 12))
                    .foregroundColor(Theme.textMuted)
            }
            
            // 4 Stats Columns: Distance, Pace, Duration, TRIMP/HR
            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(String(format: "%.2f", activity.distanceKm))
                        .font(.system(size: 20, weight: .black, design: .rounded))
                        .foregroundColor(Theme.primaryOrange)
                    Text("跑步距离 (km)")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
                
                VStack(alignment: .leading, spacing: 2) {
                    Text(activity.avg_pace_str ?? "--:--")
                        .font(.system(size: 15, weight: .bold, design: .rounded))
                        .foregroundColor(Theme.textPrimary)
                    Text("平均配速")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
                
                VStack(alignment: .leading, spacing: 2) {
                    Text(activity.durationString)
                        .font(.system(size: 15, weight: .bold, design: .rounded))
                        .foregroundColor(Theme.textPrimary)
                    Text("运动时间")
                        .font(.system(size: 10))
                        .foregroundColor(Theme.textMuted)
                }
                
                if let hr = activity.average_heartrate, hr > 0 {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(hr)")
                            .font(.system(size: 15, weight: .bold, design: .rounded))
                            .foregroundColor(Theme.accentRose)
                        Text("平均心率")
                            .font(.system(size: 10))
                            .foregroundColor(Theme.textMuted)
                    }
                }
                
                if let trimp = activity.trimp, trimp > 0 {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(String(format: "%.1f", trimp))
                            .font(.system(size: 15, weight: .bold, design: .rounded))
                            .foregroundColor(Theme.accentYellow)
                        Text("TRIMP负荷")
                            .font(.system(size: 10))
                            .foregroundColor(Theme.textMuted)
                    }
                }
            }
            
            // Canova AI Journal Commentary
            if let ai = activity.ai_journal, !ai.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(spacing: 4) {
                        Text("🤖")
                            .font(.system(size: 12))
                        Text("Canova 专项训练评析")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundColor(Theme.primaryOrange)
                    }
                    Text(ai)
                        .font(.system(size: 12))
                        .foregroundColor(Theme.textSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(10)
                .background(Theme.surfaceSecondary)
                .cornerRadius(8)
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.border, lineWidth: 1))
            }
            
            // GPS Track interactive pill
            if activity.has_gps_track == true || activity.id.starts(with: "garmin_") {
                Button(action: {
                    onTapTrack?()
                }) {
                    HStack(spacing: 6) {
                        Text("🗺️")
                            .font(.system(size: 12))
                        Text("查看高精度 GPS 轨迹与海拔剖面")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundColor(Theme.primaryOrange)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(Theme.primaryOrange)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(Theme.brandTint)
                    .cornerRadius(8)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.primaryOrange.opacity(0.25), lineWidth: 1))
                }
                .buttonStyle(PlainButtonStyle())
                .padding(.top, 2)
            }
        }
        .contentShape(Rectangle())
        .onTapGesture {
            onTapTrack?()
        }
        .padding(14)
        .background(Theme.surface)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Theme.border, lineWidth: 1)
        )
    }
    
    private func formattedDate(_ str: String?) -> String {
        guard let str = str, str.count >= 16 else { return str ?? "--" }
        let idx = str.index(str.startIndex, offsetBy: 16)
        let s = String(str[..<idx]).replacingOccurrences(of: "T", with: " ")
        return s
    }
}
