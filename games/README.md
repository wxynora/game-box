# games

每个小游戏一个子目录。

建议结构：

```text
games/example-game/
  README.md
  manifest.json
  engine.py
  tests/
  adapters/
  frontend/
```

最小要求：

- 规则引擎能脱离私有后端运行。
- 状态存储路径可配置。
- 玩家视角文本和 AI/工具视角文本分开。
- 不提交私有 token、账号、聊天记录或部署配置。
