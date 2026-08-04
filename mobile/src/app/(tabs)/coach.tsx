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
import { Sparkles, Trophy, ShieldAlert, Award, ChevronRight } from "lucide-react-native";

interface RaceAnalysis {
  race_name: string;
  race_type: string;
  difficulty_level: string;
  total_distance: string;
  elevation_gain: string;
  key_demands: string[];
  climate_notes: string;
  recommended_weekly_km: string;
  fitness_gap: string;
  readiness_score: number;
}

interface CoachFeedback {
  status: string;
  summary: string;
  encouragement?: string;
  actionable_tips: string[];
  training_principles?: { title: string; detail: string }[];
  weekly_cycle?: {
    week: number;
    week_label?: string;
    is_current?: boolean;
    status?: string;
    phase: string;
    focus: string;
    key_session: string;
    volume_note: string;
    tips?: string[];
  }[];
  key_metrics?: Record<string, string>;
  race_analysis?: RaceAnalysis;
}

const metricLabels: Record<string, string> = {
  recommended_weekly_km: "建议周跑量",
  easy_run_pace: "轻松跑配速",
  tempo_pace: "节奏跑配速",
  long_run_distance: "长跑距离",
  maf_heart_rate: "MAF心率",
  target_long_run_pct: "长距离占比",
  easy_run_pct: "轻松跑占比",
  max_weekly_increase: "最大跑量增幅",
};

export default function CoachScreen() {
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [feedback, setFeedback] = useState<CoachFeedback | null>(null);
  const [error, setError] = useState("");

  const user = auth.currentUser;

  const fetchCachedFeedback = useCallback(async () => {
    if (!user) return;
    try {
      setError("");
      const res = await apiClient.get(`/api/coach/cache/${user.uid}`);
      if (res.data && res.data.feedback) {
        setFeedback(res.data.feedback);
      }
    } catch (e) {
      console.error(e);
      setError("读取分析缓存失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user]);

  const handleGenerateFeedback = async (force = false) => {
    if (!user) return;
    setGenerating(true);
    setError("");
    try {
      const res = await apiClient.post("/api/coach/analyze", {
        uid: user.uid,
        force_refresh: force,
      });
      if (res.data && res.data.feedback) {
        setFeedback(res.data.feedback);
      } else {
        setError("生成分析失败，请稍后重试");
      }
    } catch (e) {
      console.error(e);
      setError("AI分析生成出错，请检查网络");
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    fetchCachedFeedback();
  }, [fetchCachedFeedback]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchCachedFeedback();
  };

  if (loading) {
    return (
      <View className="flex-1 bg-neutral-950 items-center justify-center">
        <ActivityIndicator size="large" color="#3b82f6" />
      </View>
    );
  }

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
              <Text className="text-neutral-400 text-xs font-semibold uppercase tracking-wider">AI RUNNING COACH</Text>
              <Text className="text-white text-2xl font-bold">Renato Canova 指导</Text>
            </View>
            <TouchableOpacity
              onPress={() => handleGenerateFeedback(true)}
              disabled={generating}
              className="bg-blue-600 active:bg-blue-700 h-10 px-4 rounded-xl items-center justify-center flex-row shadow-lg shadow-blue-500/20"
            >
              {generating ? (
                <ActivityIndicator size="small" color="white" />
              ) : (
                <>
                  <Sparkles size={14} color="white" className="mr-1.5" />
                  <Text className="text-white text-xs font-bold">重新分析</Text>
                </>
              )}
            </TouchableOpacity>
          </View>

          {generating ? (
            <View className="flex-1 justify-center items-center py-20 bg-neutral-900/40 border border-neutral-800 rounded-3xl mb-6">
              <ActivityIndicator size="large" color="#3b82f6" className="mb-4" />
              <Text className="text-white font-bold text-base mb-1">AI 正在深度诊断中...</Text>
              <Text className="text-neutral-500 text-xs text-center px-8 leading-5">
                正在并行分析您近期的 Strava 跑步轨迹、配速心率模型，并结合目标比赛制定个性化周期计划。可能需要 15-30 秒。
              </Text>
            </View>
          ) : (
            <>
              {error ? (
                <View className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 mb-6">
                  <Text className="text-red-400 text-xs">{error}</Text>
                </View>
              ) : null}

              {!feedback ? (
                <View className="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 items-center text-center mb-6">
                  <Award size={32} color="#3b82f6" className="mb-2" />
                  <Text className="text-white font-bold text-sm mb-1">暂无 AI 教练诊断</Text>
                  <Text className="text-neutral-500 text-xs mb-4 text-center leading-4">
                    点击右上角的“重新分析”按钮，让 Renato Canova AI 顾问开始为您把脉训练。
                  </Text>
                  <TouchableOpacity
                    onPress={() => handleGenerateFeedback(false)}
                    className="bg-blue-600 active:bg-blue-700 py-3 px-6 rounded-xl"
                  >
                    <Text className="text-white text-xs font-bold">开始首次分析</Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <View className="space-y-6">
                  {/* Status & Summary */}
                  <View className="bg-neutral-900 border border-neutral-800 rounded-3xl p-5 mb-5">
                    <View className="flex-row items-center mb-3">
                      <View className="bg-blue-500/15 border border-blue-500/20 px-3 py-1 rounded-full">
                        <Text className="text-blue-400 text-xs font-semibold">{feedback.status || "周期评估中"}</Text>
                      </View>
                      <Text className="text-neutral-500 text-xs ml-3">Canova 科学建议</Text>
                    </View>
                    <Text className="text-white text-sm leading-6 mb-3">{feedback.summary}</Text>
                    {feedback.encouragement ? (
                      <Text className="text-blue-400 text-xs italic font-semibold leading-5">“{feedback.encouragement}”</Text>
                    ) : null}
                  </View>

                  {/* Weekly Cycle Accordion */}
                  {feedback.weekly_cycle && feedback.weekly_cycle.length > 0 ? (
                    <View className="mb-5">
                      <Text className="text-white text-lg font-bold mb-3">周期训练计划 (3周规划)</Text>
                      {feedback.weekly_cycle.map((w, idx) => (
                        <View
                          key={idx}
                          className={`bg-neutral-900 border rounded-2xl p-4 mb-3 ${
                            w.is_current ? "border-blue-500/50" : "border-neutral-800"
                          }`}
                        >
                          <View className="flex-row justify-between items-center mb-2">
                            <Text className="text-white font-bold text-sm">第 {w.week} 周 {w.week_label || ""}</Text>
                            {w.is_current ? (
                              <View className="bg-blue-600 px-2 py-0.5 rounded-md">
                                <Text className="text-white text-[9px] font-bold">当前周</Text>
                              </View>
                            ) : (
                              <Text className="text-neutral-500 text-xs">{w.phase}</Text>
                            )}
                          </View>
                          <Text className="text-neutral-400 text-xs mb-2 leading-4"><Text className="text-neutral-300 font-semibold">聚焦：</Text>{w.focus}</Text>
                          <Text className="text-blue-400 text-xs leading-4"><Text className="text-neutral-300 font-semibold">核心训练：</Text>{w.key_session}</Text>
                          <Text className="text-neutral-500 text-[10px] mt-2 leading-4">{w.volume_note}</Text>
                        </View>
                      ))}
                    </View>
                  ) : null}

                  {/* Key Pace Metrics */}
                  {feedback.key_metrics ? (
                    <View className="mb-5">
                      <Text className="text-white text-lg font-bold mb-3">配速与跑量指标</Text>
                      <View className="bg-neutral-900 border border-neutral-800 rounded-3xl p-4 flex-row flex-wrap justify-between">
                        {Object.entries(feedback.key_metrics).map(([key, val], idx) => {
                          const label = metricLabels[key] || key;
                          return (
                            <View key={idx} className="w-[48%] bg-neutral-950/50 border border-neutral-800/30 rounded-xl p-3 mb-3">
                              <Text className="text-neutral-500 text-[10px] mb-1">{label}</Text>
                              <Text className="text-white font-bold text-sm">{val}</Text>
                            </View>
                          );
                        })}
                      </View>
                    </View>
                  ) : null}

                  {/* Race Analysis */}
                  {feedback.race_analysis ? (
                    <View className="mb-5">
                      <Text className="text-white text-lg font-bold mb-3">目标赛事诊断</Text>
                      <View className="bg-neutral-900 border border-neutral-800 rounded-3xl p-5">
                        <View className="flex-row justify-between items-center mb-3">
                          <Text className="text-white font-bold text-base">{feedback.race_analysis.race_name}</Text>
                          <Text className="text-neutral-400 text-xs">{feedback.race_analysis.race_type}</Text>
                        </View>
                        <View className="flex-row mb-4">
                          <View className="bg-red-500/10 border border-red-500/20 px-2 py-1 rounded mr-2">
                            <Text className="text-red-400 text-[10px] font-semibold">准备就绪度 {feedback.race_analysis.readiness_score}%</Text>
                          </View>
                          <View className="bg-neutral-800 px-2 py-1 rounded">
                            <Text className="text-neutral-300 text-[10px] font-semibold">难度 {feedback.race_analysis.difficulty_level}</Text>
                          </View>
                        </View>
                        <Text className="text-neutral-400 text-xs leading-5 mb-2">
                          <Text className="text-neutral-300 font-semibold">距离：</Text>{feedback.race_analysis.total_distance}  |  <Text className="text-neutral-300 font-semibold">爬升：</Text>{feedback.race_analysis.elevation_gain}
                        </Text>
                        <Text className="text-neutral-400 text-xs leading-5 mb-3">
                          <Text className="text-neutral-300 font-semibold">体能差距：</Text>{feedback.race_analysis.fitness_gap}
                        </Text>
                        <View className="bg-neutral-950/40 p-3 rounded-xl border border-neutral-800/50">
                          <Text className="text-neutral-300 font-semibold text-xs mb-1.5 flex-row items-center">
                            <ShieldAlert size={12} color="#fbbf24" className="mr-1" /> 核心挑战与气候：
                          </Text>
                          <Text className="text-neutral-500 text-[11px] leading-4">{feedback.race_analysis.climate_notes}</Text>
                        </View>
                      </View>
                    </View>
                  ) : null}
                </View>
              )}
            </>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
