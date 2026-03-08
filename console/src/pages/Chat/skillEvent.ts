export interface SkillEvent {
  id: string;
  type: string;
  session_id?: string;
  user_id?: string;
  exec_id?: string;
  skill_name?: string;
  skill_label?: string;
  stage?: "start" | "running" | "end" | "error";
  render_type?: string;
  event_name?: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  timestamp?: string;
  runtime_ms?: number;
  msg?: string;
  data?: string;
}

export function normalizeSkillEvent(raw: SkillEvent): SkillEvent {
  if (raw.skill_name || raw.skill_label || raw.event_name || raw.render_type) {
    return raw;
  }

  const nested = raw.msg || raw.data;
  if (!nested || typeof nested !== "string") {
    return raw;
  }

  try {
    const parsed = JSON.parse(nested);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return { ...raw, ...(parsed as Record<string, unknown>) } as SkillEvent;
    }
  } catch {
    // Ignore malformed historical payloads and keep raw event for debugging.
  }

  return raw;
}
