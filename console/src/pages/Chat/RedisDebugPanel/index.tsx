import { useEffect, useRef, useState } from "react";
import {
  Badge,
  Card,
  Collapse,
  Empty,
  message,
  Space,
  Tag,
  Typography,
  Button,
  Tooltip,
} from "antd";
import {
  ApiOutlined,
  ClearOutlined,
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
} from "@ant-design/icons";
import { getApiUrl } from "../../../api/config";

const { Text, Paragraph } = Typography;

interface SkillEvent {
  id: string;
  type: string;
  session_id?: string;
  exec_id?: string;
  skill_name?: string;
  stage?: "start" | "end" | "error";
  render_type?: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  timestamp?: string;
  runtime_ms?: number;
}

const STAGE_CONFIG = {
  start: { color: "processing", icon: <ClockCircleOutlined />, label: "开始" },
  end:   { color: "success",    icon: <CheckCircleOutlined />,  label: "完成" },
  error: { color: "error",      icon: <CloseCircleOutlined />,  label: "错误" },
} as const;

const SKILL_COLORS: Record<string, string> = {
  contract_template_match_by_file: "#1677ff",
  contract_template_match:          "#096dd9",
  contract_template_params:         "#722ed1",
  contract_word_gen:                "#389e0d",
  contract_draft:                   "#d46b08",
};

function JsonBlock({ data }: { data: unknown }) {
  return (
    <Paragraph
      style={{
        background: "#0d1117",
        color: "#e6edf3",
        padding: "10px 12px",
        borderRadius: 6,
        fontSize: 12,
        fontFamily: "monospace",
        margin: 0,
        maxHeight: 300,
        overflow: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
      }}
      copyable={{ text: JSON.stringify(data, null, 2) }}
    >
      {JSON.stringify(data, null, 2)}
    </Paragraph>
  );
}

function EventCard({ event, index }: { event: SkillEvent; index: number }) {
  const stage = event.stage as keyof typeof STAGE_CONFIG | undefined;
  const stageCfg = stage ? STAGE_CONFIG[stage] : null;
  const skillColor = SKILL_COLORS[event.skill_name || ""] || "#595959";
  const time = event.timestamp
    ? new Date(event.timestamp).toLocaleTimeString("zh-CN", { hour12: false })
    : "";

  const collapseItems = [
    event.input && Object.keys(event.input).length > 0 && {
      key: "input",
      label: <Text strong style={{ color: "#1677ff" }}>Input</Text>,
      children: <JsonBlock data={event.input} />,
    },
    event.output && Object.keys(event.output).length > 0 && {
      key: "output",
      label: <Text strong style={{ color: "#52c41a" }}>Output</Text>,
      children: <JsonBlock data={event.output} />,
    },
    {
      key: "full",
      label: <Text type="secondary" style={{ fontSize: 12 }}>完整 JSON</Text>,
      children: <JsonBlock data={event} />,
    },
  ].filter(Boolean) as { key: string; label: React.ReactNode; children: React.ReactNode }[];

  return (
    <Card
      size="small"
      style={{ marginBottom: 8, borderLeft: `3px solid ${skillColor}` }}
      styles={{ body: { padding: "8px 10px" } }}
    >
      {/* Header row */}
      <Space style={{ width: "100%", justifyContent: "space-between", flexWrap: "wrap", gap: 4 }}>
        <Space size={4} wrap>
          <Text style={{ color: "#999", fontSize: 11 }}>#{index + 1}</Text>
          <Tag
            color={skillColor}
            style={{ fontSize: 11, fontWeight: 600, margin: 0 }}
          >
            {event.skill_name || event.type}
          </Tag>
          {stageCfg && (
            <Badge
              status={stageCfg.color as any}
              text={
                <Text style={{ fontSize: 11 }}>
                  {stageCfg.icon} {stageCfg.label}
                </Text>
              }
            />
          )}
          {event.render_type && (
            <Tag style={{ fontSize: 10, margin: 0, color: "#666" }} bordered={false}>
              {event.render_type}
            </Tag>
          )}
        </Space>
        <Space size={4}>
          {event.runtime_ms != null && event.runtime_ms > 0 && (
            <Text type="secondary" style={{ fontSize: 10 }}>
              {event.runtime_ms}ms
            </Text>
          )}
          <Text type="secondary" style={{ fontSize: 10 }}>{time}</Text>
        </Space>
      </Space>

      {/* exec_id */}
      {event.exec_id && (
        <Text
          type="secondary"
          style={{ fontSize: 10, display: "block", marginTop: 2 }}
          ellipsis
        >
          exec: {event.exec_id}
        </Text>
      )}

      {/* Collapsible input/output/full json */}
      <Collapse
        ghost
        size="small"
        style={{ marginTop: 6 }}
        items={collapseItems}
      />
    </Card>
  );
}

interface Props {
  sessionId: string;
}

export default function RedisDebugPanel({ sessionId }: Props) {
  const [events, setEvents] = useState<SkillEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const testRedisConnection = async () => {
    setTesting(true);
    try {
      const resp = await fetch(getApiUrl("/redis/ping"));
      const data = await resp.json();
      if (data?.ok) {
        message.success(`Redis 连接成功：${data.host}:${data.port}/db${data.db}`);
      } else {
        message.error(`Redis 连接失败：${data?.error || "unknown error"}`);
      }
    } catch (e) {
      message.error(`Redis 测试请求失败：${(e as Error)?.message || "network error"}`);
    } finally {
      setTesting(false);
    }
  };

  useEffect(() => {
    if (!sessionId) {
      esRef.current?.close();
      setConnected(false);
      setError("未获取会话ID，请先发送一条消息");
      return;
    }

    // Close previous connection
    esRef.current?.close();
    setEvents([]);
    setConnected(false);
    setError(null);

    // 先做一次连通性探测，避免界面一直显示“连接中”
    fetch(getApiUrl("/redis/ping"))
      .then((r) => r.json())
      .then((d) => {
        if (!d?.ok) {
          setError(`Redis 不可用：${d?.error || "unknown error"}`);
        }
      })
      .catch((e) => {
        setError(`Redis 测试失败：${(e as Error)?.message || "network error"}`);
      });

    // last_id=0 表示从该 session stream 的最早消息开始读，面板打开时能看到历史事件
    const url = getApiUrl(`/redis/stream/${encodeURIComponent(sessionId)}?last_id=0`);
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
      setError(null);
    };

    es.onmessage = (e) => {
      try {
        const data: SkillEvent = JSON.parse(e.data);
        if (data.type === "connected") {
          setConnected(true);
          return;
        }
        if (data.type === "skill_event") {
          setEvents((prev) => [...prev, data]);
          // Auto scroll to bottom
          setTimeout(() => {
            bottomRef.current?.scrollIntoView({ behavior: "smooth" });
          }, 50);
          return;
        }
        if (data.type === "error" || (data as any).error) {
          setConnected(false);
          setError((data as any).message || (data as any).error || "Redis 连接失败");
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      setConnected(false);
      setError("连接断开，将自动重连...");
    };

    return () => {
      es.close();
    };
  }, [sessionId]);

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "#f5f5f5",
      }}
    >
      {/* Toolbar */}
      <div
        style={{
          padding: "8px 12px",
          background: "#fff",
          borderBottom: "1px solid #e8e8e8",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <Space size={6}>
          <ApiOutlined style={{ color: "#1677ff" }} />
          <Text strong style={{ fontSize: 13 }}>Redis 调试面板</Text>
          <Badge
            status={connected ? "success" : "error"}
            text={
              <Text style={{ fontSize: 11 }} type="secondary">
                {connected ? "已连接" : error ? "断开" : <><LoadingOutlined /> 连接中</>}
              </Text>
            }
          />
        </Space>
        <Space size={4}>
          <Tooltip title="手动测试 Redis 连接">
            <Button
              size="small"
              type="text"
              loading={testing}
              onClick={testRedisConnection}
            >
              测试连接
            </Button>
          </Tooltip>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {events.length} 条
          </Text>
          <Tooltip title="清空">
            <Button
              size="small"
              icon={<ClearOutlined />}
              type="text"
              onClick={() => setEvents([])}
            />
          </Tooltip>
        </Space>
      </div>

      {/* Session ID */}
      <div style={{ padding: "4px 12px", background: "#fafafa", borderBottom: "1px solid #f0f0f0" }}>
        <Text type="secondary" style={{ fontSize: 10 }}>
          session: <Text code style={{ fontSize: 10 }}>{sessionId || "—"}</Text>
        </Text>
      </div>

      {/* Events list */}
      <div style={{ flex: 1, overflow: "auto", padding: "8px 8px 0" }}>
        {events.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Text type="secondary" style={{ fontSize: 12 }}>
                {connected
                  ? "等待 skill 执行事件..."
                  : "正在连接 Redis..."}
              </Text>
            }
            style={{ marginTop: 40 }}
          />
        ) : (
          events.map((ev, i) => (
            <EventCard key={ev.id || i} event={ev} index={i} />
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
