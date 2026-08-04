import React, { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  ActivityIndicator,
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { apiClient } from "../../services/api";
import { auth } from "../../services/firebase";
import { User, LogOut, Trash2, Save, Mail, Award, Flame } from "lucide-react-native";

export default function ProfileScreen() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [gender, setGender] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [yearsRunning, setYearsRunning] = useState("");
  const [discordUrl, setDiscordUrl] = useState("");
  const [wecomUrl, setWecomUrl] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const user = auth.currentUser;

  const fetchProfile = useCallback(async () => {
    if (!user) return;
    try {
      setError("");
      const res = await apiClient.get(`/api/profile/${user.uid}`);
      const p = res.data;
      if (p) {
        setDisplayName(p.display_name || "");
        setGender(p.gender || "");
        setHeightCm(p.height_cm ? String(p.height_cm) : "");
        setWeightKg(p.weight_kg ? String(p.weight_kg) : "");
        setYearsRunning(p.years_running ? String(p.years_running) : "");
        setDiscordUrl(p.discord_webhook_url || "");
        setWecomUrl(p.wecom_webhook_url || "");
      }
    } catch (e) {
      console.error(e);
      setError("加载个人档案失败");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const handleSave = async () => {
    if (!user) return;
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      const payload = {
        uid: user.uid,
        display_name: displayName || null,
        gender: gender || null,
        height_cm: heightCm ? Number(heightCm) : null,
        weight_kg: weightKg ? Number(weightKg) : null,
        years_running: yearsRunning ? Number(yearsRunning) : null,
        discord_webhook_url: discordUrl || null,
        wecom_webhook_url: wecomUrl || null,
      };

      await apiClient.post("/api/profile/update", payload);
      setSuccess("档案保存成功！");
      setTimeout(() => setSuccess(""), 3000);
    } catch (e) {
      console.error(e);
      setError("保存失败，请检查网络");
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    Alert.alert("退出登录", "您确定要退出当前账号吗？", [
      { text: "取消", style: "cancel" },
      { text: "退出", style: "destructive", onPress: () => auth.signOut() },
    ]);
  };

  const handleDeleteAccount = () => {
    Alert.alert(
      "警告",
      "您确定要注销此账户吗？此操作不可逆，您的所有跑步历史与 AI 教练记录将被永久删除。",
      [
        { text: "我再想想", style: "cancel" },
        {
          text: "确认删除",
          style: "destructive",
          onPress: async () => {
            if (user) {
              try {
                await user.delete();
                Alert.alert("注销成功", "您的账户已被永久删除。");
              } catch (e: any) {
                console.error(e);
                if (e.code === "auth/requires-recent-login") {
                  Alert.alert("敏感操作", "为了安全起见，请重新登录后再进行此操作。");
                  auth.signOut();
                } else {
                  Alert.alert("删除失败", "删除账户失败，请稍后重试。");
                }
              }
            }
          },
        },
      ]
    );
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
      <ScrollView contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
        <View className="px-6 py-4 flex-1">
          {/* Header */}
          <View className="items-center mb-6">
            <View className="h-16 w-16 bg-neutral-800 rounded-full items-center justify-center border border-neutral-700 mb-3">
              <User size={32} color="#a3a3a3" />
            </View>
            <Text className="text-white text-xl font-bold">{displayName || "未命名跑者"}</Text>
            <Text className="text-neutral-500 text-xs mt-1">{user?.email}</Text>
          </View>

          {success ? (
            <View className="bg-green-500/10 border border-green-500/20 rounded-xl p-3 mb-4">
              <Text className="text-green-400 text-xs text-center">{success}</Text>
            </View>
          ) : null}

          {error ? (
            <View className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 mb-4">
              <Text className="text-red-400 text-xs text-center">{error}</Text>
            </View>
          ) : null}

          {/* Profile Details Form */}
          <View className="bg-neutral-900 border border-neutral-800 rounded-3xl p-5 mb-5 space-y-4">
            <Text className="text-white font-bold text-base mb-2">个人信息</Text>

            {/* Display Name */}
            <View className="mb-4">
              <Text className="text-neutral-400 text-xs font-semibold mb-2">昵称 / 跑名</Text>
              <TextInput
                value={displayName}
                onChangeText={setDisplayName}
                placeholder="例如：极速闪电"
                placeholderTextColor="#525252"
                className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-3 text-white text-sm"
              />
            </View>

            {/* Row: Gender & Years Running */}
            <View className="flex-row justify-between mb-4">
              <View className="w-[48%]">
                <Text className="text-neutral-400 text-xs font-semibold mb-2">性别</Text>
                <TextInput
                  value={gender}
                  onChangeText={setGender}
                  placeholder="男 / 女"
                  placeholderTextColor="#525252"
                  className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-3 text-white text-sm"
                />
              </View>
              <View className="w-[48%]">
                <Text className="text-neutral-400 text-xs font-semibold mb-2">跑龄 (年)</Text>
                <TextInput
                  value={yearsRunning}
                  onChangeText={setYearsRunning}
                  placeholder="输入数字"
                  placeholderTextColor="#525252"
                  keyboardType="numeric"
                  className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-3 text-white text-sm"
                />
              </View>
            </View>

            {/* Row: Height & Weight */}
            <View className="flex-row justify-between mb-2">
              <View className="w-[48%]">
                <Text className="text-neutral-400 text-xs font-semibold mb-2">身高 (cm)</Text>
                <TextInput
                  value={heightCm}
                  onChangeText={setHeightCm}
                  placeholder="例如：175"
                  placeholderTextColor="#525252"
                  keyboardType="numeric"
                  className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-3 text-white text-sm"
                />
              </View>
              <View className="w-[48%]">
                <Text className="text-neutral-400 text-xs font-semibold mb-2">体重 (kg)</Text>
                <TextInput
                  value={weightKg}
                  onChangeText={setWeightKg}
                  placeholder="例如：65"
                  placeholderTextColor="#525252"
                  keyboardType="numeric"
                  className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-3 text-white text-sm"
                />
              </View>
            </View>
          </View>

          {/* Webhook Notifications */}
          <View className="bg-neutral-900 border border-neutral-800 rounded-3xl p-5 mb-6 space-y-4">
            <Text className="text-white font-bold text-base mb-2">跑团通知通道</Text>

            {/* Discord Webhook */}
            <View className="mb-4">
              <Text className="text-neutral-400 text-xs font-semibold mb-2">Discord Webhook URL</Text>
              <TextInput
                value={discordUrl}
                onChangeText={setDiscordUrl}
                placeholder="https://discord.com/api/webhooks/..."
                placeholderTextColor="#525252"
                autoCapitalize="none"
                autoCorrect={false}
                className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-3 text-white text-xs"
              />
            </View>

            {/* WeCom Webhook */}
            <View className="mb-2">
              <Text className="text-neutral-400 text-xs font-semibold mb-2">企业微信机器人 Webhook URL</Text>
              <TextInput
                value={wecomUrl}
                onChangeText={setWecomUrl}
                placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/..."
                placeholderTextColor="#525252"
                autoCapitalize="none"
                autoCorrect={false}
                className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-3 text-white text-xs"
              />
            </View>
          </View>

          {/* Save Button */}
          <TouchableOpacity
            onPress={handleSave}
            disabled={saving}
            className="w-full bg-blue-600 active:bg-blue-700 py-4 rounded-xl flex-row items-center justify-center mb-6 shadow-lg shadow-blue-500/20"
            activeOpacity={0.8}
          >
            {saving ? (
              <ActivityIndicator size="small" color="white" />
            ) : (
              <>
                <Save size={16} color="white" className="mr-2" />
                <Text className="text-white font-bold text-sm">保存修改</Text>
              </>
            )}
          </TouchableOpacity>

          {/* Spacer */}
          <View className="h-6" />

          {/* Danger Zone */}
          <View className="border-t border-neutral-800 pt-6">
            {/* Logout Button */}
            <TouchableOpacity
              onPress={handleLogout}
              className="w-full bg-neutral-900 border border-neutral-800 py-4 rounded-xl flex-row items-center justify-center mb-4 active:bg-neutral-800"
              activeOpacity={0.8}
            >
              <LogOut size={16} color="#ef4444" className="mr-2" />
              <Text className="text-red-500 font-bold text-sm">退出登录</Text>
            </TouchableOpacity>

            {/* Delete Account Button */}
            <TouchableOpacity
              onPress={handleDeleteAccount}
              className="w-full py-4 rounded-xl flex-row items-center justify-center active:bg-red-500/10"
              activeOpacity={0.8}
            >
              <Trash2 size={14} color="#737373" className="mr-1.5" />
              <Text className="text-neutral-500 text-xs font-semibold">注销并删除我的跑者账号</Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
