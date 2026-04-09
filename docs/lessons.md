# Lessons Learned

## [2026-04-10] CI 因 ruff format 失败（v0.3.0~v0.5.0）
- **错误做法**：子代理实施时只运行 `ruff check`（lint），未运行 `ruff format --check`（格式）
- **正确做法**：每次提交前必须运行 `ruff check . && ruff format --check .`，两步缺一不可
- **防止规则**：子代理提交前验证步骤必须包含 `uv run ruff format --check .`

## [2026-04-10] fakeredis 需要 lua extra 支持 Lua 脚本
- **错误做法**：使用 `fakeredis>=2.21`，Lock 模块 Lua 脚本测试失败
- **正确做法**：使用 `fakeredis[lua]>=2.21`，安装 lupa 依赖
- **防止规则**：涉及 Lua 脚本的模块测试必须确认 fakeredis[lua] 已安装
