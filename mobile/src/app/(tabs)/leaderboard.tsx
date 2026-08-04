import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { apiClient } from "../../services/api";
import { auth } from "../../services/firebase";
import { Trophy, Award, Flame, Calendar } from "lucide-react-native";

interface LeaderboardEntry {
  uid: string;
  email: string;
  display_name?: string;
  total_distance_km: number;
  avg_pace: string;
  avg_heart_rate: number;
  goal_completion_percentage: number;
  run_count: number;
  period: "weekly" | "monthly";
}

interface YearlyEntry {
  uid: string;
  display_name?: string;
  email: string;
  total_distance_km: number;
  run_count: number;
  avg_pace: string;
  year: number;
}

type TabType = "monthly" | "weekly" | "yearly";

export default function LeaderboardScreen() {
  const [activeTab, setActiveTab] = useState<TabType>("monthly");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [yearlyEntries, setYearlyEntries] = useState<YearlyEntry[]>([]);
  const [error, setError] = useState("");

  const user = auth.currentUser;

  const fetchLeaderboard = useCallback(async () => {
    try {
      setError("");
      if (activeTab === "yearly") {
        const year = new Date().getFullYear();
        const res = await apiClient.get("/api/sync/yearly-leaderboard", {
          params: { year },
        });
        setYearlyEntries(res.data.entries || []);
      } else {
        const res = await apiClient.get("/api/data/leaderboard", {
          params: { period: activeTab, limit_n: 20 },
        });
        setEntries(res.data.entries || []);
      }
    } catch (e) {
      console.error(e);
      setError("排行榜数据加载失败，请下拉刷新");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [activeTab]);

  useEffect(() => {
    fetchLeaderboard();
  }, [fetchLeaderboard]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchLeaderboard();
  };

  const getRankBadgeStyle = (index: number) => {
    if (index === 0) return "bg-yellow-500/20 border-yellow-500/30 text-yellow-400";
    if (index === 1) return "bg-neutral-300/20 border-neutral-300/30 text-neutral-300";
    if (index === 2) return "bg-amber-700/20 border-amber-700/30 text-amber-500";
    return "bg-neutral-900 border-neutral-800 text-neutral-500";
  };

  const getName = (entry: any) => {
    return (
      entry.display_name ||
      entry.email?.split("@")[0] ||
      `跑者 #${entry.uid?.slice(0, 6)}`
    );
  };

  return (
    <SafeAreaView className="flex-1 bg-neutral-950" edges={["top"]}>
      <View className="px-6 py-4 flex-1">
        {/* Header */}
        <View className="flex-row justify-between items-center mb-6">
          <View>
            <Text className="text-neutral-400 text-xs font-semibold uppercase tracking-wider">RUNNING CLUB</Text>
            <Text className="text-white text-2xl font-bold">跑团排行榜</Text>
          </View>
          <Trophy size={28} color="#eab308" />
        </View>

        {/* Tab Selector */}
        <View className="flex-row bg-neutral-900 border border-neutral-800 p-1.5 rounded-2xl mb-6">
          {(["monthly", "weekly", "yearly"] as TabType[]).map((tab) => (
            <TouchableOpacity
              key={tab}
              onPress={() => {
                setActiveTab(tab);
                setLoading(true);
              }}
              className={`flex-1 py-3.5 rounded-xl items-center ${
                activeTab === tab ? "bg-neutral-800" : ""
              }`}
              activeOpacity={0.8}
            >
              <Text
                className={`text-xs font-bold ${
                  activeTab === tab ? "text-white" : "text-neutral-500"
                }`}
              >
                {tab === "monthly" ? "月榜" : tab === "weekly" ? "周榜" : "年榜"}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {error ? (
          <View className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 mb-6">
            <Text className="text-red-400 text-xs">{error}</Text>
          </View>
        ) : null}

        {loading ? (
          <View className="flex-1 justify-center items-center">
            <ActivityIndicator size="large" color="#3b82f6" />
          </View>
        ) : (
          <ScrollView
            contentContainerStyle={{ flexGrow: 1 }}
            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#3b82f6" />}
          >
            {activeTab === "yearly" ? (
              // Yearly entries
              yearlyEntries.length === 0 ? (
                <View className="flex-1 justify-center items-center py-20">
                  <Calendar size={36} color="#525252" className="mb-2" />
                  <Text className="text-neutral-400 text-sm">暂无年榜记录</Text>
                </View>
              ) : (
                yearlyEntries.map((entry, index) => {
                  const isCurrentUser = entry.uid === user?.uid;
                  return (
                    <View
                      key={entry.uid}
                      className={`flex-row items-center justify-between p-4 mb-3 border rounded-2xl ${
                        isCurrentUser
                          ? "bg-blue-600/10 border-blue-500/40"
                          : "bg-neutral-900 border-neutral-800"
                      }`}
                    >
                      <View className="flex-row items-center flex-1 pr-4">
                        {/* Rank Badge */}
                        <View
                          className={`h-8 w-8 rounded-full border items-center justify-center mr-3 ${getRankBadgeStyle(
                            index
                          )}`}
                        >
                          <Text className="font-bold text-xs">{index + 1}</Text>
                        </View>
                        {/* Name and Stats */}
                        <View className="flex-1">
                          <Text className="text-white font-semibold text-sm" numberOfLines={1}>
                            {getName(entry)}
                          </Text>
                          <Text className="text-neutral-500 text-[10px] mt-0.5">
                            {entry.run_count}次跑步  •  平均配速 {entry.avg_pace}
                          </Text>
                        </View>
                      </View>
                      <Text className="text-white text-base font-black">
                        {entry.total_distance_km.toFixed(1)} <Text className="text-xs font-normal text-neutral-500">km</Text>
                      </Text>
                    </View>
                  );
                })
              )
            ) : (
              // Monthly / Weekly entries
              entries.length === 0 ? (
                <View className="flex-1 justify-center items-center py-20">
                  <Award size={36} color="#525252" className="mb-2" />
                  <Text className="text-neutral-400 text-sm">本期排行榜尚无数据</Text>
                </View>
              ) : (
                entries.map((entry, index) => {
                  const isCurrentUser = entry.uid === user?.uid;
                  return (
                    <View
                      key={entry.uid}
                      className={`flex-row items-center justify-between p-4 mb-3 border rounded-2xl ${
                        isCurrentUser
                          ? "bg-blue-600/10 border-blue-500/40"
                          : "bg-neutral-900 border-neutral-800"
                      }`}
                    >
                      <View className="flex-row items-center flex-1 pr-4">
                        {/* Rank Badge */}
                        <View
                          className={`h-8 w-8 rounded-full border items-center justify-center mr-3 ${getRankBadgeStyle(
                            index
                          )}`}
                        >
                          <Text className="font-bold text-xs">{index + 1}</Text>
                        </View>
                        {/* Name and Stats */}
                        <View className="flex-1">
                          <View className="flex-row items-center">
                            <Text className="text-white font-semibold text-sm max-w-[70%]" numberOfLines={1}>
                              {getName(entry)}
                            </Text>
                            {entry.goal_completion_percentage > 0 ? (
                              <View className="bg-blue-500/15 px-1.5 py-0.5 rounded ml-2 border border-blue-500/20">
                                <Text className="text-blue-400 text-[9px] font-bold">
                                  {entry.goal_completion_percentage.toFixed(0)}% 目标
                                </Text>
                              </View>
                            ) : null}
                          </View>
                          <Text className="text-neutral-500 text-[10px] mt-0.5">
                            {entry.run_count}次  •  配速 {entry.avg_pace}  •  心率 {entry.avg_heart_rate > 0 ? entry.avg_heart_rate.toFixed(0) : "—"}
                          </Text>
                        </View>
                      </View>
                      <Text className="text-white text-base font-black">
                        {entry.total_distance_km.toFixed(1)} <Text className="text-xs font-normal text-neutral-500">km</Text>
                      </Text>
                    </View>
                  );
                })
              )
            )}
          </ScrollView>
        )}
      </View>
    </SafeAreaView>
  );
}
