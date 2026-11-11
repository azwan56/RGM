/**
 * Pure, immutable-snapshot state machine for GoalSheetModal.vue.
 * Extracted so Vue UI and automated unit tests execute the exact same code.
 */

export interface GoalSheetState {
  currentCalMonth: number;
  isDefaultGoal: boolean;
  initialWeeklyKm: number;
  initialTargetDistance: number;
  initialMonthlyArray: number[];
  editWeeklyKm: number;
  editUniformMonthlyKm: number;
  editMonthlyArray: number[];
  hasIndependentMonthly: boolean;
  customMonthMode: boolean;
  autoSyncMonthly: boolean;
  weeklyChangedByUser: boolean;
  monthlyEditedByUser: boolean;
  syncManuallyToggled: boolean;
}

export function calcSyncedMonthlyKm(weeklyKm: number): number {
  return Math.max(40, Math.round((weeklyKm * 4.3) / 10) * 10);
}

export function createGoalSheetState(rawGoal: any, currentCalMonth: number): GoalSheetState {
  const g = rawGoal || {};
  const isDefaultGoal = Boolean(g.is_default || !g.user_id);
  const baseDist = Number(g.target_distance) || 200;
  const wk =
    Number(g.next_weekly_target) ||
    Number(g.weekly_target) ||
    Math.round(baseDist / 4) ||
    50;

  let mArr: number[] = Array(12).fill(baseDist);
  if (Array.isArray(g.monthly_targets) && g.monthly_targets.length > 0) {
    mArr = Array.from({ length: 12 }, (_, i) =>
      Number(g.monthly_targets[i] ?? baseDist) || baseDist
    );
  }

  const futureSlice = currentCalMonth < 12 ? mArr.slice(currentCalMonth) : [baseDist];
  const firstFuture = futureSlice[0] ?? baseDist;
  const isUniformFuture = futureSlice.every((v) => Math.abs(v - firstFuture) < 1);
  const expectedSyncedMonth = calcSyncedMonthlyKm(wk);
  const matchesAutoFormula =
    isUniformFuture && Math.abs(Math.round(firstFuture) - expectedSyncedMonth) < 5;

  // Brand-new users haven't customized per-month targets even though default is 50k/wk & 200k/mo
  const hasIndependentMonthly = !isDefaultGoal && !matchesAutoFormula;

  return {
    currentCalMonth,
    isDefaultGoal,
    initialWeeklyKm: wk,
    initialTargetDistance: baseDist,
    initialMonthlyArray: [...mArr],
    editWeeklyKm: wk,
    editUniformMonthlyKm: Math.round(firstFuture),
    editMonthlyArray: [...mArr],
    hasIndependentMonthly,
    customMonthMode: !isDefaultGoal && !isUniformFuture,
    // Default ON only if existing saved future months already match weekly × 4.3
    autoSyncMonthly: !isDefaultGoal && matchesAutoFormula,
    weeklyChangedByUser: false,
    monthlyEditedByUser: false,
    syncManuallyToggled: false,
  };
}

export function setWeeklyKmInState(st: GoalSheetState, km: number): void {
  const clean = Number(km) || 50;
  st.editWeeklyKm = clean;
  // Note: editMonthlyArray / editUniformMonthlyKm are NEVER mutated here,
  // so changing weekly 50 -> 65 -> 50 or unchecking sync never corrupts original monthly values!
  st.weeklyChangedByUser = clean !== st.initialWeeklyKm;
}

export function toggleAutoSyncInState(st: GoalSheetState): void {
  st.autoSyncMonthly = !st.autoSyncMonthly;
  st.syncManuallyToggled = st.autoSyncMonthly;
  if (st.autoSyncMonthly) {
    st.customMonthMode = false;
  }
}

export function setUniformMonthlyKmInState(st: GoalSheetState, mkm: number): void {
  const clean = Number(mkm) || 200;
  st.customMonthMode = false;
  st.autoSyncMonthly = false;
  st.syncManuallyToggled = false;
  st.monthlyEditedByUser = true;
  st.editUniformMonthlyKm = clean;
  st.editMonthlyArray = st.editMonthlyArray.map((orig, idx) =>
    idx + 1 <= st.currentCalMonth ? orig : clean
  );
}

export function setSingleMonthKmInState(st: GoalSheetState, idx: number, rawVal: string | number): void {
  if (idx + 1 <= st.currentCalMonth) return;
  st.autoSyncMonthly = false;
  st.syncManuallyToggled = false;
  st.monthlyEditedByUser = true;
  st.hasIndependentMonthly = true;
  const n = Math.max(0, Math.min(1000, Number(rawVal) || 0));
  const next = [...st.editMonthlyArray];
  next[idx] = n;
  st.editMonthlyArray = next;
}

export function willStateRewriteFutureMonths(st: GoalSheetState): boolean {
  return st.autoSyncMonthly && (st.weeklyChangedByUser || st.syncManuallyToggled);
}

export function getPreviewNextMonthKm(st: GoalSheetState): number {
  if (willStateRewriteFutureMonths(st)) {
    return calcSyncedMonthlyKm(st.editWeeklyKm);
  }
  if (st.currentCalMonth < 12) {
    const src = st.monthlyEditedByUser ? st.editMonthlyArray : st.initialMonthlyArray;
    return src[st.currentCalMonth] || st.editUniformMonthlyKm;
  }
  return st.monthlyEditedByUser ? st.editUniformMonthlyKm : Math.round(st.initialTargetDistance);
}

export function buildGoalSavePayload(st: GoalSheetState) {
  const wk = Number(st.editWeeklyKm) || 50;
  const shouldSyncMonthly = willStateRewriteFutureMonths(st);

  let targetDist: number;
  let finalMonthly: number[];

  if (shouldSyncMonthly) {
    targetDist = calcSyncedMonthlyKm(wk);
    finalMonthly = st.initialMonthlyArray.map((orig, idx) =>
      idx + 1 <= st.currentCalMonth ? Number(orig) || 0 : targetDist
    );
  } else if (st.monthlyEditedByUser) {
    targetDist = Number(st.editUniformMonthlyKm) || 200;
    finalMonthly = st.editMonthlyArray.map((orig, idx) =>
      idx + 1 <= st.currentCalMonth
        ? Number(st.initialMonthlyArray[idx]) || 0
        : st.customMonthMode
        ? Number(orig) || 0
        : targetDist
    );
  } else {
    // Neither synced nor manually edited on Month tab -> preserve original monthly targets verbatim!
    targetDist = Number(st.initialTargetDistance) || 200;
    finalMonthly = st.initialMonthlyArray.map((v) => Number(v) || 0);
  }

  return {
    shouldSyncMonthly,
    payload: {
      weekly_target: wk,
      next_weekly_target: wk,
      target_distance: targetDist,
      monthly_targets: finalMonthly,
      period_type: "monthly",
      target_period: "next_week",
      enforce_started_lock: true,
    },
  };
}
