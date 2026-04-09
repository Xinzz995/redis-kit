# Findings

## 2026-04-05: 设计阶段研究结论

### 架构决策
- **最终方案**: 方案 B（独立模块 + 共享连接 DI）
- **否决方案**: 方案 A（Facade 全包）过于耦合；方案 C（Provider 注册）增加不必要的间接层
- **老代码库**: Registry 单例 + Provider + Proxy 架构不适合新版，但 CacheHook 设计、Event Loop 隔离、冻结配置值得保留

### 技术要点
- 同步/异步策略: 小类 + 共享 `_logic.py`（非 IO 逻辑）
- 序列化/压缩: 独立为两层 Protocol（借鉴 django-redis）
- 异常处理: 具体异常类型 + FallbackPolicy 降级策略
- 连接管理: 延迟初始化 + WeakKeyDictionary event loop 隔离
- v1/v2 边界: v1 仅 Standalone，v2 扩展 Sentinel/Cluster

### 开源库借鉴
- Pottery → API 对齐 stdlib
- cashews → TTL 字符串格式, callable key/ttl
- django-redis → 压缩器独立层, TTL 操作集, SCAN 迭代
- Spring Data Redis → BoundOperations, 异常翻译层
- Lettuce → 连接同步/异步视图
- ioredis → 透明 key 前缀
- BadrElfarri/rediskit → decorator callable bypass

## 2026-04-09: 实施阶段发现

### fakeredis Lua 脚本支持
- fakeredis 默认不支持 `evalsha`/Lua 脚本，需要安装 `fakeredis[lua]`（依赖 `lupa`）
- 已在 pyproject.toml dev 依赖中添加 `fakeredis[lua]>=2.21`

### ruff UP035 规则
- Python 3.11+ 项目中，ruff 要求将 `Callable`, `Iterator`, `AsyncIterator` 等从 `collections.abc` 导入而非 `typing`
- 所有模块已统一使用 `from collections.abc import Callable` 等
