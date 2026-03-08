# 项目背景

我现在在做一个合同起草智能体

# 智能体（skill）介绍

## contract_draft

主智能体主要是用于智能体编排

获取用户上传附件信息

file_list = os.environ.get("COPAW_INPUT_FILE_URLS") 是获取当前用户上传的附件列表

redis 进行推送智能体开始运行，json 结构如下：
    {
        "session_id": "xxx",
        "exec_id": "xxx",
        "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "skill_name": "contract_draft",
        "stage": "start",
        "render_type": "agent_start",
        "input": { ... },
        "output": {
            "file_list": os.environ.get("COPAW_INPUT_FILE_URLS") ,
        },
        "timestamp": "...",
        "runtime_ms": 0
    }


if file_list 为空，代表用户未上传附件
   AI 回复：请上传合同模板附件，引导用户上传，当然用户也可以直接选择起草、跳过合同模板上传
   如果用户坚持直接起草：那么调用子智能体contract_template_llm（skill），只有附件为空时，才调用。
if file_list 不为空
   调用合同模板匹配子智能体contract_template_match（skill），只有附件不为空时，才调用。


redis 进行推送智能体结束运行，json 结构如下：
    {
        "session_id": "xxx",
        "exec_id": "xxx",
        "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "skill_name": "contract_draft",
        "stage": "end",
        "render_type": "agent_end",
        "input": { ... },
        "output": {
            "file_list": os.environ.get("COPAW_INPUT_FILE_URLS") ,
        },
        "timestamp": "...",
        "runtime_ms": 0
    }

## contract_template_match

redis 进行推送contract_template_match智能体开始工作了，在中进行contract_template_match返回，json 结构如下：
    {
        "session_id": "xxx",
        "exec_id": "xxx",
        "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "skill_name": "contract_template_match",
        "stage": "start",
        "render_type": "agent_start",
        "input": { ... },
        "output": {
            "file_list": os.environ.get("COPAW_INPUT_FILE_URLS") ,
        },
        "timestamp": "...",
        "runtime_ms": 0
    }


file_list = os.environ.get("COPAW_INPUT_FILE_URLS") 是获取当前用户上传的附件列表


user_upload_contract_template_url：用户自己在聊天窗口上传合同模板，如：user_contract_template_url = "http://10.156.196.158:9000/yuanti/docxtpl/5-软件产品销售合同.docx"，user_upload_contract_template_url数据来至于file_list；获取其中最新的一条数据，因为file_list为 list 格式，可能存在多条数附件数据

user_upload_contract_template_file_name: 根据user_upload_contract_template_url变量，用户自己在聊天窗口上传合同模板文件提取合同模板文件名称名称，如：user_contract_template_file_name = "5-软件产品销售合同"；

user_choose_contract_template_url: 这个变量是用户二次选择匹配到多条合同模板时，进行二次确认的合同模板地址或 file_list只有一条数据时，进行赋值的。如模板文件 url 地址，"http://10.156.196.158:19000/copaw-files/users/1/2026/03/5e25dc5566f849f0b38e00f04aca1745.xlsx"


user_choose_contract_template_params: 合同模板模版中的占位符，选择确认后的合同模版中对应param_schema_json字段赋值


通过会话语义和判断是否有上传合同模板附件，判断file_list是否存在

步骤 1：
if：判断file_list是否存在：如果存在合同模板附件
     
     user_upload_contract_template_url = os.environ.get("COPAW_INPUT_FILE_URLS")，通过user_contract_template_url提取合同模板文件名称keyword_name;

if：判断file_list是否存在：不存在合同模板附件
   通过大模型分析用户对话，分析出用户是起草一份销售合同、采购合同、房屋租赁合同等，如用户输入：帮我起草一份销售合同；进行keyword_name参数赋值，keyword_name="销售"



步骤 2：
数据库模板名称检索匹配（PostgreSQL）
    数据库连接信息：
    IP：10.156.196.158
    Port:5432
    User:user_t8ZA3i
    Password:password_DTXtQH

    执行SQL：SELECT * FROM "public"."contract_templates" WHERE "title" LIKE '%keyword_name%'; 获取匹配到合同模板列表template_list参数，在进行template_list = 获取匹配到合同模板列表赋值



步骤 3：
case: 合同模板列表template_list有数据时
    进行用户二次确认，选择哪一个合同模板，在根据选择的合同模板 id，获取到 file_path,进行user_choose_contract_template_url赋值，规则为user_choose_contract_template_url = "http://10.156.196.158:19000/copaw-files"+file_path进行拼接。

    redis 进行推送在output 中进行user_choose_contract_template_url返回，json 结构如下：
    {
        "session_id": "xxx",
        "exec_id": "xxx",
        "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "skill_name": "contract_template_match",
        "stage": "running",
        "render_type": "user_choose_contract_template_url",
        "input": { ... },
        "output": {
            "template_id":对应的模板 ID，对应 id
            "template_url":user_choose_contract_template_url对应的值,
            "param_schema_json": 对应的param_schema_json字段数据,
        },
        "timestamp": "...",
        "runtime_ms": 0
    }
    调用 contract_template_params 智能体


case: 合同模板列表template_list数据为空时
    因为template_list数据为空，所以user_choose_contract_template_url也为空，直接使用用户上传的模板文件进行模板渲染，调用渲染 API 接口
    redis 进行推送在output 中进行user_choose_contract_template_url返回，json 结构如下：
    {
        "session_id": "xxx",
        "exec_id": "xxx",
        "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "skill_name": "contract_template_match",
        "stage": "running",
        "render_type": "user_choose_contract_template_url",
        "input": { ... },
        "output": {
            "template_id":"",这里为空
            "template_url":"",这里为空
            "param_schema_json": 这里为空,
        },
        "timestamp": "...",
        "runtime_ms": 0
    }
    这里需要提醒用户，如回复：未匹配到合同模板，当然不上传，就直接选择跳过，或直接起草。

    如果user_upload_contract_template_url 存在时和template_list为空时，直接
    存在时 选择跳过、直接起草就调用 contract_template_llm skill 子智能体，根据大模型本身能力进行合同编写

## contract_template_params


此子智能体主要是进行合同模板对应的合同模板参数赋值，主要是判断用户是否匹配到合同模板，如果有合同模板，获取到合同模板中的参数赋值。对应选中的合同模板数据中的param_schema_json，param_schema_json数据结构如下

redis 进行推送在output 中进行user_choose_contract_template_params返回，json 结构如下：

    
    {
        "session_id": "xxx",
        "exec_id": "xxx",
        "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "skill_name": "contract_template_match",
        "stage": "end",
        "render_type": "user_choose_contract_template_params",
        "input": { ... },
        "output": {
            "template_id":对应的模板 ID，对应 id
            "template_url":user_choose_contract_template_url对应的值,
            "param_schema_json": 对应的param_schema_json字段数据,
        },
        "timestamp": "...",
        "runtime_ms": 0
    }
    
    调用合同模板渲染 API 接口，http://10.17.55.121:8012/render 
    接口文档如下：
    ## 接口说明
    ### POST /render

    **请求体：**

    | 参数 | 类型 | 必填 | 说明 |
    |------|------|------|------|
    | template_url | string | 是 | docx 模板的 HTTP 下载地址 |
    | text | string | 是 | JSON 文本，解析后作为渲染参数 |

    **响应示例：**

    ```json
    {
    "success": true,
    "url": "http://10.156.196.158:9000/yuanti/docxtpl/xxx.docx",
    "message": "ok"
    }
    ```

    **调用示例：**

    ```bash
    curl -X POST http://10.17.55.121:8012/render \
    -H "Content-Type: application/json" \
    -d '{
        "template_url": "http://your-domain.com/templates/合同模板.docx",
        "text": "{\"contract_effect_year\":\"2024\",\"company_a\":\"北京华夏科技有限公司\",\"company_b\":\"软通智慧信息技术有限公司\"}"
    }'
    ```
   
同时redis 进行把接口返回的模板渲染发送至前端，推送在output 中进行user_choose_contract_template_render返回，json 结构如下：
    
        {
        "session_id": "xxx",
        "exec_id": "xxx",
        "run_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "skill_name": "contract_template_match",
        "stage": "end",
        "render_type": "user_choose_contract_template_render",
        "input": { ... },
        "output": {
            "template_id":对应的模板 ID，对应 id
            "template_url":user_choose_contract_template_url对应的值,
            "param_schema_json": 对应的param_schema_json字段数据,
            "template_url": 渲染接口返回的url地址,
        },
        "timestamp": "...",
        "runtime_ms": 0
    }


## contract_template_llm
  只有用户未上传合同模板、未匹配到合同模板时
  选择跳过、直接起草就调用 contract_template_llm skill 子智能体，根据大模型本身能力进行合同编写
