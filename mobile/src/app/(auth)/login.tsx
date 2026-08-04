import React, { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import { router } from "expo-router";
import { auth } from "../../services/firebase";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
} from "firebase/auth";
import { ShieldCheck, Mail, Lock } from "lucide-react-native";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [agreePrivacy, setAgreePrivacy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!email || !password) {
      setError("请输入邮箱和密码");
      return;
    }
    if (isRegister && !agreePrivacy) {
      setError("请阅读并同意个人数据声明");
      return;
    }

    setError("");
    setLoading(true);

    try {
      if (isRegister) {
        // Register
        await createUserWithEmailAndPassword(auth, email, password);
        // Call backend welcome-email if needed (can be run asynchronously in background)
        const user = auth.currentUser;
        if (user && user.email) {
          const backendUrl = process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:8000";
          fetch(`${backendUrl}/api/auth/welcome-email`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              uid: user.uid,
              email: user.email,
            }),
          }).catch(() => {});
        }
      } else {
        // Login
        await signInWithEmailAndPassword(auth, email, password);
      }
      
      // Redirect to main tabs on success
      router.replace("/(tabs)");
    } catch (e: any) {
      console.error(e);
      let errMsg = "认证失败，请检查您的网络与账号";
      if (e.code === "auth/invalid-credential") {
        errMsg = "密码错误或用户不存在";
      } else if (e.code === "auth/email-already-in-use") {
        errMsg = "该邮箱已被注册";
      } else if (e.code === "auth/weak-password") {
        errMsg = "密码强度太弱（至少6位）";
      } else if (e.code === "auth/invalid-email") {
        errMsg = "无效的邮箱地址";
      }
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : "height"}
      className="flex-1 bg-neutral-950"
    >
      <ScrollView contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
        <View className="flex-1 justify-center px-6 py-12">
          {/* Header & Logo */}
          <View className="items-center mb-10">
            <View className="h-16 w-16 bg-blue-600 rounded-2xl items-center justify-center shadow-lg shadow-blue-500/30 mb-4">
              <Text className="text-white text-3xl font-black">R</Text>
            </View>
            <Text className="text-white text-2xl font-bold tracking-wider">RGM 跑团管理</Text>
            <Text className="text-neutral-400 text-sm mt-1">记录 • 竞争 • 进化</Text>
          </View>

          {/* Form Card */}
          <View className="bg-neutral-900 border border-neutral-800 rounded-3xl p-6 shadow-2xl">
            <Text className="text-white text-xl font-bold mb-6">
              {isRegister ? "创建跑者账号" : "登录平台"}
            </Text>

            {error ? (
              <View className="bg-red-500/10 border border-red-500/20 rounded-xl p-3 mb-4">
                <Text className="text-red-400 text-xs">{error}</Text>
              </View>
            ) : null}

            {/* Email Input */}
            <View className="mb-4">
              <Text className="text-neutral-400 text-xs font-semibold mb-2">邮箱地址</Text>
              <View className="flex-row items-center bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-3">
                <Mail size={16} color="#737373" className="mr-2" />
                <TextInput
                  value={email}
                  onChangeText={setEmail}
                  placeholder="name@domain.com"
                  placeholderTextColor="#525252"
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                  className="flex-1 text-white text-sm"
                />
              </View>
            </View>

            {/* Password Input */}
            <View className="mb-6">
              <Text className="text-neutral-400 text-xs font-semibold mb-2">输入密码</Text>
              <View className="flex-row items-center bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-3">
                <Lock size={16} color="#737373" className="mr-2" />
                <TextInput
                  value={password}
                  onChangeText={setPassword}
                  placeholder="••••••••"
                  placeholderTextColor="#525252"
                  secureTextEntry
                  autoCapitalize="none"
                  autoCorrect={false}
                  className="flex-1 text-white text-sm"
                />
              </View>
            </View>

            {/* Privacy Agreement (Register Only) */}
            {isRegister ? (
              <TouchableOpacity
                onPress={() => setAgreePrivacy(!agreePrivacy)}
                className="flex-row items-center mb-6"
                activeOpacity={0.8}
              >
                <View
                  className={`h-5 w-5 rounded-md border items-center justify-center mr-2 ${
                    agreePrivacy ? "bg-blue-600 border-blue-600" : "border-neutral-700 bg-neutral-950"
                  }`}
                >
                  {agreePrivacy ? <ShieldCheck size={12} color="white" /> : null}
                </View>
                <Text className="text-neutral-400 text-xs flex-1 leading-4">
                  已阅读并同意 <Text className="text-blue-500 font-semibold">个人数据声明</Text>
                </Text>
              </TouchableOpacity>
            ) : null}

            {/* Submit Button */}
            <TouchableOpacity
              onPress={handleSubmit}
              disabled={loading}
              className={`w-full py-4 rounded-xl items-center justify-center ${
                loading ? "bg-blue-600/50" : "bg-blue-600 active:bg-blue-700"
              }`}
              activeOpacity={0.8}
            >
              {loading ? (
                <ActivityIndicator color="white" size="small" />
              ) : (
                <Text className="text-white font-bold text-sm">
                  {isRegister ? "确认注册并登录" : "立即登录"}
                </Text>
              )}
            </TouchableOpacity>

            {/* Screen Switcher */}
            <TouchableOpacity
              onPress={() => {
                setIsRegister(!isRegister);
                setError("");
              }}
              className="mt-6 align-center"
              activeOpacity={0.8}
            >
              <Text className="text-neutral-400 text-center text-xs">
                {isRegister ? (
                  <>
                    已有账号？ <Text className="text-blue-500 font-semibold">点击登录</Text>
                  </>
                ) : (
                  <>
                    新加入跑团？ <Text className="text-blue-500 font-semibold">创建新账号</Text>
                  </>
                )}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
