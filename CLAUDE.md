# 项目：redis-kit

基于 redis-py 的企业级工具库，支持同步/异步双模 API。

## 交流语言
默认使用中文交流（强制要求）。

## 代码风格

- python文件命名，下划线分隔，全小写，例如：bloom_filter.py、async_cache_service.py
- 文件夹命名，kebab-case，全小写，最多 4 层深度，例如：redis-kit/
- 单文件场景，直接放父目录，不单独建文件夹

## 常用命令
```bash
# 依赖管理  
uv sync                                       # 安装/同步依赖  

# 测试  
uv run pytest                                 # 全量测试  
uv run pytest -x -k "test_name"               # 单个测试（失败即停）  
uv run pytest tests/path/to/test_file.py -q   # 指定文件测试  
uv run pytest -k "keyword"                    # 按关键字过滤测试  

# 代码质量  
ruff check .                                  # Lint 检查  
ruff format .                                 # 代码格式化  
mypy app tests                                # 类型检查 
```

## 重要注意事项

- 异常处理必须显式捕获具体异常类型，禁止裸 except
- 字符串、时间、时区、金额、精度相关逻辑必须显式处理，禁止依赖隐式行为
- 修改任何文件前，必须先读取该文件及其调用链上下游；上下文不足时提问，不猜测
- 所有结论必须基于代码、日志、测试结果或运行输出；不基于假设、推测或二手结论
- 未经实际验证的结果，不得标记为"已完成"或"可正常工作"；无法验证时必须标注"未验证"及原因
- 找到根本原因，不做临时修补，按照资深工程师标准实现
- CHANGELOG.md，必须使用中文