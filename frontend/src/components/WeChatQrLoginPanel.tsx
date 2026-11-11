"use client";

import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { supabase } from "@/lib/supabase";
import { QrCode, RefreshCw, Smartphone, CheckCircle2, Loader2, ShieldCheck } from "lucide-react";

interface WeChatQrLoginPanelProps {
  onSuccess: () => void;
}

export default function WeChatQrLoginPanel({ onSuccess }: WeChatQrLoginPanelProps) {
  const [sceneId, setSceneId] = useState<string>("");
  const [qrBase64, setQrBase64] = useState<string | null>(null);
  const [hasOfficialWxacode, setHasOfficialWxacode] = useState<boolean>(false);
  const [miniappPath, setMiniappPath] = useState<string>("");
  const [envVersion, setEnvVersion] = useState<"release" | "trial">("release");
  const [status, setStatus] = useState<"loading" | "pending" | "scanned" | "confirmed" | "expired" | "error">("loading");
  const [scannedUser, setScannedUser] = useState<{ name: string; avatar: string }>({ name: "", avatar: "" });
  const [errText, setErrText] = useState<string>("");

  const createQrSession = useCallback(async (targetEnv?: "release" | "trial") => {
    const useEnv = targetEnv || envVersion;
    setStatus("loading");
    setErrText("");
    setScannedUser({ name: "", avatar: "" });
    try {
      const res = await axios.post("/api/auth/wechat/web-qr/create", { env_version: useEnv });
      const data = res.data || {};
      setSceneId(data.scene_id || "");
      setQrBase64(data.qrcode_base64 || null);
      setHasOfficialWxacode(Boolean(data.has_official_wxacode && data.qrcode_base64));
      setMiniappPath(data.miniapp_path || "");
      setStatus("pending");
    } catch (err: any) {
      setStatus("error");
      setErrText(err.response?.data?.detail || "获取微信扫码登录凭证失败，请点击重试");
    }
  }, [envVersion]);

  useEffect(() => {
    createQrSession();
  }, [createQrSession]);

  useEffect(() => {
    if (!sceneId || (status !== "pending" && status !== "scanned")) {
      return;
    }
    let cancelled = false;
    const timer = setInterval(async () => {
      try {
        const res = await axios.get(`/api/auth/wechat/web-qr/status/${encodeURIComponent(sceneId)}`);
        if (cancelled) return;
        const data = res.data || {};
        if (data.status === "scanned") {
          setStatus("scanned");
          setScannedUser({
            name: data.display_name || "微信跑者",
            avatar: data.avatar_url || "",
          });
        } else if (data.status === "confirmed" && data.token && data.user) {
          setStatus("confirmed");
          clearInterval(timer);
          await supabase.auth.completeTokenSession(data.token, data.user);
          onSuccess();
        } else if (data.status === "expired" || data.status === "consumed") {
          setStatus("expired");
          clearInterval(timer);
        }
      } catch {
        // Keep polling on transient network hiccups
      }
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [sceneId, status, onSuccess]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col items-center justify-center p-5 rounded-2xl bg-white/[0.03] border border-white/10">
        <div className="relative w-52 h-52 rounded-2xl bg-white p-3 flex items-center justify-center shadow-xl overflow-hidden">
          {status === "loading" ? (
            <div className="flex flex-col items-center gap-2 text-zinc-600">
              <Loader2 className="w-8 h-8 animate-spin text-[#07C160]" />
              <span className="text-xs font-semibold">正在生成专属小程序码...</span>
            </div>
          ) : qrBase64 ? (
            <img
              src={qrBase64}
              alt="微信小程序动态扫码登录"
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="flex flex-col items-center justify-center text-center px-2 gap-2 text-zinc-700">
              <QrCode className="w-16 h-16 text-[#07C160]" />
              <span className="text-[11px] font-bold leading-snug">
                本地开发环境未配置微信 AppSecret
              </span>
              {miniappPath && (
                <code className="text-[10px] bg-zinc-100 px-2 py-1 rounded text-zinc-600 break-all">
                  {miniappPath}
                </code>
              )}
            </div>
          )}

          {status === "scanned" && (
            <div className="absolute inset-0 bg-black/80 backdrop-blur-xs flex flex-col items-center justify-center p-4 text-center">
              <Smartphone className="w-9 h-9 text-[#07C160] mb-2 animate-bounce" />
              <span className="text-sm font-black text-white">手机已扫码</span>
              <span className="text-[11px] text-emerald-300 mt-1 leading-relaxed">
                请在手机微信点击
                <br />
                「确认授权登录网页版」或「立即进入小程序」
              </span>
              {scannedUser.name && (
                <span className="mt-2 px-2.5 py-0.5 rounded-full bg-white/10 text-[11px] text-zinc-200">
                  {scannedUser.name}
                </span>
              )}
            </div>
          )}

          {status === "confirmed" && (
            <div className="absolute inset-0 bg-emerald-950/90 backdrop-blur-xs flex flex-col items-center justify-center p-4 text-center">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mb-2" />
              <span className="text-sm font-black text-white">授权成功，正在进入...</span>
            </div>
          )}

          {(status === "expired" || status === "error") && (
            <div className="absolute inset-0 bg-black/85 backdrop-blur-xs flex flex-col items-center justify-center p-4 text-center gap-2.5">
              <span className="text-xs font-bold text-zinc-200">
                {errText || "二维码已过期"}
              </span>
              <button
                type="button"
                onClick={() => createQrSession()}
                className="px-4 py-2 rounded-xl bg-[#07C160] hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1.5 transition cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                刷新二维码
              </button>
            </div>
          )}
        </div>

        <div className="mt-4 text-center space-y-1">
          <div className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-[#07C160] animate-pulse" />
            打开手机微信「扫一扫」免密登录
          </div>
          <p className="text-[11px] text-zinc-400">
            {hasOfficialWxacode
              ? envVersion === "trial"
                ? "当前为体验版测试码 · 适合小程序审核发布前即时验证"
                : "动态小程序码有效期 5 分钟 · 一次一密防重放保护"
              : "支持与已绑定的佳明 / 高驰运动手表档案自动合并互通"}
          </p>
        </div>

        {(status === "pending" || status === "scanned") && (
          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={() => createQrSession()}
              className="inline-flex items-center gap-1 text-[11px] text-zinc-400 hover:text-white transition cursor-pointer"
            >
              <RefreshCw className="w-3 h-3" />
              刷新二维码
            </button>
            <span className="text-zinc-600 text-[10px]">|</span>
            <button
              type="button"
              onClick={() => {
                const next = envVersion === "release" ? "trial" : "release";
                setEnvVersion(next);
                createQrSession(next);
              }}
              className="text-[11px] text-zinc-400 hover:text-emerald-400 transition cursor-pointer"
            >
              {envVersion === "release" ? "切换体验版码" : "切回正式版码"}
            </button>
          </div>
        )}
      </div>

      <div className="flex items-start gap-2 p-2.5 bg-white/[0.03] rounded-xl border border-white/5 text-[11px] text-zinc-400 leading-relaxed">
        <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
        <span>
          扫码后在「万跑跑团助手」小程序内点击「确认授权」或「立即进入小程序」，即可自动登录网页端并同步跑团、课表与跑步记录。
        </span>
      </div>
    </div>
  );
}
