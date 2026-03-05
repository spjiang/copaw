import {
  AgentScopeRuntimeWebUI,
  IAgentScopeRuntimeWebUIOptions,
} from "@agentscope-ai/chat";
import { useEffect, useMemo, useState } from "react";
import { Modal, Button, Result, Tooltip } from "antd";
import { ExclamationCircleOutlined, SettingOutlined, BugOutlined } from "@ant-design/icons";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import sessionApi from "./sessionApi";
import { useLocalStorageState } from "ahooks";
import defaultConfig, { DefaultConfig } from "./OptionsPanel/defaultConfig";
import Weather from "./Weather";
import RedisDebugPanel from "./RedisDebugPanel";
import { getApiUrl, getApiToken } from "../../api/config";
import { providerApi } from "../../api/modules/provider";
import "./index.module.less";

interface CustomWindow extends Window {
  currentSessionId?: string;
  currentUserId?: string;
  currentChannel?: string;
}

declare const window: CustomWindow;

type OptionsConfig = DefaultConfig;

export default function ChatPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [showModelPrompt, setShowModelPrompt] = useState(false);
  const [showDebugPanel, setShowDebugPanel] = useLocalStorageState<boolean>(
    "redis-debug-panel-visible",
    { defaultValue: false },
  );
  const [debugSessionId, setDebugSessionId] = useState<string>("");

  // Keep debug panel session in sync even before sending message.
  useEffect(() => {
    const timer = window.setInterval(() => {
      const sid = window.currentSessionId || "";
      if (sid) setDebugSessionId((prev) => (prev === sid ? prev : sid));
    }, 500);
    return () => window.clearInterval(timer);
  }, []);
  const [optionsConfig] = useLocalStorageState<OptionsConfig>(
    "agent-scope-runtime-webui-options",
    {
      defaultValue: defaultConfig,
      listenStorageChange: true,
    },
  );

  const handleConfigureModel = () => {
    setShowModelPrompt(false);
    navigate("/models");
  };

  const handleSkipConfiguration = () => {
    setShowModelPrompt(false);
  };

  const options = useMemo(() => {
    const handleModelError = () => {
      setShowModelPrompt(true);
      return new Response(
        JSON.stringify({
          error: "Model not configured",
          message: "Please configure a model first",
        }),
        {
          status: 400,
          headers: { "Content-Type": "application/json" },
        },
      );
    };

    const customFetch = async (data: {
      input: any[];
      biz_params?: any;
    }): Promise<Response> => {
      try {
        const activeModels = await providerApi.getActiveModels();

        if (
          !activeModels?.active_llm?.provider_id ||
          !activeModels?.active_llm?.model
        ) {
          return handleModelError();
        }
      } catch (error) {
        console.error("Failed to check model configuration:", error);
        return handleModelError();
      }

      const { input, biz_params } = data;

      const lastMessage = input[input.length - 1];
      const session = lastMessage?.session || {};

      const session_id = window.currentSessionId || session?.session_id || "";
      const user_id = window.currentUserId || session?.user_id || "default";
      // Sync session_id to debug panel
      if (session_id) setDebugSessionId(session_id);
      const channel = window.currentChannel || session?.channel || "console";

      const requestBody = {
        input: input.slice(-1),
        session_id,
        user_id,
        channel,
        stream: true,
        ...biz_params,
      };

      const headers: HeadersInit = {
        "Content-Type": "application/json",
      };

      const token = getApiToken();
      if (token) {
        (headers as Record<string, string>).Authorization = `Bearer ${token}`;
      }

      const url = optionsConfig?.api?.baseURL || getApiUrl("/agent/process");
      return fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(requestBody),
      });
    };

    // File upload endpoint (backend saves file and returns { url, name, size })
    const baseURL = (optionsConfig?.api?.baseURL as string) || "";
    const uploadUrl = baseURL
      ? baseURL.replace("/agent/process", "").replace(/\/$/, "") + "/files/upload"
      : getApiUrl("/files/upload");

    const token = getApiToken();

    return {
      ...optionsConfig,
      session: {
        multiple: true,
        api: sessionApi,
      },
      theme: {
        ...optionsConfig.theme,
      },
      sender: {
        ...optionsConfig.sender,
        // useAttachments only renders the upload button when customRequest is provided
        attachments: {
          accept: ".pdf,.docx,.doc,.xlsx,.xls,.csv,.txt,.md,.png,.jpg,.jpeg,.gif,.webp",
          multiple: false,
          maxCount: 3,
          customRequest: async (options: any) => {
            const { file, onSuccess, onError, onProgress } = options;
            const formData = new FormData();
            formData.append("file", file);
            try {
              onProgress?.({ percent: 30 });
              const res = await fetch(uploadUrl, {
                method: "POST",
                headers: token ? { Authorization: `Bearer ${token}` } : {},
                body: formData,
              });
              if (!res.ok) {
                const err = await res.text();
                onError?.(new Error(err));
                return;
              }
              onProgress?.({ percent: 100 });
              const data = await res.json();
              // onSuccess receives the response as file.response in the file list
              onSuccess?.(data, file);
            } catch (e: any) {
              onError?.(e);
            }
          },
        },
      },
      api: {
        ...optionsConfig.api,
        fetch: customFetch,
        cancel(data: { session_id: string }) {
          console.log(data);
        },
      },
      customToolRenderConfig: {
        "weather search mock": Weather,
      },
    } as unknown as IAgentScopeRuntimeWebUIOptions;
  }, [optionsConfig]);

  return (
    <div style={{ height: "100%", width: "100%", display: "flex", position: "relative" }}>
      {/* Chat area */}
      <div style={{ flex: 1, minWidth: 0, height: "100%" }}>
        <AgentScopeRuntimeWebUI options={options} />
      </div>

      {/* Debug panel toggle button */}
      <Tooltip title={showDebugPanel ? "隐藏 Redis 调试面板" : "显示 Redis 调试面板"} placement="left">
        <Button
          icon={<BugOutlined />}
          size="small"
          type={showDebugPanel ? "primary" : "default"}
          onClick={() => setShowDebugPanel(!showDebugPanel)}
          style={{
            position: "absolute",
            right: showDebugPanel ? 362 : 4,
            top: 10,
            zIndex: 100,
            transition: "right 0.2s",
          }}
        />
      </Tooltip>

      {/* Redis debug panel */}
      {showDebugPanel && (
        <div
          style={{
            width: 360,
            height: "100%",
            flexShrink: 0,
            borderLeft: "1px solid #e8e8e8",
            background: "#f5f5f5",
          }}
        >
          <RedisDebugPanel sessionId={debugSessionId} />
        </div>
      )}

      <Modal open={showModelPrompt} closable={false} footer={null} width={480}>
        <Result
          icon={<ExclamationCircleOutlined style={{ color: "#faad14" }} />}
          title={t("modelConfig.promptTitle")}
          subTitle={t("modelConfig.promptMessage")}
          extra={[
            <Button key="skip" onClick={handleSkipConfiguration}>
              {t("modelConfig.skipButton")}
            </Button>,
            <Button
              key="configure"
              type="primary"
              icon={<SettingOutlined />}
              onClick={handleConfigureModel}
            >
              {t("modelConfig.configureButton")}
            </Button>,
          ]}
        />
      </Modal>
    </div>
  );
}

