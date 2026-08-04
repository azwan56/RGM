import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity,
  Linking,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { apiClient, backendUrl } from "../../services/api";
import { auth } from "../../services/firebase";
import { Flame, Compass, RefreshCw, Heart, Calendar } from "lucide-react-native";

interface Stats {
  total_distance_km: number;
  total_elevation_gain?: number;
  avg_pace: string;
  avg_heart_rate: number;
  goal_completion_percentage: number;
  run_count: number;
  period: "weekly" | "monthly";
  period_start: string | null;
  last_sync: string | null;
}

export default function DashboardScreen() {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  const user = auth.currentUser;

  const fetchDashboardData = useCallback(async () => {
    if (!user) return;
    try {
      setError("");
      const month = new Date().getMonth(); // 0-indexed
      const res = await apiClient.get(`/api/data/dashboard/${user.uid}`, {
        params: { period: "monthly", month },
      });
      setData(res.data);
    } catch (e: any) {
      console.error(e);
      setError("数据加载失败，请下拉重试");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user]);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchDashboardData();
  };

  const handleConnectStrava = () => {
    if (!user) return;
    // Direct user to connect Strava via backend web OAuth endpoint
    const url = `${backendUrl}/api/sync/strava/auth?uid=${user.uid}`;
    Linking.openURL(url).catch((err) => console.error("Couldn't load page", err));
  };

  if (loading) {
    return (
      <View className="flex-1 bg-neutral-950 items-center justify-center">
        <ActivityIndicator size="large" color="#3b82f6" />
      </View>
    );
  }

  const stats: Stats = data?.stats || {
    total_distance_km: 0,
    avg_pace: "—",
    avg_heart_rate: 0,
    goal_completion_percentage: 0,
    run_count: 0,
    period: "monthly",
    period_start: null,
    last_sync: null,
  };

  const activities = data?.activities?.activities || [];
  const stravaConnected = data?.strava_connected || false;
  const garminConnected = data?.garmin_connected || false;
  const isConnected = stravaConnected || garminConnected;

  const connectionLabel = (garminConnected && stravaConnected)
    ? "Garmin & Strava 已连接"
    : garminConnected
    ? "Garmin 已连接"
    : stravaConnected
    ? "Strava 已连接"
    : "未连接";

  const displayName = data?.display_name || user?.email?.split("@")[0] || "跑者";

  return (
    <SafeAreaView className="flex-1 bg-neutral-950" edges={["top"]}>
      <ScrollView
        contentContainerStyle={{ flexGrow: 1 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#3b82f6" />}
      >
        <View className="px-6 py-4 flex-1">
          {/* Header */}
          <View className="flex-row justify-between items-center mb-6">
            <View>
              <Text className="text-neutral-400 text-xs font-semibold uppercase tracking-wider">WELCOME BACK</Text>
              <Text className="text-white text-2xl font-bold">{displayName}</Text>
            </View>
            <View className="flex-row items-center">
              <View
                className={`h-2.5 w-2.5 rounded-full mr-2 ${
                  isConnected ? "bg-green-500 shadow-md shadow-green-500/50" : "bg-red-500"
                }`}
              />
              <Text className="text-xs font-semibold text-neutral-400">
                {connectionLabel}
              </Text>
            </View>
          </View>

          {/* Connect Call to Action */}
          {!isConnected ? (
            <View className="bg-orange-500/10 border border-orange-500/20 rounded-3xl p-5 mb-6">
              <Text className="text-orange-400 text-sm font-bold mb-1">同步跑步数据</Text>
              <Text className="text-neutral-400 text-xs mb-4 leading-4">
                连接您的 Strava 或 Garmin 佳明账号，系统将自动同步您的跑步距离、配速和心率，并在排行榜中与其他跑友竞争。
              </Text>
              <TouchableOpacity
                onPress={handleConnectStrava}
                className="bg-orange-600 active:bg-orange-700 py-3 px-4 rounded-xl items-center"
              >
                <Text className="text-white text-xs font-bold">连接 Strava 账号</Text>
              </TouchableOpacity>
            </View>
          ) : null}

          {error ? (
            <View className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 mb-6">
              <Text className="text-red-400 text-xs">{error}</Text>
            </View>
          ) : null}

          {/* Stats Section */}
          <Text className="text-white text-lg font-bold mb-4">本月运动状态</Text>
          <View className="flex-row flex-wrap justify-between mb-6">
            {/* Total Distance */}
            <View className="w-[48%] bg-neutral-900 border border-neutral-800 rounded-3xl p-4 mb-4">
              <View className="flex-row justify-between items-center mb-2">
                <Text className="text-neutral-400 text-xs">总跑量</Text>
                <Compass size={16} color="#3b82f6" />
              </View>
              <Text className="text-white text-2xl font-bold">{stats.total_distance_km.toFixed(1)} <Text className="text-xs font-normal">km</Text></Text>
              <View className="w-full bg-neutral-800 h-1.5 rounded-full mt-3 overflow-hidden">
                <View
                  style={{ width: `${Math.min(stats.goal_completion_percentage, 100)}%` }}
                  className="bg-blue-500 h-full rounded-full"
                />
              </View>
              <Text className="text-neutral-500 text-[10px] mt-1.5">目标完成率 {stats.goal_completion_percentage.toFixed(0)}%</Text>
            </View>

            {/* Run Count */}
            <View className="w-[48%] bg-neutral-900 border border-neutral-800 rounded-3xl p-4 mb-4">
              <View className="flex-row justify-between items-center mb-2">
                <Text className="text-neutral-400 text-xs">跑步次数</Text>
                <Flame size={16} color="#ef4444" />
              </View>
              <Text className="text-white text-2xl font-bold">{stats.run_count} <Text className="text-xs font-normal">次</Text></Text>
              <Text className="text-neutral-500 text-[10px] mt-6">坚持就是胜利！</Text>
            </View>

            {/* Average Pace */}
            <View className="w-[48%] bg-neutral-900 border border-neutral-800 rounded-3xl p-4">
              <View className="flex-row justify-between items-center mb-2">
                <Text className="text-neutral-400 text-xs">平均配速</Text>
                <RefreshCw size={16} color="#10b981" />
              </View>
              <Text className="text-white text-2xl font-bold">{stats.avg_pace}</Text>
              <Text className="text-neutral-500 text-[10px] mt-6">分/公里</Text>
            </View>

            {/* Average Heart Rate */}
            <View className="w-[48%] bg-neutral-900 border border-neutral-800 rounded-3xl p-4">
              <View className="flex-row justify-between items-center mb-2">
                <Text className="text-neutral-400 text-xs">平均心率</Text>
                <Heart size={16} color="#ec4899" />
              </View>
              <Text className="text-white text-2xl font-bold">
                {stats.avg_heart_rate > 0 ? stats.avg_heart_rate.toFixed(0) : "—"} <Text className="text-xs font-normal">{stats.avg_heart_rate > 0 ? "bpm" : ""}</Text>
              </Text>
              <Text className="text-neutral-500 text-[10px] mt-6">心血管耐力指标</Text>
            </View>
          </View>

          {/* Activity List */}
          <View className="flex-row justify-between items-center mb-4">
            <Text className="text-white text-lg font-bold">近期活动记录</Text>
            <Text className="text-neutral-500 text-xs">本月</Text>
          </View>

          {activities.length === 0 ? (
            <View className="bg-neutral-900 border border-neutral-800 rounded-3xl p-8 items-center justify-center">
              <Calendar size={32} color="#525252" className="mb-2" />
              <Text className="text-neutral-400 text-sm">本月尚无活动记录</Text>
              <Text className="text-neutral-600 text-xs mt-1">同步数据后会自动显示在此处</Text>
            </View>
          ) : (
            activities.map((act: any, idx: number) => {
              const runDate = new Date(act.start_date_local);
              const formattedDate = `${runDate.getMonth() + 1}月${runDate.getDate()}日`;
              const distance = (act.distance / 1000).toFixed(2);
              const paceMin = Math.floor(act.moving_time / 60 / (act.distance / 1000));
              const paceSec = Math.floor((act.moving_time / 60 / (act.distance / 1000) - paceMin) * 60);
              const paceStr = `${paceMin}'${paceSec.toString().padStart(2, "0")}"`;

              return (
                <View
                  key={act.id || idx}
                  className="bg-neutral-900 border border-neutral-800 rounded-2xl p-4 mb-3 flex-row justify-between items-center"
                >
                  <View>
                    <Text className="text-white font-semibold text-sm">{act.name || "跑步"}</Text>
                    <Text className="text-neutral-500 text-xs mt-1">{formattedDate} • 配速 {paceStr}</Text>
                  </View>
                  <Text className="text-blue-500 text-lg font-bold">{distance} km</Text>
                </View>
              );
            })
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
