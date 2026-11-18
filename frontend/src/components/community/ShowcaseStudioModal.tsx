"use client";

import { useState, useEffect } from "react";
import apiClient from "@/lib/apiClient";
import { useUiFeedback } from "@/components/ui/UiFeedbackProvider";
import { X, Upload, Trash2, Star, Save } from "lucide-react";

interface ShowcaseStudioModalProps {
  open: boolean;
  onClose: () => void;
  mode: "club" | "coach";
  ownerId: string; // club_id when club, user_id when coach
  operatorUid: string;
  onSaved?: () => void;
}

const PHOTO_CATEGORIES = [
  { key: "group_run", label: "合练实拍" },
  { key: "race_highlight", label: "赛场高光" },
  { key: "certificate", label: "证书奖项" },
  { key: "team_event", label: "补给团建" },
];

export default function ShowcaseStudioModal({
  open,
  onClose,
  mode,
  ownerId,
  operatorUid,
  onSaved,
}: ShowcaseStudioModalProps) {
  const { showToast, askConfirm } = useUiFeedback();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  // Club showcase state
  const [slogan, setSlogan] = useState("");
  const [styleTagsText, setStyleTagsText] = useState("");
  const [landmarksText, setLandmarksText] = useState("");
  const [scheduleSummary, setScheduleSummary] = useState("");
  const [highlightsMd, setHighlightsMd] = useState("");

  // Coach resume state
  const [headline, setHeadline] = useState("");
  const [specialtyText, setSpecialtyText] = useState("");
  const [certTitle, setCertTitle] = useState("");
  const [bioStory, setBioStory] = useState("");
  const [philosophy, setPhilosophy] = useState("");

  // Photo gallery state
  const [photos, setPhotos] = useState<any[]>([]);
  const [uploadCategory, setUploadCategory] = useState("group_run");
  const [uploadCaption, setUploadCaption] = useState("");

  useEffect(() => {
    if (!open || !ownerId) return;
    setLoading(true);
    const url =
      mode === "club"
        ? `/api/community/showcase/clubs/${encodeURIComponent(ownerId)}?viewer_uid=${encodeURIComponent(operatorUid)}`
        : `/api/community/showcase/coaches/${encodeURIComponent(ownerId)}?viewer_uid=${encodeURIComponent(operatorUid)}`;

    apiClient
      .get(url)
      .then((res: any) => {
        if (res.data?.can_edit === false) {
          showToast(
            mode === "club" ? "仅本跑团主理人/团长可编辑跑团宣传主页" : "仅教练/团长本人可编辑个人风采主页",
            "error"
          );
          onClose();
          return;
        }
        setPhotos(res.data?.photos || []);
        if (mode === "club") {
          const sc = res.data?.showcase || {};
          setSlogan(sc.slogan || "");
          setStyleTagsText((sc.style_tags || []).join("、"));
          setLandmarksText((sc.home_landmarks || []).join("、"));
          setScheduleSummary(sc.schedule_summary || "");
          setHighlightsMd(sc.highlights_md || "");
        } else {
          const r = res.data?.resume || {};
          setHeadline(r.headline || "");
          setSpecialtyText((r.specialty_tags || []).join("、"));
          const certs = r.certifications || [];
          setCertTitle(certs.map((c: any) => c.title || c).filter(Boolean).join("、"));
          setBioStory(r.bio_story || "");
          setPhilosophy(r.coaching_philosophy || "");
        }
      })
      .catch((e: any) => showToast("加载宣传页失败：" + (e?.message || ""), "error"))
      .finally(() => setLoading(false));
  }, [open, mode, ownerId, operatorUid, showToast]);

  if (!open) return null;

  function splitTags(txt: string): string[] {
    return txt
      .split(/[,，、;\n]+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }

  async function handleSaveText(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      if (mode === "club") {
        await apiClient.put(`/api/community/showcase/clubs/${encodeURIComponent(ownerId)}`, {
          operator_uid: operatorUid,
          slogan: slogan.trim(),
          style_tags: splitTags(styleTagsText),
          home_landmarks: splitTags(landmarksText),
          schedule_summary: scheduleSummary.trim(),
          highlights_md: highlightsMd.trim(),
          is_published: true,
        });
      } else {
        const certs = splitTags(certTitle).map((t) => ({ title: t, verified: false }));
        await apiClient.put(`/api/community/showcase/coaches/${encodeURIComponent(ownerId)}`, {
          operator_uid: operatorUid,
          headline: headline.trim(),
          specialty_tags: splitTags(specialtyText),
          certifications: certs,
          bio_story: bioStory.trim(),
          coaching_philosophy: philosophy.trim(),
          is_published: true,
        });
      }
      showToast("✅ 宣传页内容已保存发布");
      onSaved?.();
    } catch (err: any) {
      showToast("保存失败：" + (err?.message || ""), "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleFilesSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    setUploading(true);
    try {
      const uploaded: any[] = [];
      for (const file of Array.from(fileList).slice(0, 6)) {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("owner_type", mode);
        fd.append("owner_id", ownerId);
        fd.append("uploader_uid", operatorUid);
        fd.append("category", uploadCategory);
        fd.append("caption", uploadCaption.trim());
        fd.append("is_cover", photos.length === 0 && uploaded.length === 0 ? "true" : "false");
        const res = await apiClient.post("/api/community/showcase/photos/upload", fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        if (res.data?.photo) uploaded.push(res.data.photo);
      }
      setPhotos((prev) => [...uploaded, ...prev]);
      setUploadCaption("");
      showToast(`📸 已成功上传 ${uploaded.length} 张风采照`);
      onSaved?.();
    } catch (err: any) {
      showToast("上传失败：" + (err?.message || "格式需为 JPG/PNG/WebP"), "error");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleSetCover(photoId: string) {
    try {
      await apiClient.patch(`/api/community/showcase/photos/${photoId}`, {
        operator_uid: operatorUid,
        is_cover: true,
      });
      setPhotos((prev) => prev.map((p) => ({ ...p, is_cover: p.id === photoId })));
      showToast("⭐ 已设为宣传页主封面");
      onSaved?.();
    } catch (e: any) {
      showToast("设置封面失败：" + (e?.message || ""), "error");
    }
  }

  async function handleDeletePhoto(photoId: string) {
    const ok = await askConfirm({ title: "删除照片", message: "确认从宣传相册墙移除这张照片？", danger: true });
    if (!ok) return;
    try {
      await apiClient.delete(`/api/community/showcase/photos/${photoId}?operator_uid=${encodeURIComponent(operatorUid)}`);
      setPhotos((prev) => prev.filter((p) => p.id !== photoId));
      showToast("已删除照片");
      onSaved?.();
    } catch (e: any) {
      showToast("删除失败：" + (e?.message || ""), "error");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="rgm-bento-card max-w-2xl w-full p-6 space-y-5 shadow-2xl my-8">
        <div className="flex items-center justify-between border-b border-[var(--rgm-divider)] pb-3">
          <h3 className="text-base font-black text-[var(--rgm-text)]">
            {mode === "club" ? "🎨 装修跑团品牌宣传页 & 实拍相册墙" : "🏅 编辑团长/教练资历主页与风采相册"}
          </h3>
          <button type="button" onClick={onClose} className="text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)] cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {loading ? (
          <div className="py-10 text-center text-xs text-[var(--rgm-text-muted)]">加载宣传页资料中...</div>
        ) : (
          <>
            <form onSubmit={handleSaveText} className="space-y-3">
              {mode === "club" ? (
                <>
                  <div>
                    <label className="text-xs font-bold text-[var(--rgm-text-2)] block mb-1">品牌 Slogan / 核心宣言</label>
                    <input
                      type="text"
                      value={slogan}
                      onChange={(e) => setSlogan(e.target.value)}
                      placeholder="例如：张江科学长跑 · 严肃破330与健康耐力兼修"
                      className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-bold text-[var(--rgm-text-2)] block mb-1">跑团风格标签（逗号分隔）</label>
                      <input
                        type="text"
                        value={styleTagsText}
                        onChange={(e) => setStyleTagsText(e.target.value)}
                        placeholder="如：破330特训、戈赛梯队、新手友好"
                        className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-[var(--rgm-text-2)] block mb-1">常驻合练公园地标（逗号分隔）</label>
                      <input
                        type="text"
                        value={landmarksText}
                        onChange={(e) => setLandmarksText(e.target.value)}
                        placeholder="如：世纪公园、卢湾体育场"
                        className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-[var(--rgm-text-2)] block mb-1">固定合练排期与分组说明</label>
                    <input
                      type="text"
                      value={scheduleSummary}
                      onChange={(e) => setScheduleSummary(e.target.value)}
                      placeholder="例如：每周三 19:00 卢湾间歇 · 周六 06:00 世纪公园 7号门 20-30km 官兔领跑"
                      className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-bold text-[var(--rgm-text-2)] block mb-1">跑团亮点故事 / 迎新介绍</label>
                    <textarea
                      rows={3}
                      value={highlightsMd}
                      onChange={(e) => setHighlightsMd(e.target.value)}
                      placeholder="介绍跑团文化、补给保障、近年戈赛或上马集体成绩..."
                      className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                    />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="text-xs font-bold text-[var(--rgm-text-2)] block mb-1">个人头衔标语（如：上马255主教练 · AHA急救官）</label>
                    <input
                      type="text"
                      value={headline}
                      onChange={(e) => setHeadline(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-bold text-[var(--rgm-text-2)] block mb-1">执教擅长领域（逗号分隔）</label>
                      <input
                        type="text"
                        value={specialtyText}
                        onChange={(e) => setSpecialtyText(e.target.value)}
                        placeholder="如：Canova周期化、破300、伤病防复发"
                        className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-[var(--rgm-text-2)] block mb-1">专业资质证书（逗号分隔）</label>
                      <input
                        type="text"
                        value={certTitle}
                        onChange={(e) => setCertTitle(e.target.value)}
                        placeholder="如：中国田协教练证、AHA急救证"
                        className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-[var(--rgm-text-2)] block mb-1">跑马与执教履历简介（注：手表核验PB与官兔次数由系统自动防伪聚合）</label>
                    <textarea
                      rows={3}
                      value={bioStory}
                      onChange={(e) => setBioStory(e.target.value)}
                      className="w-full px-3 py-2 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                    />
                  </div>
                </>
              )}

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-black flex items-center gap-1.5 cursor-pointer disabled:opacity-60"
                >
                  <Save className="w-3.5 h-3.5" />
                  {saving ? "发布中..." : "保存并发布资料"}
                </button>
              </div>
            </form>

            {/* Categorized Photo Upload Wall */}
            <div className="pt-4 border-t border-[var(--rgm-divider)] space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs font-black text-[var(--rgm-text)]">
                  📸 宣传实景照片墙 ({photos.length}/36)
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <select
                    value={uploadCategory}
                    onChange={(e) => setUploadCategory(e.target.value)}
                    className="px-2.5 py-1.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)]"
                  >
                    {PHOTO_CATEGORIES.map((c) => (
                      <option key={c.key} value={c.key}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={uploadCaption}
                    onChange={(e) => setUploadCaption(e.target.value)}
                    placeholder="照片说明（选填）"
                    className="px-2.5 py-1.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text)] w-32"
                  />
                  <label className="px-3 py-1.5 rounded-xl bg-emerald-600 text-white text-xs font-bold flex items-center gap-1 cursor-pointer hover:bg-emerald-500">
                    <Upload className="w-3.5 h-3.5" />
                    {uploading ? "上传中..." : "上传大片"}
                    <input type="file" accept="image/*" multiple onChange={handleFilesSelected} className="hidden" />
                  </label>
                </div>
              </div>

              {photos.length > 0 && (
                <div className="grid grid-cols-3 sm:grid-cols-4 gap-2.5 max-h-60 overflow-y-auto pr-1">
                  {photos.map((p) => (
                    <div key={p.id} className="relative rounded-xl overflow-hidden border border-[var(--rgm-border)] group aspect-square bg-[var(--rgm-card-2)]">
                      <img src={p.photo_url} alt={p.caption || "photo"} className="w-full h-full object-cover" />
                      {p.is_cover && (
                        <span className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded bg-[#FC4C02] text-white text-[9px] font-black">
                          主封面
                        </span>
                      )}
                      <div className="absolute inset-x-0 bottom-0 bg-black/70 px-1.5 py-1 flex items-center justify-between gap-1 opacity-0 group-hover:opacity-100 transition">
                        {mode === "club" && !p.is_cover && (
                          <button
                            type="button"
                            onClick={() => handleSetCover(p.id)}
                            className="text-[10px] text-amber-300 font-bold flex items-center gap-0.5 cursor-pointer"
                          >
                            <Star className="w-3 h-3" /> 封面
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => handleDeletePhoto(p.id)}
                          className="text-[10px] text-rose-400 font-bold ml-auto cursor-pointer"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
