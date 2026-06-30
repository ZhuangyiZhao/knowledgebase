# 0. 第 1 个月：大模型基础和模型网关 TD

更新时间：2026-05-06  
适用对象：AI 项目经验为 0 的资深后端工程师  
目标产物：一个可本地运行、可扩展到生产形态的 **LLM（Large Language Model，大语言模型）模型网关 MVP（Minimum Viable Product，最小可行产品）**

## 0.1 目录

- [1. 最简练版](#1-最简练版)
- [2. 详细解释版](#2-详细解释版)
  - [2.1 背景](#21-背景)
  - [2.2 目标](#22-目标)
  - [2.3 非目标](#23-非目标)
  - [2.4 成功标准](#24-成功标准)
  - [2.5 核心术语](#25-核心术语)
- [3. 总体设计](#3-总体设计)
  - [3.1 系统定位](#31-系统定位)
  - [3.2 总体架构](#32-总体架构)
  - [3.3 核心模块](#33-核心模块)
  - [3.4 请求主链路](#34-请求主链路)
  - [3.5 流式输出链路](#35-流式输出链路)
- [4. 详细设计](#4-详细设计)
  - [4.1 项目目录](#41-项目目录)
  - [4.2 配置设计](#42-配置设计)
  - [4.3 接口设计](#43-接口设计)
  - [4.4 数据模型设计](#44-数据模型设计)
  - [4.5 Provider 抽象设计](#45-provider-抽象设计)
  - [4.6 模型路由设计](#46-模型路由设计)
  - [4.7 超时重试设计](#47-超时重试设计)
  - [4.8 熔断降级设计](#48-熔断降级设计)
  - [4.9 限流设计](#49-限流设计)
  - [4.10 缓存设计](#410-缓存设计)
  - [4.11 成本统计设计](#411-成本统计设计)
  - [4.12 Prompt 模板设计](#412-prompt-模板设计)
  - [4.13 日志和链路追踪设计](#413-日志和链路追踪设计)
  - [4.14 安全设计](#414-安全设计)
- [5. 代码骨架](#5-代码骨架)
  - [5.1 依赖文件](#51-依赖文件)
  - [5.2 环境变量](#52-环境变量)
  - [5.3 FastAPI 入口](#53-fastapi-入口)
  - [5.4 配置加载](#54-配置加载)
  - [5.5 请求模型](#55-请求模型)
  - [5.6 Provider 接口](#56-provider-接口)
  - [5.7 OpenAI 兼容 Provider](#57-openai-兼容-provider)
  - [5.8 模型路由器](#58-模型路由器)
  - [5.9 模型网关服务](#59-模型网关服务)
  - [5.10 SSE 流式响应](#510-sse-流式响应)
  - [5.11 Redis 限流](#511-redis-限流)
  - [5.12 Redis 缓存](#512-redis-缓存)
  - [5.13 调用日志](#513-调用日志)
  - [5.14 错误码](#514-错误码)
  - [5.15 本地启动](#515-本地启动)
- [6. 四周实施计划](#6-四周实施计划)
  - [6.1 第 1 周：模型调用和基础概念](#61-第-1-周模型调用和基础概念)
  - [6.2 第 2 周：HTTP 服务和流式输出](#62-第-2-周http-服务和流式输出)
  - [6.3 第 3 周：模型网关核心能力](#63-第-3-周模型网关核心能力)
  - [6.4 第 4 周：生产化补强](#64-第-4-周生产化补强)
- [7. 测试和验收](#7-测试和验收)
  - [7.1 单元测试](#71-单元测试)
  - [7.2 接口测试](#72-接口测试)
  - [7.3 压测](#73-压测)
  - [7.4 故障演练](#74-故障演练)
- [8. 口述材料](#8-口述材料)
  - [8.1 3 分钟版本](#81-3-分钟版本)
  - [8.2 高频追问](#82-高频追问)
- [9. 图示](#9-图示)
- [10. 最终检查清单](#10-最终检查清单)
- [11. Reference](#11-reference)
- [12. Notes](#12-notes)

## 1. 最简练版

第 1 个月的目标不是“学完 AI”，而是先做出一个 **模型网关**：业务方统一请求网关，网关负责调用不同大模型，并提供流式输出、超时重试、模型路由、限流、缓存、降级、Prompt 版本和成本统计。这样做的本质是把大模型从“第三方 API”封装成公司内部可治理的基础服务。对后端来说，重点不在模型训练，而在 **稳定性、可观测性、成本控制、安全边界和扩展性**。完成后，你就有了后续 RAG（Retrieval-Augmented Generation，检索增强生成）和 Agent（智能体）的底座。

## 2. 详细解释版

### 2.1 背景

业务系统如果直接调用模型供应商，会很快遇到这些问题：

| 问题 | 具体表现 | 后果 |
|---|---|---|
| 调用分散 | 每个业务自己接 DeepSeek / Qwen / Doubao / OpenAI | 重复开发，无法统一治理 |
| 稳定性不可控 | 超时、限流、模型异常没有统一处理 | 用户体验不稳定 |
| 成本不可见 | 不知道谁用了多少 Token | 预算失控 |
| 质量不可评估 | Prompt 改了没有版本记录 | 效果变差无法回滚 |
| 安全不可控 | 用户输入、系统 Prompt、API Key 混在一起 | 有泄露和越权风险 |
| 观测缺失 | 看不到 p95、错误率、模型分布 | 线上问题难定位 |

模型网关要解决的核心问题是：

> **把不可控的模型调用，变成可治理、可观测、可降级、可计费的后端基础能力。**

### 2.2 目标

本 TD 要实现一个可运行 MVP，包含以下能力：

| 能力 | 第 1 个月目标 |
|---|---|
| 普通问答 | 支持 `/v1/chat/completions` 非流式返回 |
| 流式输出 | 支持 SSE（Server-Sent Events，服务端事件流）逐段返回 |
| 多模型接入 | 先接入 1 个 OpenAI 兼容接口，预留多个 Provider |
| 模型路由 | 支持按 `model`、任务类型、默认策略选择模型 |
| 超时重试 | 模型调用失败后有限重试 |
| 熔断降级 | 主模型失败时切换备用模型或返回降级响应 |
| 限流 | 按用户做每分钟请求数限制 |
| 缓存 | 对非流式、确定性问题做结果缓存 |
| 成本统计 | 记录输入 Token、输出 Token、耗时、估算成本 |
| Prompt 版本 | 每次请求记录 Prompt 模板版本 |
| 可观测性 | 结构化日志 + 基础指标字段 |
| 安全 | API Key 从环境变量读取，日志脱敏 |

### 2.3 非目标

第 1 个月不要做这些：

| 非目标 | 原因 |
|---|---|
| 不做 RAG 完整链路 | RAG 是第 2 个月重点，第 1 个月只预留接口 |
| 不做复杂 Agent 编排 | Agent 是第 3 个月重点，第 1 个月只做工具底座 |
| 不做模型微调 | 先把调用、治理、观测跑通 |
| 不做复杂前端 | 用 curl / Postman / 简单 HTML 验证即可 |
| 不做 Kubernetes 部署 | Docker Compose 足够本地验证 |
| 不做复杂权限系统 | 先用 API Token 和 user_id 模拟 |

### 2.4 成功标准

第 1 个月结束时，必须做到：

- [ ] 本地启动 FastAPI 服务。
- [ ] `/health` 返回正常。
- [ ] `/v1/chat/completions` 支持普通返回。
- [ ] `/v1/chat/completions` 支持 `stream=true` 流式输出。
- [ ] 支持至少一个真实模型供应商。
- [ ] 模型超时后能返回统一错误。
- [ ] 主模型失败后能切换备用模型。
- [ ] 同一个用户一分钟内超过阈值会被限流。
- [ ] 相同问题可以命中 Redis 缓存。
- [ ] 每次请求有 request_id。
- [ ] 每次请求记录模型、耗时、Token、成本和状态。
- [ ] README 能说明如何启动、如何调用、如何扩展 Provider。

### 2.5 核心术语

| 术语 | 全称和中文含义 | 在本系统里的作用 |
|---|---|---|
| LLM | Large Language Model，大语言模型 | 被网关调用的模型服务 |
| Token | 模型处理文本的基本单位 | 影响上下文长度、延迟和成本 |
| Prompt | 提示词 | 控制模型回答风格、任务和格式 |
| SSE | Server-Sent Events，服务端事件流 | 实现逐字或逐段返回 |
| Provider | 模型供应商适配器 | 屏蔽不同模型 API 差异 |
| Router | 路由器 | 决定本次请求用哪个模型 |
| Circuit Breaker | 熔断器 | 模型错误率高时临时摘除 |
| Rate Limit | 限流 | 防止单用户打爆模型或成本 |
| Cache | 缓存 | 降低重复问题的延迟和成本 |
| Fallback | 降级 | 主链路失败时走备用模型或简化回答 |
| Observability | 可观测性 | 日志、指标、Trace 和告警 |

## 3. 总体设计

### 3.1 系统定位

模型网关位于业务系统和模型供应商之间。

![OpenAPI 标识图](https://upload.wikimedia.org/wikipedia/commons/6/61/OpenAPI_Logo_Pantone.svg)

图意说明：模型网关对外最好提供稳定、清晰、可文档化的 HTTP API，OpenAPI 可以用于描述接口契约。图片来源：Wikimedia Commons。

```text
业务系统 / 用户
      |
      v
模型网关
      |
      +--> DeepSeek
      +--> Qwen
      +--> Doubao
      +--> OpenAI
      |
      v
日志 / 指标 / 成本 / 审计
```

### 3.2 总体架构

```text
Client
  |
  v
FastAPI API Layer
  |
  +--> Auth Middleware
  |
  +--> Request ID Middleware
  |
  +--> Rate Limiter
  |
  +--> Cache Manager
  |
  +--> Prompt Manager
  |
  +--> Model Router
  |
  +--> Model Gateway Service
          |
          +--> Provider: DeepSeek
          +--> Provider: Qwen
          +--> Provider: Doubao
          +--> Provider: OpenAI Compatible
  |
  v
Call Log + Metrics + Cost
```

### 3.3 核心模块

| 模块 | 职责 | 第 1 个月实现程度 |
|---|---|---|
| API Layer | 暴露 HTTP 接口 | 完整实现 |
| Auth Middleware | 校验请求方身份 | 简化实现 |
| Request ID | 串联一次请求日志 | 完整实现 |
| Rate Limiter | 按用户限流 | Redis 实现 |
| Cache Manager | 缓存确定性回答 | Redis 实现 |
| Prompt Manager | 管理 Prompt 模板和版本 | 内存配置起步 |
| Model Router | 选择模型 | 规则路由起步 |
| Provider | 适配模型供应商 | OpenAI 兼容接口起步 |
| Gateway Service | 编排调用、重试、降级 | 完整实现 MVP |
| Call Logger | 记录调用明细 | 先写日志，后续入库 |
| Metrics | 暴露指标 | 先预留字段，后续接 Prometheus |

### 3.4 请求主链路

![OpenTelemetry 架构图](https://opentelemetry.io/img/otel-diagram.svg)

图意说明：后续接入 OpenTelemetry 后，一次模型请求可以串起 API、缓存、模型调用和日志，定位慢请求会更容易。图片来源：OpenTelemetry 官方文档。

```text
Client
  |
  v
POST /v1/chat/completions
  |
  v
生成 request_id
  |
  v
鉴权
  |
  v
限流
  |
  v
读取 Prompt 模板
  |
  v
判断缓存
  |
  +-- 命中 --> 返回缓存结果
  |
  +-- 未命中
        |
        v
     模型路由
        |
        v
     调用 Provider
        |
        +-- 成功 --> 记录日志 -> 写缓存 -> 返回
        |
        +-- 失败 --> 重试 -> 降级 -> 记录日志 -> 返回
```

### 3.5 流式输出链路

普通 HTTP 返回需要等模型完整生成后才返回，体验较慢。流式输出会把模型生成的片段一段一段推给客户端。

```text
Client                    Gateway                    Model
  |                         |                          |
  | ---- stream=true -----> |                          |
  |                         | ---- stream request ---> |
  |                         | <------ chunk 1 -------- |
  | <------ SSE 1 -------- |                          |
  |                         | <------ chunk 2 -------- |
  | <------ SSE 2 -------- |                          |
  |                         | <------ chunk 3 -------- |
  | <------ SSE 3 -------- |                          |
  | <------ [DONE] ------- |                          |
```

SSE 数据格式：

```text
event: message
data: {"request_id":"xxx","delta":"你好"}

event: done
data: {"request_id":"xxx","finish_reason":"stop"}
```

## 4. 详细设计

### 4.1 项目目录

建议目录如下：

```text
llm-gateway/
  |
  +-- app/
  |   +-- main.py
  |   +-- config.py
  |   +-- schemas.py
  |   +-- errors.py
  |   +-- middlewares.py
  |   +-- gateway/
  |   |   +-- service.py
  |   |   +-- router.py
  |   |   +-- provider.py
  |   |   +-- prompt.py
  |   |   +-- cost.py
  |   +-- infra/
  |   |   +-- redis_client.py
  |   |   +-- rate_limiter.py
  |   |   +-- cache.py
  |   |   +-- logger.py
  |   +-- providers/
  |       +-- openai_compatible.py
  |
  +-- tests/
  |   +-- test_gateway.py
  |
  +-- docker-compose.yml
  +-- requirements.txt
  +-- .env.example
  +-- README.md
```

### 4.2 配置设计

配置分三类：

| 类型 | 示例 | 存放位置 |
|---|---|---|
| 敏感配置 | API Key、数据库密码 | 环境变量 |
| 路由配置 | 默认模型、备用模型 | 配置文件或环境变量 |
| 运行参数 | 超时、重试、限流阈值 | 环境变量 |

核心配置：

| 配置项 | 示例 | 说明 |
|---|---|---|
| `MODEL_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容接口地址 |
| `MODEL_API_KEY` | `sk-xxx` | 模型 API Key |
| `DEFAULT_MODEL` | `deepseek-chat` | 默认模型 |
| `FALLBACK_MODEL` | `qwen-plus` | 备用模型 |
| `MODEL_TIMEOUT_SECONDS` | `30` | 模型调用超时 |
| `MODEL_MAX_RETRIES` | `2` | 最大重试次数 |
| `RATE_LIMIT_PER_MINUTE` | `30` | 用户每分钟限制 |
| `CACHE_TTL_SECONDS` | `3600` | 缓存过期时间 |

### 4.3 接口设计

![FastAPI 标识图](https://upload.wikimedia.org/wikipedia/commons/1/1a/FastAPI_logo.svg)

图意说明：第 1 个月建议用 FastAPI 快速完成 HTTP 接口、参数校验和 SSE 流式输出，重点把模型网关主链路跑通。图片来源：Wikimedia Commons。

#### 4.3.1 健康检查接口

```http
GET /health
```

响应：

```json
{
  "status": "ok",
  "service": "llm-gateway"
}
```

#### 4.3.2 普通问答接口

```http
POST /v1/chat/completions
Content-Type: application/json
Authorization: Bearer dev-token
```

请求：

```json
{
  "user_id": "u_10001",
  "model": "deepseek-chat",
  "messages": [
    {
      "role": "user",
      "content": "解释 Redis 缓存击穿"
    }
  ],
  "temperature": 0.3,
  "stream": false,
  "prompt_version": "backend_qa_v1"
}
```

响应：

```json
{
  "request_id": "req_20260506_abc",
  "model": "deepseek-chat",
  "content": "Redis 缓存击穿是指热点 key 过期瞬间...",
  "usage": {
    "input_tokens": 30,
    "output_tokens": 180,
    "total_tokens": 210
  },
  "cost": {
    "estimated_cny": 0.0021
  },
  "latency_ms": 1320,
  "cache_hit": false
}
```

#### 4.3.3 流式问答接口

请求中设置：

```json
{
  "user_id": "u_10001",
  "messages": [
    {
      "role": "user",
      "content": "用 5 句话解释 MySQL MVCC"
    }
  ],
  "stream": true
}
```

响应头：

```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

响应片段：

```text
event: message
data: {"request_id":"req_xxx","delta":"MVCC"}

event: message
data: {"request_id":"req_xxx","delta":" 是 MySQL"}

event: done
data: {"request_id":"req_xxx","finish_reason":"stop"}
```

### 4.4 数据模型设计

第 1 个月可以先写结构化日志，不一定立刻建库。但 TD 里要把未来表结构设计出来。

#### 4.4.1 调用日志表

```sql
CREATE TABLE llm_call_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  request_id VARCHAR(64) NOT NULL,
  user_id VARCHAR(64) NOT NULL,
  model VARCHAR(128) NOT NULL,
  provider VARCHAR(64) NOT NULL,
  prompt_version VARCHAR(64) DEFAULT NULL,
  stream TINYINT NOT NULL DEFAULT 0,
  input_tokens INT NOT NULL DEFAULT 0,
  output_tokens INT NOT NULL DEFAULT 0,
  total_tokens INT NOT NULL DEFAULT 0,
  estimated_cost_cny DECIMAL(12, 6) NOT NULL DEFAULT 0,
  latency_ms INT NOT NULL DEFAULT 0,
  cache_hit TINYINT NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL,
  error_code VARCHAR(64) DEFAULT NULL,
  error_message VARCHAR(512) DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_user_created (user_id, created_at),
  KEY idx_request_id (request_id),
  KEY idx_model_created (model, created_at)
);
```

#### 4.4.2 Prompt 模板表

```sql
CREATE TABLE prompt_template (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(128) NOT NULL,
  version VARCHAR(64) NOT NULL,
  content TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_by VARCHAR(64) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_name_version (name, version)
);
```

#### 4.4.3 模型配置表

```sql
CREATE TABLE model_config (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  model VARCHAR(128) NOT NULL,
  provider VARCHAR(64) NOT NULL,
  base_url VARCHAR(512) NOT NULL,
  context_window INT NOT NULL,
  input_price_per_1k DECIMAL(12, 6) NOT NULL DEFAULT 0,
  output_price_per_1k DECIMAL(12, 6) NOT NULL DEFAULT 0,
  timeout_seconds INT NOT NULL DEFAULT 30,
  enabled TINYINT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_model (model)
);
```

### 4.5 Provider 抽象设计

Provider 的目标是屏蔽不同模型供应商的 API 差异。

```text
Gateway Service
      |
      v
ModelProvider Interface
      |
      +--> DeepSeekProvider
      +--> QwenProvider
      +--> DoubaoProvider
      +--> OpenAICompatibleProvider
```

Provider 必须提供两个能力：

| 方法 | 说明 |
|---|---|
| `chat()` | 非流式调用，返回完整文本 |
| `stream_chat()` | 流式调用，返回异步片段 |

### 4.6 模型路由设计

第 1 个月先做规则路由，不上复杂策略。

路由优先级：

1. 请求中显式指定 `model`，并且该模型可用。
2. 根据 `task_type` 选择模型，例如 `coding`、`summary`、`qa`。
3. 使用默认模型。
4. 默认模型不可用时使用备用模型。

路由示例：

| 场景 | 模型 |
|---|---|
| 普通问答 | `deepseek-chat` |
| 代码解释 | `qwen-coder` |
| 长文本总结 | `qwen-long` |
| 主模型异常 | `fallback-model` |

### 4.7 超时重试设计

超时重试要克制，不能无限重试。

| 策略 | 说明 |
|---|---|
| 单次超时 | 默认 30 秒 |
| 最大重试 | 默认 2 次 |
| 退避策略 | 第 1 次失败等 200ms，第 2 次失败等 500ms |
| 不重试场景 | 参数错误、鉴权失败、余额不足 |
| 可重试场景 | 网络抖动、超时、5xx |

### 4.8 熔断降级设计

熔断目标是保护系统，不让请求持续打到异常模型。

```text
模型调用失败
  |
  v
统计最近 1 分钟错误率
  |
  +-- 错误率 < 阈值 --> 继续使用
  |
  +-- 错误率 >= 阈值
          |
          v
       熔断 60 秒
          |
          v
       路由到备用模型
```

第 1 个月可以先做简化版：

- 如果连续失败 3 次，则 60 秒内不再选这个模型。
- 熔断状态放 Redis。
- 熔断期间直接走备用模型。

### 4.9 限流设计

按 user_id 限流：

![Redis 标识图](https://upload.wikimedia.org/wikipedia/commons/e/ee/Redis_logo.svg)

图意说明：Redis 适合承载限流计数和短期缓存，模型网关第 1 个月用 Redis 能快速实现“调用前治理”。图片来源：Wikimedia Commons。

| 维度 | 示例 |
|---|---|
| 限流 key | `rate:u_10001:202605061530` |
| 窗口 | 1 分钟 |
| 阈值 | 30 次 |
| 存储 | Redis |
| 超限响应 | HTTP 429 |

注意：

- 限流要在模型调用前执行。
- 限流失败不能调用模型。
- 管理员或内部压测账号可以配置更高阈值。

### 4.10 缓存设计

缓存只用于 **非流式、低随机性、可复用问题**。

缓存 key：

```text
cache:{model}:{prompt_version}:{sha256(normalized_messages)}
```

缓存条件：

| 条件 | 是否缓存 |
|---|---|
| `stream=false` | 可以缓存 |
| `temperature <= 0.3` | 可以缓存 |
| 用户问题不含敏感信息 | 可以缓存 |
| 包含当前时间、个人信息、实时数据 | 不缓存 |

### 4.11 成本统计设计

成本公式：

```text
estimated_cost = input_tokens / 1000 * input_price_per_1k
               + output_tokens / 1000 * output_price_per_1k
```

第 1 个月如果供应商没有返回准确 Token，可以先做估算：

```text
中文：约 1 个字 ~= 1 到 2 个 Token
英文：约 4 个字符 ~= 1 个 Token
```

记录维度：

| 维度 | 用途 |
|---|---|
| 用户 | 看谁消耗最多 |
| 模型 | 看哪个模型成本最高 |
| Prompt 版本 | 看哪个模板更费 Token |
| 接口 | 看业务线成本 |
| 日期 | 做每日预算 |

### 4.12 Prompt 模板设计

Prompt 不要写死在业务代码里。

模板示例：

```text
你是一个后端技术助手。
请用清晰、有层次的方式回答。
如果不确定，请明确说明不确定，不要编造。

用户问题：
{{user_question}}
```

版本字段：

| 字段 | 示例 |
|---|---|
| name | `backend_qa` |
| version | `v1` |
| status | `active` |
| content | 模板正文 |

### 4.13 日志和链路追踪设计

![Prometheus 架构图](https://prometheus.io/assets/docs/architecture.svg)

图意说明：第 1 个月可以先写结构化日志，第 4 周开始预留 Prometheus 指标字段，后续再接 Grafana 看板。图片来源：Prometheus 官方文档。

每条日志必须包含：

| 字段 | 说明 |
|---|---|
| `request_id` | 请求唯一 ID |
| `user_id` | 用户 |
| `model` | 模型 |
| `provider` | 供应商 |
| `latency_ms` | 耗时 |
| `input_tokens` | 输入 Token |
| `output_tokens` | 输出 Token |
| `cache_hit` | 是否命中缓存 |
| `status` | 成功或失败 |
| `error_code` | 错误码 |

日志示例：

```json
{
  "request_id": "req_20260506_abc",
  "user_id": "u_10001",
  "model": "deepseek-chat",
  "provider": "deepseek",
  "latency_ms": 1320,
  "input_tokens": 30,
  "output_tokens": 180,
  "cache_hit": false,
  "status": "success"
}
```

### 4.14 安全设计

安全底线：

| 风险 | 处理方式 |
|---|---|
| API Key 泄露 | 只放环境变量，不写代码，不进日志 |
| 日志泄露隐私 | 手机号、邮箱、Key 做脱敏 |
| 恶意刷接口 | API Token + user_id 限流 |
| Prompt 注入 | 第 1 个月先记录风险，第 2 到 3 个月加强 |
| 成本打爆 | 每用户限流 + 每日成本预算 |
| 供应商异常 | 超时、重试、熔断、备用模型 |

## 5. 代码骨架

### 5.1 依赖文件

`requirements.txt`：

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pydantic-settings==2.7.1
python-dotenv==1.0.1
httpx==0.28.1
redis==5.2.1
orjson==3.10.12
```

### 5.2 环境变量

`.env.example`：

```bash
APP_NAME=llm-gateway
ENV=dev

API_TOKEN=dev-token

MODEL_BASE_URL=https://api.deepseek.com
MODEL_API_KEY=replace-me
DEFAULT_MODEL=deepseek-chat
FALLBACK_MODEL=deepseek-chat
MODEL_TIMEOUT_SECONDS=30
MODEL_MAX_RETRIES=2

REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_PER_MINUTE=30
CACHE_TTL_SECONDS=3600
```

### 5.3 FastAPI 入口

`app/main.py`：

```python
import time
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import ORJSONResponse, StreamingResponse

from app.config import settings
from app.gateway.service import ModelGatewayService
from app.infra.cache import RedisCache
from app.infra.rate_limiter import RedisRateLimiter
from app.schemas import ChatRequest

app = FastAPI(default_response_class=ORJSONResponse)


def get_request_id() -> str:
    return f"req_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


async def verify_token(authorization: str = Header(default="")) -> None:
    expected = f"Bearer {settings.api_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name}


@app.post("/v1/chat/completions", dependencies=[Depends(verify_token)])
async def chat(req: ChatRequest, request: Request):
    request_id = get_request_id()
    rate_limiter = RedisRateLimiter()
    cache = RedisCache()
    gateway = ModelGatewayService(cache=cache)

    allowed = await rate_limiter.allow(
        user_id=req.user_id,
        limit=settings.rate_limit_per_minute,
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    if req.stream:
        async def event_stream():
            async for item in gateway.stream_chat(req=req, request_id=request_id):
                yield item

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": request_id,
            },
        )

    resp = await gateway.chat(req=req, request_id=request_id)
    return resp
```

### 5.4 配置加载

`app/config.py`：

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "llm-gateway"
    env: str = "dev"
    api_token: str = "dev-token"

    model_base_url: str
    model_api_key: str
    default_model: str = "deepseek-chat"
    fallback_model: str = "deepseek-chat"
    model_timeout_seconds: int = 30
    model_max_retries: int = 2

    redis_url: str = "redis://localhost:6379/0"
    rate_limit_per_minute: int = 30
    cache_ttl_seconds: int = 3600


settings = Settings()
```

### 5.5 请求模型

`app/schemas.py`：

```python
from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["system", "user", "assistant"]


class Message(BaseModel):
    role: Role
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    messages: list[Message] = Field(min_length=1, max_length=50)
    model: str | None = None
    task_type: str | None = None
    prompt_version: str = "backend_qa_v1"
    temperature: float = Field(default=0.3, ge=0, le=2)
    stream: bool = False


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class Cost(BaseModel):
    estimated_cny: float = 0


class ChatResponse(BaseModel):
    request_id: str
    model: str
    content: str
    usage: Usage
    cost: Cost
    latency_ms: int
    cache_hit: bool = False
```

### 5.6 Provider 接口

`app/gateway/provider.py`：

```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.schemas import ChatRequest


class ProviderResult:
    def __init__(
        self,
        content: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        raw_model: str | None = None,
    ):
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.raw_model = raw_model


class ModelProvider(ABC):
    name: str

    @abstractmethod
    async def chat(self, req: ChatRequest, model: str) -> ProviderResult:
        raise NotImplementedError

    @abstractmethod
    async def stream_chat(self, req: ChatRequest, model: str) -> AsyncIterator[str]:
        raise NotImplementedError
```

### 5.7 OpenAI 兼容 Provider

`app/providers/openai_compatible.py`：

```python
from collections.abc import AsyncIterator

import httpx

from app.config import settings
from app.gateway.provider import ModelProvider, ProviderResult
from app.schemas import ChatRequest


class OpenAICompatibleProvider(ModelProvider):
    name = "openai_compatible"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.model_api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, req: ChatRequest, model: str, stream: bool) -> dict:
        return {
            "model": model,
            "messages": [m.model_dump() for m in req.messages],
            "temperature": req.temperature,
            "stream": stream,
        }

    async def chat(self, req: ChatRequest, model: str) -> ProviderResult:
        url = f"{settings.model_base_url.rstrip('/')}/v1/chat/completions"
        timeout = httpx.Timeout(settings.model_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json=self._payload(req, model=model, stream=False),
            )
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return ProviderResult(
            content=content,
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            raw_model=data.get("model"),
        )

    async def stream_chat(self, req: ChatRequest, model: str) -> AsyncIterator[str]:
        url = f"{settings.model_base_url.rstrip('/')}/v1/chat/completions"
        timeout = httpx.Timeout(settings.model_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                url,
                headers=self._headers(),
                json=self._payload(req, model=model, stream=True),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line.removeprefix("data: ").strip()
                    if chunk == "[DONE]":
                        break
                    yield chunk
```

### 5.8 模型路由器

`app/gateway/router.py`：

```python
from app.config import settings
from app.schemas import ChatRequest


class ModelRouter:
    def select_model(self, req: ChatRequest) -> str:
        if req.model:
            return req.model

        if req.task_type == "coding":
            return "qwen-coder"

        if req.task_type == "summary":
            return settings.default_model

        return settings.default_model

    def fallback_model(self) -> str:
        return settings.fallback_model
```

### 5.9 模型网关服务

`app/gateway/service.py`：

```python
import asyncio
import json
import time
from collections.abc import AsyncIterator

from app.config import settings
from app.gateway.router import ModelRouter
from app.infra.cache import RedisCache
from app.infra.logger import log_call
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas import ChatRequest, ChatResponse, Cost, Usage


class ModelGatewayService:
    def __init__(self, cache: RedisCache):
        self.cache = cache
        self.router = ModelRouter()
        self.provider = OpenAICompatibleProvider()

    async def chat(self, req: ChatRequest, request_id: str) -> ChatResponse:
        start = time.perf_counter()
        model = self.router.select_model(req)
        cache_key = self.cache.build_key(req=req, model=model)

        if self.cache.cacheable(req):
            cached = await self.cache.get(cache_key)
            if cached:
                payload = json.loads(cached)
                payload["request_id"] = request_id
                payload["cache_hit"] = True
                return ChatResponse(**payload)

        last_error: Exception | None = None
        result = None

        for attempt in range(settings.model_max_retries + 1):
            try:
                result = await self.provider.chat(req=req, model=model)
                break
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(0.2 * (attempt + 1))

        if result is None:
            fallback = self.router.fallback_model()
            try:
                result = await self.provider.chat(req=req, model=fallback)
                model = fallback
            except Exception as exc:
                await log_call(
                    request_id=request_id,
                    user_id=req.user_id,
                    model=model,
                    status="failed",
                    error_code="MODEL_CALL_FAILED",
                    error_message=str(last_error or exc),
                )
                raise

        latency_ms = int((time.perf_counter() - start) * 1000)
        usage = Usage(
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.input_tokens + result.output_tokens,
        )
        cost = Cost(estimated_cny=self._estimate_cost(usage))
        resp = ChatResponse(
            request_id=request_id,
            model=model,
            content=result.content,
            usage=usage,
            cost=cost,
            latency_ms=latency_ms,
            cache_hit=False,
        )

        if self.cache.cacheable(req):
            await self.cache.set(cache_key, resp.model_dump_json())

        await log_call(
            request_id=request_id,
            user_id=req.user_id,
            model=model,
            status="success",
            latency_ms=latency_ms,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost_cny=cost.estimated_cny,
        )
        return resp

    async def stream_chat(self, req: ChatRequest, request_id: str) -> AsyncIterator[str]:
        model = self.router.select_model(req)
        yield self._sse("meta", {"request_id": request_id, "model": model})

        try:
            async for chunk in self.provider.stream_chat(req=req, model=model):
                yield self._sse("message", {"request_id": request_id, "delta": chunk})
            yield self._sse("done", {"request_id": request_id, "finish_reason": "stop"})
        except Exception as exc:
            yield self._sse(
                "error",
                {
                    "request_id": request_id,
                    "error_code": "STREAM_MODEL_FAILED",
                    "message": str(exc),
                },
            )

    def _estimate_cost(self, usage: Usage) -> float:
        input_price = 0.001
        output_price = 0.002
        return round(
            usage.input_tokens / 1000 * input_price
            + usage.output_tokens / 1000 * output_price,
            6,
        )

    def _sse(self, event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

### 5.10 SSE 流式响应

流式接口的关键点：

| 点 | 说明 |
|---|---|
| `StreamingResponse` | FastAPI 返回异步生成器 |
| `text/event-stream` | SSE 标准响应类型 |
| `event` | 事件类型，例如 `message`、`done`、`error` |
| `data` | 事件内容，建议 JSON |
| 错误处理 | 流中途失败也要返回 `error` 事件 |

最小客户端测试：

```bash
curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-token" \
  -d '{
    "user_id": "u_10001",
    "stream": true,
    "messages": [
      {
        "role": "user",
        "content": "用三句话解释 TCP 三次握手"
      }
    ]
  }'
```

### 5.11 Redis 限流

`app/infra/rate_limiter.py`：

```python
import time

from app.infra.redis_client import get_redis


class RedisRateLimiter:
    async def allow(self, user_id: str, limit: int) -> bool:
        redis = await get_redis()
        minute = int(time.time() // 60)
        key = f"rate:{user_id}:{minute}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 70)
        return count <= limit
```

`app/infra/redis_client.py`：

```python
from redis.asyncio import Redis

from app.config import settings

_redis: Redis | None = None


async def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis
```

### 5.12 Redis 缓存

`app/infra/cache.py`：

```python
import hashlib
import json

from app.config import settings
from app.infra.redis_client import get_redis
from app.schemas import ChatRequest


class RedisCache:
    def cacheable(self, req: ChatRequest) -> bool:
        if req.stream:
            return False
        if req.temperature > 0.3:
            return False
        text = " ".join(m.content for m in req.messages)
        risky_words = ["今天", "现在", "实时", "手机号", "身份证", "token", "password"]
        return not any(word.lower() in text.lower() for word in risky_words)

    def build_key(self, req: ChatRequest, model: str) -> str:
        normalized = {
            "model": model,
            "prompt_version": req.prompt_version,
            "messages": [m.model_dump() for m in req.messages],
            "temperature": req.temperature,
        }
        raw = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"llm_cache:{digest}"

    async def get(self, key: str) -> str | None:
        redis = await get_redis()
        return await redis.get(key)

    async def set(self, key: str, value: str) -> None:
        redis = await get_redis()
        await redis.set(key, value, ex=settings.cache_ttl_seconds)
```

### 5.13 调用日志

`app/infra/logger.py`：

```python
import json
import logging

logger = logging.getLogger("llm_gateway")
logging.basicConfig(level=logging.INFO)


def mask_secret(text: str | None) -> str | None:
    if not text:
        return text
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}***{text[-4:]}"


async def log_call(**kwargs) -> None:
    safe = dict(kwargs)
    if "error_message" in safe:
        safe["error_message"] = mask_secret(str(safe["error_message"]))
    logger.info(json.dumps(safe, ensure_ascii=False))
```

### 5.14 错误码

`app/errors.py`：

```python
from enum import StrEnum


class ErrorCode(StrEnum):
    UNAUTHORIZED = "UNAUTHORIZED"
    RATE_LIMITED = "RATE_LIMITED"
    MODEL_TIMEOUT = "MODEL_TIMEOUT"
    MODEL_CALL_FAILED = "MODEL_CALL_FAILED"
    STREAM_MODEL_FAILED = "STREAM_MODEL_FAILED"
    INVALID_REQUEST = "INVALID_REQUEST"
```

统一错误响应建议：

```json
{
  "request_id": "req_xxx",
  "error": {
    "code": "MODEL_TIMEOUT",
    "message": "model request timeout"
  }
}
```

### 5.15 本地启动

`docker-compose.yml`：

```yaml
services:
  redis:
    image: redis:7
    ports:
      - "6379:6379"
```

启动 Redis：

```bash
docker compose up -d
```

启动服务：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

普通请求：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-token" \
  -d '{
    "user_id": "u_10001",
    "messages": [
      {
        "role": "user",
        "content": "解释 Redis 缓存击穿"
      }
    ],
    "stream": false
  }'
```

## 6. 四周实施计划

### 6.1 第 1 周：模型调用和基础概念

| Day | 任务 | 代码产出 | 验收 |
|---|---|---|---|
| Day 1 | 准备 API Key 和 `.env` | `.env.example` | 能读取环境变量 |
| Day 2 | 写最小模型调用脚本 | `scripts/chat_once.py` | 输入问题，输出回答 |
| Day 3 | 学 Prompt 和 Token | `docs/prompt_notes.md` | 写出 5 个 Prompt |
| Day 4 | 封装 Provider | `provider.py` | 能调用 `chat()` |
| Day 5 | 加超时 | `openai_compatible.py` | 超时后抛出明确异常 |
| Day 6 | 加重试 | `service.py` | 网络失败可重试 |
| Day 7 | 周复盘 | `README.md` | 写明本周链路 |

### 6.2 第 2 周：HTTP 服务和流式输出

| Day | 任务 | 代码产出 | 验收 |
|---|---|---|---|
| Day 1 | FastAPI 项目初始化 | `main.py` | `/health` 正常 |
| Day 2 | 普通问答接口 | `schemas.py` | curl 可调用 |
| Day 3 | SSE 流式接口 | `StreamingResponse` | `curl -N` 能看到分段 |
| Day 4 | request_id | `get_request_id()` | 日志可串联 |
| Day 5 | 统一错误码 | `errors.py` | 错误返回结构一致 |
| Day 6 | 接 Redis | `redis_client.py` | 能 ping Redis |
| Day 7 | 接口文档 | `README.md` | 写明请求和响应 |

### 6.3 第 3 周：模型网关核心能力

| Day | 任务 | 代码产出 | 验收 |
|---|---|---|---|
| Day 1 | Provider 抽象 | `provider.py` | 可替换供应商 |
| Day 2 | 模型路由 | `router.py` | 按 model / task_type 选择 |
| Day 3 | 备用模型 | `fallback_model()` | 主模型失败可切换 |
| Day 4 | 限流 | `rate_limiter.py` | 超限返回 429 |
| Day 5 | 缓存 | `cache.py` | 相同问题命中缓存 |
| Day 6 | 成本估算 | `cost.py` 或服务内函数 | 返回 cost 字段 |
| Day 7 | 架构图 | `docs/architecture.md` | 能讲清楚链路 |

### 6.4 第 4 周：生产化补强

| Day | 任务 | 代码产出 | 验收 |
|---|---|---|---|
| Day 1 | Prompt 模板 | `prompt.py` | Prompt 不硬编码 |
| Day 2 | Prompt 版本 | `prompt_version` | 日志记录版本 |
| Day 3 | 鉴权 | `verify_token()` | 无 Token 拒绝 |
| Day 4 | 日志脱敏 | `logger.py` | Key 不进日志 |
| Day 5 | 指标字段 | 日志扩展 | QPS、耗时、错误可统计 |
| Day 6 | 压测 | `wrk` / `hey` | 记录 p95 |
| Day 7 | 月度总结 | `docs/month1_summary.md` | 写出结果和待改进 |

## 7. 测试和验收

### 7.1 单元测试

建议测试点：

| 测试项 | 断言 |
|---|---|
| 路由 | 未指定模型时使用默认模型 |
| 限流 | 超过阈值返回 false |
| 缓存 key | 相同请求生成相同 key |
| 缓存策略 | `stream=true` 不缓存 |
| 成本估算 | 输入输出 Token 能计算成本 |

示例：

```python
from app.gateway.router import ModelRouter
from app.schemas import ChatRequest, Message


def test_default_model_route():
    req = ChatRequest(
        user_id="u1",
        messages=[Message(role="user", content="hello")],
    )
    model = ModelRouter().select_model(req)
    assert model
```

### 7.2 接口测试

健康检查：

```bash
curl -i http://127.0.0.1:8000/health
```

未授权测试：

```bash
curl -i http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","messages":[{"role":"user","content":"hi"}]}'
```

期望：

```text
HTTP/1.1 401 Unauthorized
```

限流测试：

```bash
for i in {1..40}; do
  curl -s http://127.0.0.1:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer dev-token" \
    -d '{"user_id":"u_rate","messages":[{"role":"user","content":"hi"}]}' > /dev/null
done
```

期望：

```text
超过阈值后返回 429
```

### 7.3 压测

可以使用 `hey`：

```bash
hey -n 100 -c 10 \
  -m POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-token" \
  -d '{"user_id":"u_load","messages":[{"role":"user","content":"解释 TCP TIME_WAIT"}]}' \
  http://127.0.0.1:8000/v1/chat/completions
```

记录指标：

| 指标 | 说明 |
|---|---|
| QPS | 每秒请求数 |
| p50 | 中位延迟 |
| p95 | 95 分位延迟 |
| 错误率 | 非 2xx 占比 |
| 缓存命中率 | 命中缓存请求占比 |

### 7.4 故障演练

必须演练 5 个场景：

| 场景 | 操作 | 预期 |
|---|---|---|
| API Key 错误 | 写错 `MODEL_API_KEY` | 返回统一错误，不泄露 Key |
| 模型超时 | 把超时设为 1 秒 | 触发重试或降级 |
| Redis 不可用 | 停掉 Redis | 服务给出明确错误或降级 |
| 用户刷接口 | 循环请求 40 次 | 触发 429 |
| 主模型不可用 | 改错默认模型 | 尝试备用模型 |

## 8. 口述材料

### 8.1 3 分钟版本

可以这样讲：

```text
我第一个月做的是模型网关，目标是把大模型调用从业务代码里抽出来，变成一个统一、可治理的基础服务。

核心链路是：业务请求进入网关后，先做鉴权、限流和 request_id 生成，然后根据任务类型做模型路由，再通过 Provider 调用具体模型。非流式请求支持缓存，流式请求通过 SSE 返回。每次调用都会记录模型、耗时、Token、成本、Prompt 版本和状态。

这个设计的重点不是模型本身，而是后端工程化：超时重试、熔断降级、限流、缓存、成本统计和可观测性。后续 RAG 和 Agent 都可以复用这个网关能力。
```

### 8.2 高频追问

| 追问 | 回答要点 |
|---|---|
| 为什么需要模型网关 | 统一接入、治理、观测、成本、安全 |
| 为什么业务不直接调模型 | 分散调用会导致不可控、不可观测、重复开发 |
| 流式输出怎么做 | SSE + `StreamingResponse` + 异步生成器 |
| 限流放在哪里 | 模型调用前，避免成本浪费 |
| 哪些请求能缓存 | 非流式、低温度、不含实时和敏感信息 |
| 模型失败怎么办 | 超时、重试、熔断、备用模型、降级响应 |
| 成本怎么统计 | Token 数乘以模型单价，按用户和模型聚合 |
| Prompt 为什么要版本 | 效果可追踪，出问题可回滚 |
| 日志记录什么 | request_id、user_id、model、latency、Token、status |
| 最大风险是什么 | 成本失控、供应商异常、数据泄露、日志缺失 |

## 9. 图示

模型网关主链路：

```text
Client
  |
  v
Auth
  |
  v
Rate Limit
  |
  v
Cache Lookup
  |
  +-- hit --> Response
  |
  +-- miss
       |
       v
    Model Router
       |
       v
    Provider
       |
       v
    Model API
       |
       v
    Log + Cost + Metrics
       |
       v
    Response
```

多模型路由：

```text
request.model 存在
  |
  +-- 是 --> 使用指定模型
  |
  +-- 否
       |
       v
    判断 task_type
       |
       +-- coding --> coder model
       +-- summary --> long-context model
       +-- default --> default model
```

缓存链路：

```text
非流式请求
  |
  v
temperature <= 0.3
  |
  v
无实时 / 敏感字段
  |
  v
生成 hash key
  |
  +-- Redis 命中 --> 返回缓存
  |
  +-- Redis 未命中 --> 调模型 -> 写缓存
```

降级链路：

```text
调用主模型
  |
  +-- 成功 --> 返回
  |
  +-- 失败
       |
       v
    重试 1 到 2 次
       |
       +-- 成功 --> 返回
       |
       +-- 失败
            |
            v
         调用备用模型
            |
            +-- 成功 --> 返回
            |
            +-- 失败 --> 返回统一错误
```

观测链路：

```text
request_id
  |
  +--> API 日志
  +--> 限流日志
  +--> 缓存日志
  +--> 模型调用日志
  +--> 成本日志
  |
  v
一次请求完整画像
```

## 10. 最终检查清单

文档检查：

- [ ] TD 包含背景、目标、非目标、架构、接口、数据模型和代码。
- [ ] 所有核心缩写首次出现都有英文全称和中文含义。
- [ ] 有至少 5 个图示或配图。
- [ ] 有本地启动命令。
- [ ] 有接口测试命令。

代码检查：

- [ ] FastAPI 服务可启动。
- [ ] `/health` 可访问。
- [ ] 普通问答接口可调用。
- [ ] 流式问答接口可调用。
- [ ] Provider 抽象清晰。
- [ ] 模型路由可扩展。
- [ ] Redis 限流可运行。
- [ ] Redis 缓存可运行。
- [ ] 调用日志包含 request_id。
- [ ] API Key 不出现在代码和日志里。

能力检查：

- [ ] 能解释模型网关解决什么问题。
- [ ] 能解释 SSE 的工作方式。
- [ ] 能解释为什么要限流和缓存。
- [ ] 能解释模型失败后的降级链路。
- [ ] 能解释成本统计怎么做。
- [ ] 能解释 Prompt 版本的价值。
- [ ] 能把这套网关如何支撑后续 RAG 和 Agent 讲清楚。

## 11. Reference

## 12. Notes
