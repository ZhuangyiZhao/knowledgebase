# Explain、慢 SQL 分析、深分页优化

**适用场景：** SQL（Structured Query Language，结构化查询语言）性能定位、慢查询治理、列表页分页优化、线上抖动复盘。  
**回答主线：** 先用慢日志和监控确认问题，再用 `EXPLAIN` 看访问路径，最后围绕 **少扫行、少排序、少回表、少锁等待** 做 SQL、索引和链路调整。

## 目录

- [1. EXPLAIN 主要看哪些字段？（基本难度）](#1-explain-主要看哪些字段基本难度)
  - [1.1 最简练版](#11-最简练版)
  - [1.2 详细解释版](#12-详细解释版)
    - [1.2.1 type：访问类型](#121-type访问类型)
    - [1.2.2 key：实际使用的索引](#122-key实际使用的索引)
    - [1.2.3 rows：预估扫描行数](#123-rows预估扫描行数)
    - [1.2.4 Extra：额外执行信息](#124-extra额外执行信息)
    - [1.2.5 其他次要关注字段](#125-其他次要关注字段)
- [2. 慢 SQL 应该怎么分析？（中等难度）](#2-慢-sql-应该怎么分析中等难度)
  - [2.1 最简练版](#21-最简练版)
  - [2.2 详细解释版](#22-详细解释版)
    - [2.2.1 通用排查步骤](#221-通用排查步骤)
    - [2.2.2 具体例子：订单列表接口突然变慢](#222-具体例子订单列表接口突然变慢)
    - [2.2.3 结合 EXPLAIN 判断问题](#223-结合-explain-判断问题)
    - [2.2.4 优化方案和验证](#224-优化方案和验证)
    - [2.2.5 口述模板](#225-口述模板)
- [3. EXPLAIN 和 EXPLAIN ANALYZE 怎么配合？（中等难度）](#3-explain-和-explain-analyze-怎么配合中等难度)
  - [3.1 最简练版](#31-最简练版)
  - [3.2 详细解释版](#32-详细解释版)
  - [3.3 例子](#33-例子)
- [4. 深分页为什么慢？（中等难度）](#4-深分页为什么慢中等难度)
  - [4.1 最简练版](#41-最简练版)
  - [4.2 详细解释版](#42-详细解释版)
  - [4.3 例子](#43-例子)
- [5. 深分页怎么优化？（高难度）](#5-深分页怎么优化高难度)
  - [5.1 最简练版](#51-最简练版)
  - [5.2 详细解释版](#52-详细解释版)
  - [5.3 例子](#53-例子)
- [6. 慢查询治理上线时要注意什么？（高难度）](#6-慢查询治理上线时要注意什么高难度)
  - [6.1 最简练版](#61-最简练版)
  - [6.2 详细解释版](#62-详细解释版)
  - [6.3 例子](#63-例子)
- [7. Reference](#7-reference)
- [8. Notes](#8-notes)

---

## 1. EXPLAIN 主要看哪些字段？（基本难度）

### 1.1 最简练版

在 MySQL 中，用 `EXPLAIN` 分析 SQL 执行计划时，**最核心、最值得关注的字段通常是 `type`、`key`、`rows` 和 `Extra`**。  
`type` 看访问类型，是判断查询性能的关键；`key` 看实际用了哪个索引；`rows` 看预估扫描行数；`Extra` 看是否出现额外排序、临时表、覆盖索引等信息。  
如果 `type=ALL`、`key=NULL`、`rows` 很大，或者 `Extra` 出现 `Using filesort`、`Using temporary`，通常说明 SQL 或索引需要重点优化。  
其他字段比如 `id`、`key_len`、`filtered` 也要看，但更多是辅助判断执行顺序、联合索引使用程度和过滤效果。

### 1.2 详细解释版

`EXPLAIN` 的本质是让你看到优化器打算怎么执行一条 SQL。它不是直接告诉你“哪里慢”，而是暴露访问路径，方便判断扫描量、排序、回表和索引使用是否合理。

#### 1.2.1 type：访问类型

`type` 是衡量查询性能最关键的指标，描述 MySQL 如何查找表中的数据。

性能从优到差大致可以这样排序：

```text
system > const > eq_ref > ref > range > index > ALL
```

重点关注：

| `type` | 含义 | 怎么看 |
|---|---|---|
| `system` / `const` | 表最多匹配一行 | 非常好，常见于主键或唯一索引等值查询 |
| `eq_ref` | 连接时通过唯一索引匹配一行 | 性能优秀，多表连接里常见 |
| `ref` | 使用非唯一索引或唯一索引前缀匹配 | 性能较好，常见于普通索引等值查询 |
| `range` | 范围扫描，例如 `BETWEEN`、`>`、`<` | 比较理想，但要关注范围大小 |
| `index` | 全索引扫描 | 比全表扫描好一些，但依然可能扫很多数据 |
| `ALL` | 全表扫描 | 通常意味着索引没用上，性能最差，要重点排查 |

#### 1.2.2 key：实际使用的索引

`key` 表示 MySQL 最终决定使用的索引。

重点关注：

- 如果 `key` 为 `NULL`，说明没有使用索引，需要检查 `possible_keys` 和 SQL 条件是否匹配已有索引。
- 如果 `key` 不是预期索引，要看统计信息、字段选择性、联合索引顺序和查询条件。
- `possible_keys` 只是可能用到的索引，**不代表优化器一定会选它**。

#### 1.2.3 rows：预估扫描行数

`rows` 表示 MySQL 认为执行查询必须检查的行数，这是一个估算值。

重点关注：

- `rows` 越小，查询效率通常越高。
- 如果 `rows` 很大，说明扫描量大，通常需要通过索引、SQL 改写或缩小查询范围来优化。
- 如果 `rows` 和真实返回行数差距很大，要怀疑统计信息不准、数据分布倾斜或条件选择性差。

#### 1.2.4 Extra：额外执行信息

`Extra` 提供优化器选择执行计划的额外线索，尤其要关注是否发生额外排序、临时表或覆盖索引。

| `Extra` | 含义 | 怎么看 |
|---|---|---|
| `Using filesort` | MySQL 需要额外排序，无法完全利用索引完成排序 | **危险信号**，大结果集下可能很慢，通常要优化排序索引 |
| `Using temporary` | 使用临时表，常见于 `GROUP BY`、`DISTINCT`、复杂排序 | **危险信号**，会增加内存或磁盘开销 |
| `Using index` | 使用覆盖索引，不需要回表 | **优秀信号**，但仍要看扫描行数 |
| `Using where` | 存储引擎取出记录后，Server 层继续过滤 | 常见现象，关键看过滤前扫描了多少行 |
| `Using index condition` | ICP（Index Condition Pushdown，索引条件下推） | 能在索引层先过滤部分记录，减少回表 |

#### 1.2.5 其他次要关注字段

| 字段 | 含义 | 重点关注 |
|---|---|---|
| `id` | 查询序列号 | `id` 相同通常从上往下执行；`id` 不同通常 `id` 值大的先执行，例如子查询 |
| `key_len` | 使用索引的字节长度 | 可判断联合索引是否被充分利用，即大致用了多少个字段 |
| `filtered` | 返回结果行数占读取行数的百分比 | 值越大代表过滤效果越好；值很低说明读了很多无效行 |

回答时可以按这个顺序说：

1. **先看 `type`，判断访问方式是不是全表扫描或全索引扫描。**
2. **再看 `key`，确认实际使用的索引是否符合预期。**
3. **再看 `rows`，判断扫描量是否过大。**
4. **最后看 `Extra`，重点排查 `Using filesort`、`Using temporary`，同时留意 `Using index` 这种覆盖索引信号。**
5. **辅助看 `id`、`key_len`、`filtered`，判断执行顺序、联合索引利用程度和过滤效果。**

## 2. 慢 SQL 应该怎么分析？（中等难度）

### 2.1 最简练版

**慢 SQL 分析要先定位现象，再还原 SQL，最后结合执行计划、索引、数据分布和系统指标判断瓶颈。**  
我会先看慢日志、接口 RT（Response Time，响应时间）、P95（95th Percentile，第 95 百分位延迟）、CPU（Central Processing Unit，中央处理器）和连接数。  
然后带真实参数跑 `EXPLAIN`，看是否扫行过多、排序、临时表、回表或锁等待。  
优化后要用压测、灰度和监控验证，不能只看本地执行一次变快。

### 2.2 详细解释版

#### 2.2.1 通用排查步骤

慢 SQL 排查可以按六步走：

| 步骤 | 目标 | 重点 |
| --- | --- | --- |
| 1. 确认现象 | 判断是不是数据库瓶颈 | RT、P95、P99、错误率、CPU、I/O（Input/Output，输入输出） |
| 2. 找到 SQL | 从慢日志和监控定位 | SQL 文本、真实参数、调用方、频率 |
| 3. 看执行计划 | 判断访问路径 | `type`、`key`、`rows`、`Extra` |
| 4. 看表结构 | 判断索引是否匹配 | 主键、联合索引、字段类型、行宽 |
| 5. 看数据分布 | 判断过滤是否有效 | 大租户、热门状态、时间范围、倾斜值 |
| 6. 验证收益 | 防止只优化个例 | 压测、灰度、慢日志下降、资源下降 |

常用命令：

```sql
show variables like 'slow_query_log';
show variables like 'long_query_time';
show variables like 'log_queries_not_using_indexes';

explain select ...;
explain analyze select ...;

show index from order_tab;
show table status like 'order_tab';
show engine innodb status;
```

常见原因可以这样归类：

- **索引问题：** 没索引、索引顺序不对、低选择性索引、索引失效。
- **SQL 问题：** `select *`、函数包列、隐式类型转换、深分页、大范围排序。
- **数据问题：** 大租户、热点状态、历史数据堆积、统计信息不准。
- **系统问题：** 锁等待、连接池打满、磁盘 I/O 高、Buffer Pool（缓冲池）命中率下降。
- **链路问题：** 上游重试、批量导出、定时任务和核心流量抢资源。

容易踩坑的一点是：**不要只看单次耗时，要看调用频率和总成本。** 一条 `200ms` 的 SQL 如果 QPS（Queries Per Second，每秒查询数）很高，可能比偶发 `2s` 的 SQL 更值得优先治理。

#### 2.2.2 具体例子：订单列表接口突然变慢

假设线上有一个订单列表接口，最近业务反馈“商家后台打开订单列表很慢”。监控里看到：

| 指标 | 现象 | 初步判断 |
|---|---|---|
| 接口 RT | 平均从 `80ms` 涨到 `900ms` | 用户体感明显变慢 |
| P95 | 从 `150ms` 涨到 `2.8s` | 大部分慢请求不是偶发 |
| DB CPU | 从 `35%` 涨到 `85%` | 数据库压力明显上升 |
| 慢日志 | 出现大量订单列表查询 | 慢点大概率在 SQL |

慢日志里抓到的 SQL 类似这样：

```sql
select id, order_no, buyer_id, status, amount, created_at
from order_tab
where shop_id = 10001
  and status = 2
  and date(created_at) = '2026-05-06'
order by created_at desc
limit 20;
```

表结构和已有索引大致如下：

```sql
create table order_tab (
  id bigint primary key,
  shop_id bigint not null,
  buyer_id bigint not null,
  status tinyint not null,
  amount decimal(12,2) not null,
  created_at datetime not null,
  key idx_shop_id (shop_id),
  key idx_created_at (created_at)
);
```

这个 SQL 有两个明显风险：

1. **`date(created_at)` 对索引列做函数计算**，可能导致 `created_at` 索引用不上。
2. **过滤条件和排序条件没有一个匹配的联合索引**，MySQL 可能先扫很多行，再额外排序。

#### 2.2.3 结合 EXPLAIN 判断问题

先带真实参数执行：

```sql
explain
select id, order_no, buyer_id, status, amount, created_at
from order_tab
where shop_id = 10001
  and status = 2
  and date(created_at) = '2026-05-06'
order by created_at desc
limit 20;
```

可能看到类似结果：

| id | type | key | rows | Extra |
|---|---|---|---:|---|
| 1 | ref | idx_shop_id | 180000 | Using where; Using filesort |

这个执行计划可以这样解读：

| 字段 | 看到什么 | 说明什么 |
|---|---|---|
| `type=ref` | 用了 `shop_id` 普通索引 | 不是最差，但只按商家过滤还不够 |
| `key=idx_shop_id` | 实际只用了商家索引 | 没有同时利用 `status` 和 `created_at` |
| `rows=180000` | 预估扫描 18 万行 | 扫描量太大 |
| `Using filesort` | 需要额外排序 | `order by created_at desc` 没有利用合适索引顺序 |

所以这里不是简单说“用了索引就没问题”。真正的问题是：**索引用得不够精准，扫描行数大，并且还要额外排序**。

#### 2.2.4 优化方案和验证

第一步，先改写 SQL，避免对索引列做函数计算：

```sql
select id, order_no, buyer_id, status, amount, created_at
from order_tab
where shop_id = 10001
  and status = 2
  and created_at >= '2026-05-06 00:00:00'
  and created_at <  '2026-05-07 00:00:00'
order by created_at desc
limit 20;
```

第二步，根据查询条件和排序方式增加联合索引：

```sql
alter table order_tab
add index idx_shop_status_created (shop_id, status, created_at);
```

这个索引的设计逻辑是：

| 索引列 | 作用 |
|---|---|
| `shop_id` | 先按商家过滤，通常是高频查询条件 |
| `status` | 再按订单状态过滤 |
| `created_at` | 既做时间范围过滤，又支持按时间倒序取最新订单 |

优化后再看执行计划，可能变成：

| id | type | key | rows | Extra |
|---|---|---|---:|---|
| 1 | range | idx_shop_status_created | 800 | Using index condition |

优化前后可以这样验证：

| 指标 | 优化前 | 优化后 | 说明 |
|---|---:|---:|---|
| `rows` | 180000 | 800 | 扫描行数明显下降 |
| `Extra` | Using where; Using filesort | Using index condition | 避免大范围额外排序 |
| 单次耗时 | 900ms 左右 | 30ms 到 60ms | 用户体感恢复 |
| DB CPU | 85% | 40% 左右 | 数据库压力下降 |

上线时还要注意：

- **先确认新增索引的写入成本**，订单表如果写入很高，索引不是越多越好。
- **选择低峰期建索引**，大表建索引要关注锁、复制延迟和磁盘空间。
- **灰度验证接口指标**，看 P95、慢日志数量、DB CPU 是否真的下降。
- **保留回滚方案**，如果索引导致写入抖动，要能快速处理。

#### 2.2.5 口述模板

这类题可以这样回答：

> 慢 SQL 我一般不会直接上来就改索引，而是先确认是不是数据库瓶颈。比如一个订单列表接口变慢，我会先看接口 RT、P95、慢日志、DB CPU 和连接数，找到具体 SQL 和真实参数。然后用 `EXPLAIN` 看 `type`、`key`、`rows`、`Extra`，如果发现只用了单列索引、扫描行数很大，还出现 `Using filesort`，就说明问题大概率是索引不匹配查询和排序。  
> 
> 具体优化时，我会先改写 SQL，比如把 `date(created_at)` 改成时间范围，避免索引失效；再根据 `where shop_id/status` 和 `order by created_at` 建联合索引 `(shop_id, status, created_at)`。优化后再看 `rows` 是否下降、`Using filesort` 是否消失，并通过灰度观察 P95、慢日志数量和 DB CPU。核心不是只让一条 SQL 本地变快，而是让线上整体扫描量、排序成本和资源占用都下降。

## 3. EXPLAIN 和 EXPLAIN ANALYZE 怎么配合？（中等难度）

### 3.1 最简练版

**`EXPLAIN` 看优化器预估计划，`EXPLAIN ANALYZE` 看真实执行过程。**  
`EXPLAIN` 不真正执行查询，适合快速判断索引和扫描路径；`EXPLAIN ANALYZE` 会执行 SQL，能看到真实耗时、真实行数和循环次数。  
如果预估行数和真实行数差距很大，通常说明统计信息、数据分布或条件选择性存在问题。  
线上使用 `EXPLAIN ANALYZE` 要谨慎，因为它会真的跑查询。

### 3.2 详细解释版

两者的区别可以这样说：

| 工具 | 是否执行 SQL | 主要价值 | 风险 |
| --- | --- | --- | --- |
| `EXPLAIN` | 通常不执行目标查询 | 看优化器计划、索引选择、预估行数 | 只是估算 |
| `EXPLAIN FORMAT=JSON` | 通常不执行目标查询 | 看成本、条件下推、排序等细节 | 输出较长 |
| `EXPLAIN ANALYZE` | **会执行** | 看真实耗时、真实行数、循环次数 | 可能影响线上数据和负载 |

排查时可以先用：

```sql
explain
select id, order_no, created_at
from order_tab
where tenant_id = ?
  and status = ?
order by created_at desc
limit 20;
```

如果怀疑优化器估算错了，再在安全环境或低峰期用：

```sql
explain analyze
select id, order_no, created_at
from order_tab
where tenant_id = ?
  and status = ?
order by created_at desc
limit 20;
```

重点看三类差异：

1. **预估行数 vs 真实行数：** 差距大说明统计信息或数据倾斜可能影响计划。
2. **单个节点耗时：** 找到时间主要花在扫描、排序、嵌套循环还是回表。
3. **loops 次数：** 多表连接里，如果内表被循环访问很多次，可能需要调整连接顺序或索引。

如果统计信息不准，可以考虑：

```sql
analyze table order_tab;
```

但这只是让优化器估算更接近真实数据，**不等于一定能解决慢 SQL**。根本上仍要看索引路径和扫描量。

### 3.3 例子

假设订单表 `order_tab` 有 `1000` 万行，其中大部分订单都是 `status = 1`。现在有一个商家订单列表查询：

```sql
select id, order_no, created_at
from order_tab
where shop_id = 10001
  and status = 1
order by created_at desc
limit 20;
```

已有索引只有：

```sql
key idx_status_created (status, created_at)
```

先看 `EXPLAIN`：

| type | key | rows | Extra |
|---|---|---:|---|
| range | idx_status_created | 50000 | Using where |

从预估计划看，MySQL 认为走 `(status, created_at)` 索引大概扫描 `5` 万行，然后再过滤 `shop_id`。这个计划看起来不算最差，因为它用了索引，也没有出现 `Using filesort`。

但再看 `EXPLAIN ANALYZE`，可能发现真实情况是：

| 节点 | 预估行数 | 真实行数 | 真实耗时 | 说明 |
|---|---:|---:|---:|---|
| Index range scan on `idx_status_created` | 50000 | 920000 | 850ms | `status = 1` 选择性太差，真实扫描远高于预估 |
| Filter `shop_id = 10001` | 1000 | 20 | 860ms | 扫了大量其他商家的订单，最后只留下 20 条 |

这个例子说明：**`EXPLAIN` 告诉你优化器打算怎么走，`EXPLAIN ANALYZE` 告诉你这条路实际走得有多贵。**  
这里的根因不是“没用索引”，而是 **索引列顺序不匹配查询条件，且 `status` 选择性太差**。更合适的索引通常是：

```sql
alter table order_tab
add index idx_shop_status_created (shop_id, status, created_at);
```

优化后再看，理想状态是：

| 工具 | 重点观察 | 期望结果 |
|---|---|---|
| `EXPLAIN` | `key`、`rows`、`Extra` | 使用 `idx_shop_status_created`，预估扫描行数明显下降 |
| `EXPLAIN ANALYZE` | `actual rows`、`actual time`、`loops` | 真实扫描接近返回结果，耗时稳定下降 |

口述时可以这样说：**我会先用 `EXPLAIN` 看优化器预估的访问路径，再用 `EXPLAIN ANALYZE` 验证真实执行。如果发现预估 `5` 万行、实际扫了 `92` 万行，就说明统计信息、数据分布或索引选择存在问题。这个时候不能只说“用了索引”，而要继续判断这个索引是不是足够精准，是否匹配 `where` 条件和 `order by` 顺序。**

---

## 4. 深分页为什么慢？（中等难度）

### 4.1 最简练版

**深分页慢的本质是 `limit offset, size` 要先扫描并丢弃 offset 条记录，再返回 size 条。**  
当 offset 很大时，即使走了索引，也要沿着索引扫描很多条；如果查询列不覆盖索引，还可能产生大量回表。  
所以慢的不是 `limit` 本身，而是“为了拿最后几十条，前面几十万条也要先走一遍”。  
列表越往后翻，延迟和数据库资源消耗越容易放大。

### 4.2 详细解释版

典型 SQL：

```sql
select id, title, created_at
from article
where status = 1
order by created_at desc
limit 100000, 20;
```

数据库大概率要做几件事：

1. 按 `status = 1` 找到候选记录。
2. 按 `created_at desc` 得到有序结果。
3. 扫描前 `100000 + 20` 条。
4. 丢弃前 `100000` 条。
5. 返回最后 `20` 条。

如果索引是 `(status, created_at)`，它能帮助过滤和排序，但仍然不能让第 `100001` 条免费出现。  
如果查询字段不在索引里，前面被丢弃的记录也可能触发回表，成本会更高。

常见慢点：

- **offset 线性放大扫描量。**
- **排序无法利用索引时，需要额外排序。**
- **`select *` 破坏覆盖索引，回表次数增加。**
- **用户随意跳页或导出，绕过前端分页体验限制。**

回答时可以补一句：**深分页问题通常不是加单列索引就能解决，而是要改变访问方式。**

### 4.3 例子

假设文章表有 `200` 万条已发布文章，业务要查第 `5001` 页，每页 `20` 条：

```sql
select id, title, created_at
from article
where status = 1
order by created_at desc
limit 100000, 20;
```

即使已经有索引：

```sql
create index idx_status_created
on article(status, created_at);
```

数据库也不是直接跳到第 `100001` 条，而是要沿着索引顺序往后扫：

| 阶段 | 数据量 | 成本说明 |
|---|---:|---|
| 找到 `status = 1` 的有序记录 | 很多 | 依赖 `(status, created_at)` 索引 |
| 扫描分页窗口前的数据 | 100000 条 | 这些记录最终都会被丢弃 |
| 继续扫描本页数据 | 20 条 | 只有这 20 条返回给业务 |
| 返回结果 | 20 条 | 网络传输很少，但数据库扫描成本很高 |

如果查询列都在索引里，成本主要是 **扫描 `100020` 条索引记录**。  
如果写成 `select *`，并且字段不在索引里，前面被丢弃的 `100000` 条也可能触发大量回表，成本会进一步放大。

口述时可以这样说：**深分页慢不是因为返回了很多数据，而是因为数据库为了返回后面 20 条，必须先走过并丢弃前面 10 万条。offset 越大，扫描量越大；如果还伴随回表或额外排序，延迟就会快速上升。**

---

## 5. 深分页怎么优化？（高难度）

### 5.1 最简练版

**深分页优先用游标翻页，把 offset 改成基于上一页最后一条记录继续查。**  
如果必须保留跳页，可以先用覆盖索引查主键，再延迟关联回表取详情，减少回表成本。  
同时要让联合索引匹配 `where + order by + limit`，并限制最大页深。  
导出和后台统计不要走同步深分页，通常改成异步任务更稳。

### 5.2 详细解释版

方案一：游标翻页。

```sql
select id, title, created_at
from article
where status = 1
  and created_at < ?
order by created_at desc
limit 20;
```

如果 `created_at` 可能重复，要加 `id` 做稳定游标：

```sql
select id, title, created_at
from article
where status = 1
  and (
    created_at < ?
    or (created_at = ? and id < ?)
  )
order by created_at desc, id desc
limit 20;
```

对应索引：

```sql
create index idx_status_time_id
on article(status, created_at, id);
```

方案二：延迟关联。

```sql
select a.id, a.title, a.content, a.created_at
from article a
join (
  select id
  from article
  where status = 1
  order by created_at desc, id desc
  limit 100000, 20
) t on a.id = t.id
order by a.created_at desc, a.id desc;
```

这个方案仍然会扫描 offset，但子查询只扫描覆盖索引，最后只对 `20` 条记录回表，适合必须兼容页码跳转的场景。

方案三：限制产品能力。

- 用户侧只允许查看前 N 页。
- 后台查询强制选择时间范围。
- 大批量导出走异步任务。
- 搜索类需求交给专门检索系统或离线宽表。

方案取舍：

| 方案 | 适用场景 | 优点 | 代价 |
| --- | --- | --- | --- |
| 游标翻页 | 信息流、订单列表、消息列表 | 扫描稳定，性能最好 | 不适合任意跳页 |
| 延迟关联 | 必须保留页码 | 减少大量回表 | offset 扫描仍存在 |
| 覆盖索引 | 列表字段少 | 少读数据页 | 索引变宽有写成本 |
| 限制页深 | 用户侧列表 | 资源可控 | 需要产品配合 |
| 异步导出 | 后台报表 | 不阻塞核心链路 | 链路复杂度增加 |

### 5.3 例子

还是文章列表场景，原 SQL 是：

```sql
select id, title, created_at
from article
where status = 1
order by created_at desc, id desc
limit 100000, 20;
```

如果业务只是“下一页、上一页”这种连续翻页，优先改成游标翻页。第一页查询：

```sql
select id, title, created_at
from article
where status = 1
order by created_at desc, id desc
limit 20;
```

假设第一页最后一条是：

| id | created_at |
|---:|---|
| 880001 | 2026-05-06 10:00:00 |

第二页就带上上一页最后一条的游标：

```sql
select id, title, created_at
from article
where status = 1
  and (
    created_at < '2026-05-06 10:00:00'
    or (created_at = '2026-05-06 10:00:00' and id < 880001)
  )
order by created_at desc, id desc
limit 20;
```

配套索引：

```sql
create index idx_status_created_id
on article(status, created_at, id);
```

优化前后对比：

| 方案 | SQL 特点 | 扫描成本 | 适用场景 |
|---|---|---:|---|
| `limit 100000, 20` | 按页码跳转 | 至少扫描 `100020` 条 | 兼容传统页码 |
| 游标翻页 | 基于上一页最后一条继续查 | 接近扫描 `20` 条 | 信息流、订单列表、消息列表 |

如果业务强依赖“跳到第 N 页”，可以用延迟关联降低回表成本：

```sql
select a.id, a.title, a.content, a.created_at
from article a
join (
  select id
  from article
  where status = 1
  order by created_at desc, id desc
  limit 100000, 20
) t on a.id = t.id
order by a.created_at desc, a.id desc;
```

这时子查询只走覆盖索引拿 `id`，最后只对 `20` 条结果回表。它不能消除 offset 扫描，但能避免对前面 `100000` 条被丢弃记录做大量回表。

口述时可以这样说：**能改产品交互时，我优先把页码分页改成游标翻页，让每次查询都从上一页最后一条继续查。不能改交互时，我会用覆盖索引加延迟关联，把大 offset 的成本尽量控制在索引扫描上，减少无效回表。**

---

## 6. 慢查询治理上线时要注意什么？（高难度）

### 6.1 最简练版

**慢查询优化不能只改完 SQL 就上线，要评估 DDL（Data Definition Language，数据定义语言）风险、执行计划稳定性、回滚方案和监控指标。**  
加索引要避开高峰，关注锁、复制延迟、磁盘空间和构建耗时。  
SQL 改写要灰度验证，确认 P95、P99、扫描行数、CPU、I/O 和慢日志都改善。  
如果是核心链路，最好保留开关，异常时能快速回退。

### 6.2 详细解释版

上线前检查：

| 检查项 | 关注点 |
| --- | --- |
| 执行计划 | 新旧 SQL 的 `key`、`rows`、`Extra` 是否符合预期 |
| 数据分布 | 大租户、热点状态、边界时间范围是否覆盖 |
| 索引变更 | 是否产生锁、是否影响主从复制、磁盘空间是否足够 |
| 写入成本 | 新索引是否拖慢写入、更新、删除 |
| 回滚方案 | 能否关闭新路径、回退 SQL、删除新索引 |
| 监控指标 | RT、P95、P99、慢日志、CPU、I/O、连接数、锁等待 |

上线后观察：

```text
5 分钟：错误率、连接数、CPU 是否异常
30 分钟：慢日志和高分位延迟是否下降
1 天：高峰期是否稳定
1 周：索引命中率和写入成本是否可接受
```

常见追问可以这样接：

- 如果优化器没选新索引，先看统计信息和成本估算，不要马上强行 `force index`。
- 如果索引生效但仍慢，看返回行数、回表次数、排序和锁等待。
- 如果写入明显变慢，评估索引是否过宽、是否有重复索引、是否需要拆分读写场景。
- 如果数据继续增长，提前规划归档、冷热分离、异步化或分片。

### 6.3 例子

假设订单列表接口高峰期 P95 从 `120ms` 上升到 `1.8s`，慢日志里发现主要 SQL 是：

```sql
select id, order_no, status, created_at
from order_tab
where shop_id = ?
  and status = ?
order by created_at desc
limit 20;
```

原来只有单列索引：

```sql
key idx_shop_id (shop_id)
```

优化方案是新增联合索引并灰度切流：

```sql
alter table order_tab
add index idx_shop_status_created (shop_id, status, created_at);
```

上线前要准备的不是只有这条 DDL，还要把风险和验证点列清楚：

| 阶段 | 要做什么 | 重点指标 |
|---|---|---|
| 预发验证 | 对新旧 SQL 分别跑 `EXPLAIN` | `key` 是否命中新索引，`rows` 是否下降 |
| 低峰 DDL | 在线建索引，控制变更窗口 | DDL 耗时、锁等待、复制延迟、磁盘空间 |
| 小流量灰度 | 先放 `5%` 流量到新查询路径 | RT、P95、P99、错误率、慢日志数量 |
| 扩大流量 | 从 `5%` 到 `30%` 再到 `100%` | DB CPU、I/O、连接数、Buffer Pool 命中率 |
| 异常回退 | 关闭开关，回到旧 SQL 或降级列表能力 | 错误率是否恢复，数据库压力是否下降 |

如果灰度后发现读延迟下降，但写入 RT 从 `20ms` 升到 `80ms`，说明新索引的写入成本不可忽略。这个时候要继续评估：

- **索引是否过宽**，是否把不必要的列放进联合索引。
- **是否存在重复索引**，例如已有 `(shop_id, status)` 可以合并治理。
- **是否所有流量都需要这个索引**，如果只是低频后台查询，可能不值得牺牲核心写入。
- **是否需要产品限制或异步化**，例如导出、超深分页、复杂筛选不走核心库实时查询。

口述时可以这样说：**慢查询治理上线我会重点看四件事：执行计划是否真的变好、DDL 会不会影响线上、灰度指标是否符合预期、异常时能不能快速回退。尤其是加索引，不只看查询变快，还要看写入成本、复制延迟和磁盘空间，避免读优化把写链路拖慢。**

## 7. Reference

## 8. Notes
