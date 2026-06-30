# Go channel、select、context 与异常处理

**适用场景：** Go 并发通信、取消传播、资源释放、异常边界、`goroutine` 泄漏治理。

**回答模板：** 先讲 `channel` 是带锁的通信队列和等待队列；再讲 `select` 如何在多个通信操作中选择；然后用 `context` 统一取消、超时和请求生命周期；最后说明 `defer`、`panic`、`recover` 的执行边界。

## 目录

- [1. channel 的底层机制是什么？（中等难度）](#1-channel-的底层机制是什么中等难度)
  - [1.1 最简练版](#11-最简练版)
  - [1.2 详细解释版](#12-详细解释版)
  - [1.3 图示和例子](#13-图示和例子)
- [2. 无缓冲 channel 和有缓冲 channel 的区别是什么？（基本难度）](#2-无缓冲-channel-和有缓冲-channel-的区别是什么基本难度)
  - [2.1 最简练版](#21-最简练版)
  - [2.2 详细解释版](#22-详细解释版)
  - [2.3 图示和例子](#23-图示和例子)
- [3. select 的底层行为是什么？（中等难度）](#3-select-的底层行为是什么中等难度)
  - [3.1 最简练版](#31-最简练版)
  - [3.2 详细解释版](#32-详细解释版)
  - [3.3 图示和例子](#33-图示和例子)
- [4. context 解决了什么问题？（基本难度）](#4-context-解决了什么问题基本难度)
  - [4.1 最简练版](#41-最简练版)
  - [4.2 详细解释版](#42-详细解释版)
  - [4.3 图示和例子](#43-图示和例子)
- [5. 如何避免 goroutine 泄漏？（高难度）](#5-如何避免-goroutine-泄漏高难度)
  - [5.1 最简练版](#51-最简练版)
  - [5.2 详细解释版](#52-详细解释版)
  - [5.3 图示和例子](#53-图示和例子)
- [6. defer 的执行时机和常见坑有哪些？（中等难度）](#6-defer-的执行时机和常见坑有哪些中等难度)
  - [6.1 最简练版](#61-最简练版)
  - [6.2 详细解释版](#62-详细解释版)
  - [6.3 图示和例子](#63-图示和例子)
- [7. panic 和 recover 应该如何使用？（中等难度）](#7-panic-和-recover-应该如何使用中等难度)
  - [7.1 最简练版](#71-最简练版)
  - [7.2 详细解释版](#72-详细解释版)
  - [7.3 图示和例子](#73-图示和例子)
- [8. Reference](#8-reference)
- [9. Notes](#9-notes)

---

## 1. channel 的底层机制是什么？（中等难度）

### 1.1 最简练版

**channel 本质是 Go 运行时提供的并发安全通信结构。**  
它底层包含环形缓冲区、发送等待队列、接收等待队列和一把锁。  
发送和接收时，如果能直接匹配等待方，就直接交付；否则根据缓冲区状态决定入队、出队或挂起当前 `goroutine`。  
所以 channel 既能传数据，也能表达同步和背压。

### 1.2 详细解释版

可以把 channel 理解成运行时里的 `hchan` 结构，核心信息包括：

| 字段类型 | 作用 |
|---|---|
| 缓冲区 | 有缓冲 channel 保存元素的环形队列 |
| `sendx` / `recvx` | 发送和接收在环形队列中的位置 |
| `sendq` | 因发送阻塞而等待的 `goroutine` 队列 |
| `recvq` | 因接收阻塞而等待的 `goroutine` 队列 |
| lock | 保护 channel 内部状态 |

发送过程大致是：

1. 如果有接收者正在等待，发送者直接把数据交给接收者。
2. 如果没有等待接收者，但缓冲区没满，数据进入缓冲区。
3. 如果缓冲区满了，发送者挂起，进入 `sendq`。

接收过程大致是：

1. 如果有发送者正在等待，接收者直接取发送者的数据。
2. 如果缓冲区有数据，从缓冲区取出。
3. 如果没有数据，接收者挂起，进入 `recvq`。

关闭 channel 时，等待中的接收者会被唤醒；继续从已关闭且已取空的 channel 接收，会得到零值和 `ok=false`。  
向已关闭的 channel 发送会触发 `panic`。

### 1.3 图示和例子

```text
channel
  |
  +-- buffer: [e1][e2][  ][  ]
  +-- sendq : 等待发送的 G
  +-- recvq : 等待接收的 G
  +-- lock  : 保护内部状态
```

典型代码：

```go
ch := make(chan int, 2)
ch <- 1
ch <- 2

v := <-ch
_ = v
```

---

## 2. 无缓冲 channel 和有缓冲 channel 的区别是什么？（基本难度）

### 2.1 最简练版

**无缓冲 channel 强调同步交接，有缓冲 channel 强调有限异步排队。**  
无缓冲 channel 发送必须等到接收者，接收也必须等到发送者，因此天然带同步语义。  
有缓冲 channel 在缓冲区未满时发送可以先返回，在缓冲区非空时接收可以先返回。  
缓冲区满了会阻塞发送，缓冲区空了会阻塞接收，因此它也能提供背压。

### 2.2 详细解释版

| 对比维度 | 无缓冲 channel | 有缓冲 channel |
|---|---|---|
| 创建方式 | `make(chan T)` | `make(chan T, n)` |
| 发送返回条件 | 接收者已经准备好 | 缓冲区未满或有接收者 |
| 接收返回条件 | 发送者已经准备好 | 缓冲区非空或有发送者 |
| 语义重点 | 同步交接 | 有限队列 |
| 常见用途 | 事件通知、严格同步 | 生产消费、削峰、限流 |

选择建议：

- 需要强同步时，用无缓冲 channel。
- 需要短暂吸收突发流量时，用有缓冲 channel。
- 不要把缓冲区当无限队列。容量过大只会隐藏下游慢的问题，并增加内存和延迟。

### 2.3 图示和例子

无缓冲：

```text
sender  ---- value ----> receiver
     必须同时准备好，发送才完成
```

有缓冲：

```text
sender -> [buffer: v1 v2 v3] -> receiver
          缓冲区未满时，sender 可先返回
```

---

## 3. select 的底层行为是什么？（中等难度）

### 3.1 最简练版

**select 用来等待多个 channel 操作，运行时会从已就绪的 case 中选择一个执行。**  
如果多个 case 同时就绪，Go 会做伪随机选择，避免长期偏向某一个 case。  
如果没有 case 就绪且有 `default`，会立即执行 `default`；如果没有 `default`，当前 `goroutine` 会挂起等待。  
`nil` channel 对应的 case 永远不会就绪，常用于动态开关某个分支。

### 3.2 详细解释版

`select` 的关键行为：

| 行为 | 说明 |
|---|---|
| 多 case 就绪 | 伪随机选一个 |
| 没有就绪且有 `default` | 立即执行 `default`，不会阻塞 |
| 没有就绪且无 `default` | 当前 `goroutine` 挂起 |
| channel 为 `nil` | 该 case 永远不就绪 |
| channel 已关闭 | 接收 case 会立即就绪，返回零值和 `ok=false` |

底层大致会做这些事：

1. 打乱 case 检查顺序，降低固定顺序带来的偏向。
2. 按固定锁顺序锁住涉及的 channel，避免死锁。
3. 扫描是否已有可执行的发送或接收。
4. 如果没有就绪分支，并且没有 `default`，把当前 `goroutine` 挂到相关 channel 的等待队列上。
5. 某个 channel 就绪后唤醒 `goroutine`，执行对应 case。

#### 3.2.1 如何理解 nil channel 动态开关分支

如果一个 channel 变量是 `nil`，那么对它发送或接收都会永远阻塞。  
所以在 `select` 里，如果某个 case 操作的是 `nil channel`，这个 case 就永远不会被选中，相当于这个分支被临时关闭。

比如：

```go
var ch <-chan int // nil channel

select {
case v := <-ch:
    fmt.Println(v)
case <-time.After(time.Second):
    fmt.Println("timeout")
}
```

这里 `ch` 是 `nil`，所以 `<-ch` 永远不会就绪。最后只可能走 `timeout` 分支。

“动态开关”的含义是：

```text
ch = nil     -> select 里的这个 case 永远不触发，相当于关闭
ch = realCh  -> case 恢复正常，等待 realCh 就绪
```

这个技巧常用于某个阶段不想再监听某个 channel，但又不想拆掉整个 `select` 结构。把 channel 变量设为 `nil` 后，对应 case 就自然失效。

### 3.3 图示和例子

```go
select {
case v := <-resultCh:
    return v, nil
case <-ctx.Done():
    return 0, ctx.Err()
default:
    return 0, nil
}
```

动态关闭分支：

```go
var ch <-chan int
if enable {
    ch = realCh
}

select {
case v := <-ch:
    _ = v
case <-ctx.Done():
    return
}
```

当 `enable=false` 时，`ch` 是 `nil`，第一个 case 永远不会被选中。

---

## 4. context 解决了什么问题？（基本难度）

### 4.1 最简练版

**context 解决的是跨 goroutine、跨调用链的取消、超时和请求级数据传递问题。**  
一个请求可能派生多个下游调用和后台任务，入口取消后，下游也应该尽快停止。  
`context.Context` 可以把取消信号、截止时间和少量请求级元数据沿调用链传递。  
它不是通用参数包，也不适合存大对象或可选业务参数。

### 4.2 详细解释版

常见用法：

| 能力 | 常见函数 | 作用 |
|---|---|---|
| 取消传播 | `context.WithCancel` | 主流程结束时通知子任务退出 |
| 超时控制 | `context.WithTimeout` | 控制某段逻辑最长执行时间 |
| 截止时间 | `context.WithDeadline` | 到指定时间自动取消 |
| 请求级值 | `context.WithValue` | 传链路追踪标识、用户标识等少量元数据 |

使用原则：

- 函数的第一个参数通常是 `ctx context.Context`。
- 创建带取消能力的 context 后，要及时调用 `cancel()`，释放定时器和相关资源。
- 不要把 `context` 存到结构体里长期复用。
- 不要用 `context.WithValue` 传业务参数、配置项或大对象。

### 4.3 图示和例子

```text
入口请求 ctx
  |
  +-- 数据库查询 ctx
  |
  +-- RPC 调用 ctx
  |
  +-- 后台 goroutine ctx

入口取消或超时
  |
  v
下游全部收到 ctx.Done()
```

```go
ctx, cancel := context.WithTimeout(parent, 200*time.Millisecond)
defer cancel()

select {
case result := <-resultCh:
    return result, nil
case <-ctx.Done():
    return nil, ctx.Err()
}
```

---

## 5. 如何避免 goroutine 泄漏？（高难度）

### 5.1 最简练版

**避免 goroutine 泄漏，核心是每个 goroutine 都要有明确退出条件。**  
常见泄漏来自 channel 永远没人读写、下游调用没有超时、后台循环没有监听退出信号。  
工程上要用 `context`、关闭 channel、超时控制、worker pool 和 `WaitGroup` 管理生命周期。  
线上可以通过 `pprof` 的 goroutine profile 看堆栈数量和阻塞位置。

### 5.2 详细解释版

常见泄漏来源：

| 泄漏类型 | 典型原因 | 解决思路 |
|---|---|---|
| channel 发送阻塞 | 下游不再接收 | 发送时监听 `ctx.Done()` |
| channel 接收阻塞 | 上游不再发送也不关闭 | 上游负责关闭，或接收侧监听取消 |
| 后台循环不退出 | `for {}` 没有退出分支 | 增加 context 或 stop channel |
| 外部调用卡住 | 没有超时 | 为网络、数据库、远程调用设置超时 |
| worker 无边界 | 每个请求都启动长期任务 | 使用 worker pool 或队列限流 |

排查路径：

1. 看 `runtime.NumGoroutine()` 是否持续上涨。
2. 打开 `net/http/pprof`，查看 `/debug/pprof/goroutine?debug=2`。
3. 关注堆栈里大量重复的位置，比如 `<-ch`、`ch <- x`、`sync.(*Mutex).Lock`、网络读写。
4. 结合近期发布、流量变化、下游异常，判断是新代码路径还是外部阻塞。

### 5.3 图示和例子

容易泄漏的写法：

```go
go func() {
    resultCh <- query()
}()
```

如果外层超时返回，`resultCh` 又没人接收，这个发送就可能永久阻塞。  
更稳的写法：

```go
go func() {
    result := query()
    select {
    case resultCh <- result:
    case <-ctx.Done():
        return
    }
}()
```

生命周期图：

```text
启动 goroutine
  |
  +-- 正常完成 -> return
  |
  +-- ctx 取消 -> return
  |
  +-- 上游关闭 -> return
```

---

## 6. defer 的执行时机和常见坑有哪些？（中等难度）

### 6.1 最简练版

**defer 会在当前函数返回前执行，多个 defer 按 LIFO（Last In First Out，后进先出）顺序执行。**  
`defer` 注册时，函数值、方法 receiver 和参数会立即求值；真正的函数体会等到当前函数退出前再执行。  
`return` 时会先计算返回值，再执行 `defer`，最后函数真正返回。  
它常用于释放资源、解锁、记录耗时、恢复异常，但容易踩坑：循环里延迟释放资源、闭包捕获变量、命名返回值被修改、`os.Exit` 不执行 `defer`、清理逻辑里的 `panic` 覆盖原始错误。

### 6.2 详细解释版

关键规则：

| 规则 | 说明 |
|---|---|
| 执行时机 | 当前函数返回前，或 panic 展开栈时 |
| 执行顺序 | 后注册的先执行 |
| 注册阶段 | 函数值、方法 receiver、参数表达式立即求值 |
| 执行阶段 | deferred function 的函数体延后执行 |
| 命名返回值 | `defer` 可以在 return 之后、函数真正返回前修改它 |
| 资源释放 | 不要在大循环里直接 `defer Close()`，除非每轮都在单独函数里 |
| 退出边界 | `return` 和 `panic` 会执行 `defer`，`os.Exit` 和 `log.Fatal` 不会 |

`return` 和 `defer` 的顺序要记成三步：

```text
计算 return 后面的表达式，或把值赋给命名返回值
  |
  v
按 LIFO 顺序执行 defer
  |
  v
函数真正返回给调用方
```

`panic` 时也会执行当前 goroutine 调用栈上的 `defer`：

```text
发生 panic
  |
  v
当前 goroutine 开始展开调用栈
  |
  v
每一层函数退出前先执行自己的 defer
  |
  v
如果某个 defer recover 成功，panic 停止传播
```

面试里容易答错的点主要有：

| 易错点 | 关键结论 |
|---|---|
| `defer fmt.Println(x)` | `x` 在注册时就被取值 |
| `defer func(){ fmt.Println(x) }()` | 闭包里的 `x` 在执行时读取 |
| `defer obj.Method()` | `obj` 这个 receiver 表达式在注册时求值 |
| 命名返回值 | `defer` 可以改最终返回值 |
| 非命名返回值 | `return` 表达式已经先被拷贝到返回槽 |
| 循环里 `defer Close()` | 资源等外层函数结束才释放 |
| `defer` 解锁 | 要确认锁的生命周期，不要把循环内解锁拖到函数结束 |
| `os.Exit` / `log.Fatal` | 直接退出进程，不执行 `defer` |

### 6.3 图示和例子

下面这些例子都适合面试时先问“输出是什么”，再解释原因。

1. **参数立即求值**

```go
i := 1
defer fmt.Println("defer:", i)
i = 2
```

输出：

```text
defer: 1
```

原因：`fmt.Println` 的参数 `i` 在注册 `defer` 时已经被求值。

2. **用 defer 统计耗时写错**

```go
start := time.Now()
defer fmt.Println("cost:", time.Since(start))

time.Sleep(100 * time.Millisecond)
```

输出的耗时会接近 `0`，因为 `time.Since(start)` 在注册时已经执行。  
正确写法是把计算放进延迟执行的函数体里：

```go
start := time.Now()
defer func() {
    fmt.Println("cost:", time.Since(start))
}()

time.Sleep(100 * time.Millisecond)
```

3. **闭包捕获外部变量**

```go
i := 0
for ; i < 3; i++ {
    defer func() {
        fmt.Println(i)
    }()
}
```

输出：

```text
3
3
3
```

原因：闭包捕获的是同一个外部变量 `i`，真正执行时循环已经结束。  
更稳的写法是把值作为参数传进去：

```go
for i := 0; i < 3; i++ {
    defer func(v int) {
        fmt.Println(v)
    }(i)
}
```

输出：

```text
2
1
0
```

注意：Go 1.22+ 调整了循环变量语义，经典 `for range` 闭包题在新老版本里结论可能不同。面试时最好主动说明版本；上面第一个例子用的是循环外变量，各版本都成立。

4. **循环里 defer 释放资源太晚**

```go
for _, file := range files {
    f, _ := os.Open(file)
    defer f.Close()
}
```

这些文件会等整个函数结束才关闭，可能耗尽文件描述符。

可以把它想成去图书馆借书：每循环一次借一本书，`defer f.Close()` 不是“看完这一本马上还”，而是“先记账，等今天离开图书馆时一起还”。  
如果 `files` 很多，实际执行效果就是：

```text
打开第 1 个文件，不关
打开第 2 个文件，不关
打开第 3 个文件，不关
...
函数结束，才开始一个个关
```

文件、网络连接、锁这些都属于资源，系统能同时打开的资源数量是有限的。一直打开不关，就可能报 `too many open files` 这类错误。

所以要记住：**`defer` 跟函数绑定，不跟循环绑定。循环里直接 `defer`，资源会拖到整个函数结束才释放。**

更好的方式是把每轮逻辑放进独立函数，让 `defer` 在每一轮的小函数结束时执行：

```go
for _, file := range files {
    if err := func() error {
        f, err := os.Open(file)
        if err != nil {
            return err
        }
        defer f.Close()

        return handle(f)
    }(); err != nil {
        return err
    }
}
```

这样执行效果就变成：

```text
打开第 1 个文件，处理，关闭
打开第 2 个文件，处理，关闭
打开第 3 个文件，处理，关闭
```

5. **循环里 defer 解锁导致死锁**

```go
for _, item := range items {
    mu.Lock()
    defer mu.Unlock()

    handle(item)
}
```

第一轮加锁后，`Unlock` 要等整个函数返回才执行。第二轮再次 `Lock` 时就可能卡住。  
循环里的锁通常应该在本轮结束时释放：

```go
for _, item := range items {
    mu.Lock()
    handle(item)
    mu.Unlock()
}
```

如果 `handle` 可能 `panic`，可以把每轮逻辑包进单独函数，再在里面 `defer mu.Unlock()`。

6. **命名返回值会被 defer 修改**

```go
func f() (n int) {
    defer func() {
        n++
    }()

    return 1
}
```

返回值是：

```text
2
```

原因：`return 1` 先把 `n` 赋值为 `1`，再执行 `defer`，所以最终返回 `2`。

7. **非命名返回值不会被 defer 改掉**

```go
func f() int {
    n := 1
    defer func() {
        n++
    }()

    return n
}
```

返回值是：

```text
1
```

原因：`return n` 先把 `n` 的值拷贝到返回槽，之后 `defer` 修改的是局部变量 `n`，不是最终返回值。

8. **命名返回值和参数立即求值叠加**

```go
func f() (n int) {
    defer fmt.Println("defer:", n)

    n = 1
    return n
}
```

输出和返回值：

```text
defer: 0
return: 1
```

原因：`fmt.Println` 的参数在 `defer` 注册时求值，当时 `n` 还是零值。

9. **方法 receiver 的求值时机**

```go
type Counter int

func (c Counter) Value() {
    fmt.Println("value:", c)
}

func (c *Counter) Ptr() {
    fmt.Println("ptr:", *c)
}

func demo() {
    c := Counter(1)

    defer c.Value()
    defer c.Ptr()

    c = 2
}
```

输出：

```text
ptr: 2
value: 1
```

原因：`defer c.Value()` 注册时复制了值 receiver；`defer c.Ptr()` 注册时保存的是指向 `c` 的地址，执行时看到的是修改后的值。再叠加 LIFO，所以先输出 `ptr`。

10. **defer 注册的是 nil 函数值**

```go
var cleanup func()

defer cleanup()

cleanup = func() {
    fmt.Println("cleanup")
}
```

函数返回时会 `panic`，因为 `defer` 注册时保存的是 nil 函数值。后面再给 `cleanup` 赋值也没有用。

11. **还没判断 err 就 defer Close**

```go
resp, err := http.Get(url)
defer resp.Body.Close()

if err != nil {
    return err
}
```

如果请求失败，`resp` 可能是 `nil`，这段代码会因为访问 `resp.Body` 触发 `panic`。  
正确顺序是先判断错误，再注册清理动作：

```go
resp, err := http.Get(url)
if err != nil {
    return err
}
defer resp.Body.Close()
```

12. **忽略 Close 的错误**

```go
func write(path string, data []byte) (err error) {
    f, err := os.Create(path)
    if err != nil {
        return err
    }
    defer f.Close()

    _, err = f.Write(data)
    return err
}
```

`f.Close()` 可能触发真正的刷盘或写回错误，但这里的错误被直接丢掉了。对文件写入这类场景，可以用命名返回值接住：

```go
func write(path string, data []byte) (err error) {
    f, err := os.Create(path)
    if err != nil {
        return err
    }
    defer func() {
        if closeErr := f.Close(); err == nil {
            err = closeErr
        }
    }()

    _, err = f.Write(data)
    return err
}
```

13. **os.Exit 和 log.Fatal 不执行 defer**

```go
func main() {
    defer fmt.Println("cleanup")

    os.Exit(1)
}
```

不会输出 `cleanup`。`log.Fatal` 内部也会调用 `os.Exit`，所以同样不会执行 `defer`。如果需要清理资源，要在退出前显式清理。

14. **defer 里的 panic 会干扰原始 panic**

```go
func f() {
    defer func() {
        if r := recover(); r != nil {
            fmt.Println("recover:", r)
        }
    }()

    defer func() {
        panic("defer panic")
    }()

    panic("body panic")
}
```

输出：

```text
recover: defer panic
```

原因：先发生 `body panic`，栈展开时执行第二个 `defer`，它又触发了新的 `panic`。外层 `recover` 捕获到的是后一个 `panic`。清理逻辑里尽量不要再 `panic`，否则会让真正的失败原因变得很难查。

15. **多个 defer 的执行顺序**

```go
func demo() {
    defer fmt.Println("A")
    defer fmt.Println("B")
    defer fmt.Println("C")
}
```

输出顺序：

```text
C
B
A
```

---

## 7. panic 和 recover 应该如何使用？（中等难度）

### 7.1 最简练版

**panic 表示当前流程遇到无法继续执行的异常，recover 用来在 defer 中捕获 panic。**  
`recover` 只有在同一个 `goroutine` 的 deferred function 中调用才有效。  
业务错误优先返回 `error`，不要用 `panic` 做普通控制流。  
`panic/recover` 更适合放在服务入口、中间件、任务边界和 goroutine 顶层，避免整个进程被异常打垮。

### 7.2 详细解释版

使用边界：

| 场景 | 建议 |
|---|---|
| 参数校验失败 | 返回 `error` |
| 下游调用失败 | 返回 `error` 并带上下文 |
| 程序不可恢复状态 | 可以 `panic` |
| Web handler 边界 | 用中间件 `recover`，记录日志并返回错误响应 |
| 新启动的 goroutine | 顶层加 `defer recover`，防止异常直接杀进程 |

重要规则：

- `recover` 必须在 `defer` 注册的函数里直接或间接执行。
- `recover` 不能捕获其他 `goroutine` 的 `panic`。
- 捕获后要记录堆栈，避免问题被吞掉。
- 捕获后要考虑是否继续运行，某些状态损坏类错误不适合继续处理。

### 7.3 图示和例子

```go
func safeRun(fn func()) {
    defer func() {
        if r := recover(); r != nil {
            log.Printf("panic: %v\n%s", r, debug.Stack())
        }
    }()

    fn()
}
```

跨 `goroutine` 捕获无效：

```go
defer func() {
    _ = recover()
}()

go func() {
    panic("boom")
}()
```

外层 `recover` 捕不到新 `goroutine` 里的 `panic`。新 `goroutine` 要自己在顶层加保护。

```text
G1 defer recover
 |
 +-- G2 panic

G1 捕不到 G2 的 panic
```

---

## 8. Reference

## 9. Notes
