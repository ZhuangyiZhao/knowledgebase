# Go sync 并发原语与服务排障

**适用场景：** 锁选择、并发任务编排、对象复用、CPU（Central Processing Unit，中央处理器）飙高、内存上涨、RT（Response Time，响应时间）抖动。

**回答模板：** 先按读写比例和临界区成本选择 `Mutex` 或 `RWMutex`；再说明 `Once`、`WaitGroup`、`Pool` 各自只解决一种问题；最后把 CPU、内存和 RT 排障拆成“确认范围、抓剖析、看指标、定位代码路径”四步。

## 目录

- [1. sync.Mutex 和 sync.RWMutex 怎么选？（中等难度）](#1-syncmutex-和-syncrwmutex-怎么选中等难度)
  - [1.1 最简练版](#11-最简练版)
  - [1.2 详细解释版](#12-详细解释版)
  - [1.3 图示和例子](#13-图示和例子)
- [2. sync.Once、WaitGroup、Pool 的适用场景是什么？（基本难度）](#2-synconcewaitgrouppool-的适用场景是什么基本难度)
  - [2.1 最简练版](#21-最简练版)
  - [2.2 详细解释版](#22-详细解释版)
  - [2.3 图示和例子](#23-图示和例子)
- [3. Go 服务 CPU 飙高时如何排查？（高难度）](#3-go-服务-cpu-飙高时如何排查高难度)
  - [3.1 最简练版](#31-最简练版)
  - [3.2 详细解释版](#32-详细解释版)
  - [3.3 图示和例子](#33-图示和例子)
- [4. Go 服务内存上涨时如何排查？（高难度）](#4-go-服务内存上涨时如何排查高难度)
  - [4.1 最简练版](#41-最简练版)
  - [4.2 详细解释版](#42-详细解释版)
  - [4.3 图示和例子](#43-图示和例子)
- [5. Go 服务 RT 抖动大时你会怀疑哪些点？（高难度）](#5-go-服务-rt-抖动大时你会怀疑哪些点高难度)
  - [5.1 最简练版](#51-最简练版)
  - [5.2 详细解释版](#52-详细解释版)
  - [5.3 图示和例子](#53-图示和例子)
- [6. Reference](#6-reference)
- [7. Notes](#7-notes)

---

## 1. sync.Mutex 和 sync.RWMutex 怎么选？（中等难度）

### 1.1 最简练版

**默认优先考虑 `sync.Mutex`，只有在读多写少、读临界区明显较长时才考虑 `sync.RWMutex`。**  
`Mutex` 简单、开销低，适合大多数短临界区。  
`RWMutex` 允许多个读锁并发，但写锁会和所有读锁、写锁互斥，内部维护成本更高。  
如果读操作很短、写入频繁，`RWMutex` 可能比 `Mutex` 更慢。

### 1.2 详细解释版

选择维度：

| 维度 | 选择建议 |
|---|---|
| 读写比例 | 读远多于写，才考虑 `RWMutex` |
| 临界区耗时 | 读临界区越长，读锁并发收益越明显 |
| 写入频率 | 写多时 `RWMutex` 容易退化 |
| 代码复杂度 | `Mutex` 更简单，不容易误用 |
| 数据结构 | map、缓存、配置快照等常见场景可以评估 `RWMutex` |

`RWMutex` 的常见坑：

- 读锁不是无成本的，也有原子操作和状态维护。
- 不能从读锁直接升级成写锁，否则容易死锁。
- 有写锁等待时，新读锁可能被阻塞，以避免写者长期拿不到锁。
- 临界区里不要做慢 IO（Input/Output，输入输出）、远程调用或复杂计算，否则锁竞争会被放大。

进一步优化方向：

- 简单计数用 `atomic`。
- 读极多写极少的配置可以用 copy-on-write 或 `atomic.Value`。
- 高并发 map 可以做分片锁，降低单锁竞争。

### 1.3 图示和例子

```text
Mutex:

G1 ---- lock ---- unlock
G2      wait  ---- lock ---- unlock

RWMutex:

R1 ---- RLock -------- RUnlock
R2 ---- RLock -------- RUnlock
W1              wait -------- Lock ---- Unlock
```

读多写少缓存：

```go
type Cache struct {
    mu sync.RWMutex
    m  map[string]string
}

func (c *Cache) Get(k string) (string, bool) {
    c.mu.RLock()
    defer c.mu.RUnlock()
    v, ok := c.m[k]
    return v, ok
}

func (c *Cache) Set(k, v string) {
    c.mu.Lock()
    defer c.mu.Unlock()
    c.m[k] = v
}
```

---

## 2. sync.Once、WaitGroup、Pool 的适用场景是什么？（基本难度）

### 2.1 最简练版

**`sync.Once` 用于只初始化一次，`sync.WaitGroup` 用于等待一组 goroutine 完成，`sync.Pool` 用于复用临时对象、降低分配压力。**  
`Once` 适合懒加载配置、单例资源初始化。  
`WaitGroup` 适合并发 fan-out 后等待所有任务结束。  
`Pool` 适合复用 `bytes.Buffer` 这类临时对象，但不能用来保存必须可靠存在的业务状态。

### 2.2 详细解释版

| 类型 | 解决的问题 | 常见坑 |
|---|---|---|
| `sync.Once` | 保证某段初始化逻辑只执行一次 | 如果函数 panic，也会被视为已经执行过 |
| `sync.WaitGroup` | 等待多个 goroutine 完成 | `Add` 要在启动 goroutine 前调用；使用后不要复制 |
| `sync.Pool` | 复用临时对象，减少分配 | 池中对象可能在 GC（Garbage Collection，垃圾回收）时被清掉，不能依赖它做状态保存 |

`sync.Once` 使用原则：

- `Do(f)` 可以被调用很多次，但 `f` 最多只会真正执行一次。
- 多个 goroutine 同时调用 `Do(f)` 时，只有一个 goroutine 会执行 `f`，其他 goroutine 会等待它执行完成。
- 如果 `f` 执行过程中发生 panic，`Once` 也会认为这次 `Do` 已经执行过了，后续再调用 `Do(f)` 不会重试。

举个例子：

```go
var once sync.Once

func initConfig() {
    fmt.Println("start init")
    panic("init failed")
}

func main() {
    for i := 0; i < 2; i++ {
        func() {
            defer func() {
                if r := recover(); r != nil {
                    fmt.Println("recover:", r)
                }
            }()

            once.Do(initConfig)
        }()
    }
}
```

输出：

```text
start init
recover: init failed
```

注意第二次循环不会再次输出 `start init`。  
原因是：第一次 `once.Do(initConfig)` 虽然 panic 了，但 `sync.Once` 仍然把它当成已经执行过。后续再调用 `once.Do(initConfig)` 时，`initConfig` 不会再运行。

一句话记忆：

```text
sync.Once 只认“有没有执行过”，不保证“有没有执行成功”。
```

所以如果初始化逻辑可能失败，尤其是读配置、连数据库、请求远程服务这类场景，不要直接把失败藏在 `sync.Once` 里。更常见的做法是让初始化函数返回 `error`，或者自己设计可重试逻辑。

`WaitGroup` 使用原则：

- `Add(n)` 先执行，再启动 goroutine。
- 每个 goroutine 里 `defer wg.Done()`。
- 不要在 `Wait()` 可能已经开始后再并发 `Add()`。

`sync.Pool` 使用原则：

- 适合无状态、可重置、临时对象。
- `Get()` 出来后要重置对象状态。
- `Put()` 回去前不要再被其他地方引用。
- 不适合连接池、事务对象、必须关闭的资源。

### 2.3 图示和例子

`WaitGroup`：

```go
var wg sync.WaitGroup

for _, job := range jobs {
    wg.Add(1)
    go func(job Job) {
        defer wg.Done()
        handle(job)
    }(job)
}

wg.Wait()
```

`sync.Pool`：

```go
var bufPool = sync.Pool{
    New: func() any {
        return new(bytes.Buffer)
    },
}

buf := bufPool.Get().(*bytes.Buffer)
buf.Reset()
defer bufPool.Put(buf)
```

---

## 3. Go 服务 CPU 飙高时如何排查？（高难度）

### 3.1 最简练版

**CPU 飙高先确认是机器、容器还是进程级别，再用 CPU profile 定位热点函数。**  
Go 服务优先抓 `pprof/profile`，看 `top`、`list`、火焰图里哪些函数消耗最多。  
常见原因包括流量突增、死循环、复杂序列化、正则、压缩加密、GC 过频、锁竞争自旋和日志过量。  
定位后要结合发布记录、请求类型、下游状态和运行时指标，判断是业务热点还是运行时开销。

### 3.2 详细解释版

排查步骤：

1. **确认范围。** 看是单实例、单容器、单机器，还是全链路普遍升高。
2. **确认进程。** 用 `top`、`pidstat`、容器监控确认哪个进程吃 CPU。
3. **抓 CPU profile。**

```bash
curl -o cpu.pprof "http://127.0.0.1:6060/debug/pprof/profile?seconds=30"
go tool pprof cpu.pprof
```

4. **看热点。** 在 pprof 里用 `top`、`list funcName`、`web` 或浏览器视图看调用栈。
5. **交叉验证。** 对比发布、流量、错误率、GC、goroutine 数、锁等待、下游耗时。

常见原因表：

| 类型 | 现象 | 关注点 |
|---|---|---|
| 业务计算热点 | 某些业务函数在 profile 顶部 | 算法复杂度、循环次数、数据量 |
| 序列化开销 | JSON（JavaScript Object Notation，JavaScript 对象表示法）、反射、拷贝函数占比高 | 大对象、重复编码、字段过多 |
| 正则或字符串处理 | regexp、strings、bytes 占比高 | 正则复杂度、重复编译 |
| GC 开销 | runtime.gc 相关函数明显 | 分配速度、临时对象、堆增长 |
| 忙等循环 | 循环函数占满 CPU | 缺少 sleep、select default 空转 |
| 日志过量 | fmt、日志库、编码函数占比高 | 热路径日志、同步写盘 |

### 3.3 图示和例子

```text
CPU 飙高
  |
  v
确认范围：单实例还是全局
  |
  v
抓 CPU profile
  |
  v
定位热点函数
  |
  v
结合发布 / 流量 / GC / 下游
  |
  v
修复并压测验证
```

忙等例子：

```go
for {
    select {
    case job := <-jobCh:
        handle(job)
    default:
        // 空转会持续消耗 CPU
    }
}
```

如果确实需要非阻塞轮询，也要有退避、定时器或事件驱动机制。

---

## 4. Go 服务内存上涨时如何排查？（高难度）

### 4.1 最简练版

**内存上涨要先区分是 Go heap 上涨、goroutine 栈上涨，还是 RSS（Resident Set Size，常驻内存集）上涨。**  
Go 服务优先看 heap profile、alloc profile、goroutine profile 和 GC 指标。  
常见原因包括对象缓存无上限、slice 引用大数组、goroutine 泄漏、map 持续增长、临时对象分配过多、cgo 或 mmap 不受 Go heap 直接统计。  
判断是否泄漏要看 GC 后堆是否持续回落，如果每次 GC 后基线仍上升，就要重点排查存活对象。

### 4.2 详细解释版

排查步骤：

1. **看趋势。** 是持续上涨、不回落，还是周期性上涨后回落。
2. **区分指标。** 对比 heap、RSS、goroutine 数、GC 次数、分配速率。
3. **抓 heap profile。**

```bash
curl -o heap.pprof "http://127.0.0.1:6060/debug/pprof/heap"
go tool pprof -sample_index=inuse_space heap.pprof
```

4. **看累计分配。**

```bash
curl -o allocs.pprof "http://127.0.0.1:6060/debug/pprof/allocs"
go tool pprof -sample_index=alloc_space allocs.pprof
```

5. **看 goroutine。**

```bash
curl "http://127.0.0.1:6060/debug/pprof/goroutine?debug=2"
```

常见原因：

| 类型 | 表现 | 处理 |
|---|---|---|
| 缓存无上限 | map 或本地缓存持续增大 | 加容量、过期、淘汰策略 |
| slice 持有大数组 | 小切片引用大底层数组 | `copy` 出需要的数据 |
| goroutine 泄漏 | goroutine 数持续上涨 | 查阻塞堆栈和退出条件 |
| 临时对象过多 | alloc profile 很高 | 复用对象、减少转换和拷贝 |
| 指针对象过多 | GC 扫描压力大 | 优化结构体、拆分热路径 |
| cgo/native 内存 | RSS 涨但 heap 不明显 | 查 native 分配、mmap、外部库 |

### 4.3 图示和例子

```text
内存上涨
  |
  v
heap 涨？ ---- no ---- RSS 涨？
  |                    |
 yes                  yes
  |                    v
  v              查 cgo / mmap / 线程栈 / 系统缓存
抓 heap profile
  |
  v
看 inuse_space 和 inuse_objects
  |
  v
定位存活对象来源
```

slice 持有大数组：

```go
func head(data []byte) []byte {
    return data[:10]
}
```

如果 `data` 很大，返回的 10 字节仍会引用整个底层数组。可以复制：

```go
func headCopy(data []byte) []byte {
    out := make([]byte, 10)
    copy(out, data[:10])
    return out
}
```

---

## 5. Go 服务 RT 抖动大时你会怀疑哪些点？（高难度）

### 5.1 最简练版

**RT 抖动要优先看尾延迟，比如 P99（99th Percentile，第 99 百分位）和 P999（99.9th Percentile，第 99.9 百分位），而不是只看平均值。**  
我会先判断抖动来自服务内部、下游依赖、网络、机器资源还是流量排队。  
Go 服务内部重点怀疑 GC、CPU 抢占或限额、锁竞争、channel 堵塞、连接池耗尽、goroutine 暴涨和大对象分配。  
排查时要把 trace、pprof、日志、指标和下游耗时串起来看。

### 5.2 详细解释版

怀疑点清单：

| 方向 | 具体怀疑点 |
|---|---|
| 资源 | CPU 打满、容器被限流、内存紧张、磁盘 IO 慢 |
| GC | 分配突增、GC 频率升高、暂停影响尾延迟 |
| 调度 | goroutine 太多、可运行队列堆积、系统调用阻塞 |
| 锁 | `Mutex`、`RWMutex`、全局 map、连接池锁竞争 |
| channel | 有缓冲 channel 堆积、无缓冲 channel 等待、select 空转 |
| 下游 | 数据库慢查询、缓存大 key、远程调用超时、连接池不足 |
| 网络 | 丢包、重传、跨机房调用、DNS（Domain Name System，域名系统）解析慢 |
| 发布 | 新版本算法变慢、日志变多、序列化对象变大 |

排查路径：

1. 看 `p50/p90/p99/p999`，确认是整体变慢还是尾部抖动。
2. 按接口、实例、机房、依赖维度切分，找到异常集中点。
3. 对比 CPU、内存、GC、goroutine、连接池、队列长度。
4. 抓 `runtime/trace`、CPU profile、heap profile、mutex profile、block profile。
5. 对照慢请求日志和链路追踪，确认耗时卡在哪一段。

常用抓取：

```bash
curl -o trace.out "http://127.0.0.1:6060/debug/pprof/trace?seconds=5"
go tool trace trace.out
```

锁和阻塞剖析需要代码里打开采样：

```go
runtime.SetMutexProfileFraction(10)
runtime.SetBlockProfileRate(1)
```

### 5.3 图示和例子

```text
RT 抖动
  |
  v
是所有接口吗？
  |
  +-- 是 -> 看资源 / GC / 网络 / 机器
  |
  +-- 否 -> 看特定接口代码路径 / 下游 / 数据规模
          |
          v
      查 trace + pprof + 慢日志
```

一次典型判断：

```text
P99 上升
  |
  v
CPU 未满，但 goroutine 数上涨
  |
  v
goroutine profile 显示大量等待连接池
  |
  v
下游 RT 上升或连接池过小
```

这种情况下，盲目扩容 Go 服务不一定有效，可能需要优化下游、连接池、超时和降级策略。

---

## 6. Reference

## 7. Notes
