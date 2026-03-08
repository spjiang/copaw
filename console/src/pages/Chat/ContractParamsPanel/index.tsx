import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Input,
  message,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  FileTextOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import { getApiUrl } from "../../../api/config";
import { normalizeSkillEvent, SkillEvent } from "../skillEvent";

const { Text, Paragraph } = Typography;

interface ParamTableRow {
  path: string;
  field_name?: string;
  group?: string;
  desc?: string;
  required?: boolean;
  value?: unknown;
  display_value?: string;
  status?: string;
}

interface ParamTableSummary {
  total_fields?: number;
  filled_fields?: number;
  missing_fields_count?: number;
  missing_fields?: string[];
}

interface ParamTableData {
  rows?: ParamTableRow[];
  summary?: ParamTableSummary;
}

interface UpdateContext {
  paramsFile: string;
  execId: string;
  userId: string;
}

interface Props {
  sessionId: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function extractParamTable(event: SkillEvent): ParamTableData | null {
  if (!isRecord(event.output)) {
    return null;
  }
  const paramTable = event.output.param_table;
  if (!isRecord(paramTable)) {
    return null;
  }
  return {
    rows: Array.isArray(paramTable.rows) ? (paramTable.rows as ParamTableRow[]) : [],
    summary: isRecord(paramTable.summary) ? (paramTable.summary as ParamTableSummary) : {},
  };
}

function toEditableValue(value: unknown): string {
  if (value == null) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function ContractParamsPanel({ sessionId }: Props) {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<SkillEvent | null>(null);
  const [tableData, setTableData] = useState<ParamTableData | null>(null);
  const [context, setContext] = useState<UpdateContext | null>(null);
  const [draftValues, setDraftValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId) {
      esRef.current?.close();
      setConnected(false);
      setLastEvent(null);
      setTableData(null);
      setContext(null);
      setDraftValues({});
      return;
    }

    esRef.current?.close();
    setConnected(false);
    setLastEvent(null);
    setTableData(null);
    setContext(null);
    setDraftValues({});

    const url = getApiUrl(`/redis/stream/${encodeURIComponent(sessionId)}?last_id=0`);
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      setConnected(true);
    };

    es.onmessage = (e) => {
      try {
        const event = normalizeSkillEvent(JSON.parse(e.data) as SkillEvent);
        if (event.type === "connected") {
          setConnected(true);
          return;
        }
        if (event.type !== "skill_event") {
          return;
        }

        const extracted = extractParamTable(event);
        if (!extracted) {
          return;
        }

        setLastEvent(event);
        setTableData(extracted);
        setContext({
          paramsFile:
            isRecord(event.input) && typeof event.input.params_file === "string"
              ? event.input.params_file
              : "",
          execId: event.exec_id || "",
          userId: event.user_id || "",
        });
        setDraftValues(
          Object.fromEntries(
            (extracted.rows || []).map((row) => [row.path, toEditableValue(row.value)])
          )
        );
      } catch {
        // Ignore malformed SSE payloads.
      }
    };

    es.onerror = () => {
      setConnected(false);
    };

    return () => {
      es.close();
    };
  }, [sessionId]);

  const rows = useMemo(() => tableData?.rows || [], [tableData]);
  const summary = tableData?.summary || {};
  const changedRows = useMemo(
    () =>
      rows.filter((row) => (draftValues[row.path] ?? "") !== toEditableValue(row.value)),
    [draftValues, rows]
  );
  const updatedAt = lastEvent?.timestamp
    ? new Date(lastEvent.timestamp).toLocaleTimeString("zh-CN", { hour12: false })
    : "";

  const handleReset = () => {
    setDraftValues(
      Object.fromEntries(rows.map((row) => [row.path, toEditableValue(row.value)]))
    );
  };

  const handleSubmit = async () => {
    if (!context?.paramsFile || !context?.execId) {
      message.error("缺少参数文件上下文，请先重新触发一次模板参数采集。");
      return;
    }
    if (!changedRows.length) {
      message.info("当前没有待提交的修改。");
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(getApiUrl("/contract-params/update"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          params_file: context.paramsFile,
          exec_id: context.execId,
          session_id: sessionId,
          user_id: context.userId,
          updates: changedRows.map((row) => ({
            path: row.path,
            value: draftValues[row.path] ?? "",
          })),
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data?.ok) {
        throw new Error(data?.detail || data?.message || "提交失败");
      }
      message.success(`已提交 ${changedRows.length} 项参数，右侧总表将自动刷新。`);
    } catch (error) {
      message.error((error as Error)?.message || "批量更新失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "#fafafa",
      }}
    >
      <div
        style={{
          padding: "8px 12px",
          background: "#fff",
          borderBottom: "1px solid #e8e8e8",
          flexShrink: 0,
        }}
      >
        <Space size={6} wrap>
          <FileTextOutlined style={{ color: "#722ed1" }} />
          <Text strong style={{ fontSize: 13 }}>合同参数总表</Text>
          <Badge
            status={connected ? "success" : "processing"}
            text={
              <Text style={{ fontSize: 11 }} type="secondary">
                {connected ? "同步中" : <><LoadingOutlined /> 连接中</>}
              </Text>
            }
          />
        </Space>
        <div style={{ marginTop: 6 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            支持一次修改多个字段并提交；提交后会重新推送参数事件，聊天窗口和右侧总表会一起刷新。
          </Text>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: 12 }}>
        {!rows.length ? (
          <Card size="small">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="当前还没有合同参数总表，请先触发一次模板参数采集。"
            />
          </Card>
        ) : (
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Alert
              type="info"
              showIcon
              message="批量填写说明"
              description="直接在“当前值”列中修改多个参数，点击“提交批量更新”即可。留空表示清空当前值。"
            />
            <Card size="small" styles={{ body: { padding: 12 } }}>
              <Space wrap size={[8, 8]}>
                <Tag color="blue">总参数 {summary.total_fields || rows.length}</Tag>
                <Tag color="green">已填写 {summary.filled_fields || 0}</Tag>
                <Tag color="orange">待填写 {summary.missing_fields_count || 0}</Tag>
                <Tag color={changedRows.length ? "gold" : "default"}>待提交 {changedRows.length}</Tag>
                {lastEvent?.event_name && <Tag>{lastEvent.event_name}</Tag>}
                {updatedAt && <Tag bordered={false}>更新时间 {updatedAt}</Tag>}
              </Space>
              <Space style={{ marginTop: 10 }} wrap>
                <Button size="small" onClick={handleReset} disabled={!changedRows.length || saving}>
                  重置本次修改
                </Button>
                <Button
                  size="small"
                  type="primary"
                  loading={saving}
                  onClick={handleSubmit}
                  disabled={!changedRows.length}
                >
                  提交批量更新
                </Button>
              </Space>
              {Array.isArray(summary.missing_fields) && summary.missing_fields.length > 0 && (
                <Paragraph style={{ marginTop: 10, marginBottom: 0 }}>
                  <Text strong>当前仍缺少：</Text> {summary.missing_fields.join("、")}
                </Paragraph>
              )}
            </Card>

            <Card
              size="small"
              title="当前参数明细"
              extra={
                <Tooltip title="表格内容来自 Redis 事件中的 output.param_table">
                  <Text type="secondary" style={{ fontSize: 12 }}>实时同步</Text>
                </Tooltip>
              }
              styles={{ body: { padding: 0 } }}
            >
              <Table<ParamTableRow>
                rowKey={(record) => record.path}
                dataSource={rows}
                pagination={false}
                size="small"
                scroll={{ x: 720, y: 520 }}
                columns={[
                  {
                    title: "参数名称",
                    dataIndex: "field_name",
                    key: "field_name",
                    width: 130,
                    render: (_, record) => (
                      <Space direction="vertical" size={0}>
                        <Text strong>{record.field_name || record.path}</Text>
                        {record.group && (
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            分组：{record.group}
                          </Text>
                        )}
                      </Space>
                    ),
                  },
                  {
                    title: "填写说明",
                    dataIndex: "desc",
                    key: "desc",
                    width: 220,
                    render: (value: string | undefined) => value || <Text type="secondary">未提供说明</Text>,
                  },
                  {
                    title: "当前值",
                    dataIndex: "display_value",
                    key: "display_value",
                    width: 260,
                    render: (_value: string | undefined, record) => (
                      <Input.TextArea
                        autoSize={{ minRows: 1, maxRows: 4 }}
                        value={draftValues[record.path] ?? ""}
                        placeholder="请输入参数值，可一次编辑多项"
                        onChange={(e) => {
                          const nextValue = e.target.value;
                          setDraftValues((prev) => ({
                            ...prev,
                            [record.path]: nextValue,
                          }));
                        }}
                      />
                    ),
                  },
                  {
                    title: "状态",
                    dataIndex: "status",
                    key: "status",
                    width: 100,
                    align: "center",
                    render: (_value: string | undefined, record) => {
                      const currentValue = draftValues[record.path] ?? "";
                      if (currentValue.trim()) {
                        return <Tag color="success">已填写</Tag>;
                      }
                      return <Tag color={record.required ? "warning" : "default"}>{record.required ? "待填写" : "可选"}</Tag>;
                    },
                  },
                ]}
              />
            </Card>
          </Space>
        )}
      </div>
    </div>
  );
}
