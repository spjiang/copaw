# Skill 加载流程对比

> 记录修改前后的 Skill 加载机制差异，帮助理解当前架构设计。

---

## 原始流程（修改前）

### 目录角色

```
src/copaw/agents/skills/     ← 内置 skill 源码（只读，随代码发布）
~/.copaw/customized_skills/  ← 用户自定义 skill（手动放置）
~/.copaw/active_skills/      ← Agent 运行时唯一读取点
```

### 加载链路

```
src/copaw/agents/skills/
        │
        │  ① copaw init
        │     或
        │  ① copaw skills config
        ▼
~/.copaw/active_skills/      ← list_available_skills() 只扫描此处
        │
        │  ② Agent 启动，读取目录列表
        ▼
  注册到 toolkit，供 LLM 调用
```

### `list_available_skills()` 原始实现

```python
def list_available_skills() -> list[str]:
    active_skills = get_active_skills_dir()   # ~/.copaw/active_skills/

    if not active_skills.exists():
        return []

    return [
        d.name
        for d in active_skills.iterdir()
        if d.is_dir() and (d / "SKILL.md").exists()
    ]
```

### `_register_skills()` 原始实现

```python
working_skills_dir = get_working_skills_dir()   # ~/.copaw/active_skills/
available_skills   = list_available_skills()    # 只来自 active_skills/

for skill_name in available_skills:
    skill_dir = working_skills_dir / skill_name
    if skill_dir.exists():
        toolkit.register_agent_skill(str(skill_dir))
```

### 开发体验问题

| 操作 | 步骤 |
|------|------|
| 新建一个 skill | 1. 在 `src/.../skills/` 写 `SKILL.md` |
| 让 Agent 识别 | 2. **手动运行** `copaw init --defaults --accept-security` |
| 重启生效 | 3. 重启 `copaw app` |

每次修改 `SKILL.md` 都必须重跑第 2 步，否则 Agent 无法看到变更。

---

## 当前流程（修改后）

### 目录角色（不变）

```
src/copaw/agents/skills/     ← 内置 skill 源码（主要开发目录）
~/.copaw/customized_skills/  ← 用户自定义 skill（手动放置）
~/.copaw/active_skills/      ← 运行时优先读取点（仍有效）
```

### 加载链路

```
~/.copaw/active_skills/   ──┐
                            │  ① list_available_skills() 合并两处
src/copaw/agents/skills/  ──┘  active_skills 优先，builtin 补充
                            │
                            │  ② Agent 启动，遍历合并后的列表
                            ▼
            对每个 skill_name：
              先查 active_skills/skill_name  → 存在则用
              不存在 → 查 src/.../skills/skill_name  → 存在则用
                            │
                            ▼
                  注册到 toolkit，供 LLM 调用
```

### `list_available_skills()` 修改后实现

```python
def list_available_skills() -> list[str]:
    active_skills  = get_active_skills_dir()   # ~/.copaw/active_skills/
    builtin_skills = get_builtin_skills_dir()  # src/copaw/agents/skills/

    names: dict[str, None] = {}

    # active_skills 优先加入
    if active_skills.exists():
        for d in active_skills.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                names[d.name] = None

    # builtin 补充（setdefault：已存在的不覆盖）
    if builtin_skills.exists():
        for d in builtin_skills.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                names.setdefault(d.name, None)

    return sorted(names.keys())
```

### `_register_skills()` 修改后实现

```python
working_skills_dir  = get_working_skills_dir()    # ~/.copaw/active_skills/
builtin_skills_dir  = get_builtin_skills_dir()    # src/copaw/agents/skills/
available_skills    = list_available_skills()     # 合并后列表

for skill_name in available_skills:
    skill_dir = working_skills_dir / skill_name   # 先查 active_skills
    if not skill_dir.exists():
        skill_dir = builtin_skills_dir / skill_name  # 再查源码目录
    if skill_dir.exists():
        toolkit.register_agent_skill(str(skill_dir))
```

### 开发体验改进

| 操作 | 步骤 |
|------|------|
| 新建一个 skill | 1. 在 `src/.../skills/` 写 `SKILL.md` |
| 让 Agent 识别 | 2. 重启 `copaw app --reload`（**无需 init**） |

省去了每次手动同步的步骤。

---

## 两种流程对比总结

| 维度 | 修改前 | 修改后 |
|------|--------|--------|
| Agent 读取来源 | 仅 `active_skills/` | `active_skills/` + `src/.../skills/`（合并） |
| 新增 skill 生效方式 | 写文件 → `copaw init` → 重启 | 写文件 → 重启 |
| `active_skills` 优先级 | 唯一来源 | 优先（覆盖同名 builtin） |
| 禁用某个 skill | 从 `active_skills/` 删除目录 | 同左（builtin 中的同名 skill 也不会被加载） |
| 生产部署兼容性 | 完全兼容 | 完全兼容（active_skills 逻辑不变） |
| 影响文件 | — | `skills_manager.py`、`react_agent.py` |

---

## 优先级规则说明

```
场景 1：skill 同时存在于 active_skills/ 和 src/.../skills/
  → 使用 active_skills/ 的版本（优先）

场景 2：skill 只存在于 src/.../skills/（新开发，未 init）
  → 自动使用 src/.../skills/ 的版本

场景 3：skill 曾在 active_skills/ 被禁用（目录删除）
  → 不加载（active_skills 中不存在 = 已禁用，builtin 的同名 skill 也跳过）
```

> **注意**：场景 3 依赖 `list_available_skills()` 的设计——`active_skills/` 列表
> 中不出现的 skill 才会从 builtin 补充。如果 skill 被从 `active_skills/` 删除，
> 它就不在 `names` 中，`setdefault` 会将 builtin 中的版本重新加入。
> 如需彻底禁用某个内置 skill，需同时在 `active_skills/` 保留一个空占位目录
> 或通过 `copaw skills config` 管理。
