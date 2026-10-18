# 架构图存放目录

何时读：修改架构图或核对图表与源码依赖说明。

## 来源与维护边界

图表真源为 [references/architecture.md](../references/architecture.md) 中的 Mermaid 块，本目录保存派生产物。先修改真源再重新生成，不用图片中的连线反向定义源码依赖；完整依赖仍以工程守护和测量为准。

## 产物

| 文件 | 说明 |
|---|---|
| architecture.mmd | 从 architecture.md 提取的 mermaid 源码快照（已含 `drift` 节点与 `WF --> DRIFT`、`DRIFT --> DOMAIN` 两条连线） |
| architecture.svg | **待重新生成**：仍是旧版（不含 drift 节点），与新 mmd 不一致；重新渲染前不要用它判断模块 |
| puppeteer.json | mermaid-cli 的浏览器沙箱配置，供可正常渲染的机器复用 |

## 更新流程

在仓库根目录操作：

1. 修改 references/architecture.md 中的 Mermaid 块；只有说明文字变化时无需重绘。块首的 `%%` 注释说明 SVG 是否待重新生成，改图时一并维护。
2. 重新提取源码快照（与 README 的 Mermaid 块保持逐字一致）：

   ```bash
   # POSIX
   sed -n '/```mermaid/,/```$/p' references/architecture.md | sed '1d;$d' > docs/architecture.mmd
   ```

   ```powershell
   # Windows PowerShell
   $t = Get-Content -Raw -Encoding utf8 references/architecture.md
   $src = [regex]::Match($t, '(?s)```mermaid\n(.*?)```').Groups[1].Value.Trim()
   Set-Content -Encoding utf8 -NoNewline docs/architecture.mmd $src
   ```

3. 同步更新 README.md 里的同一块 Mermaid（`tests/test_runtime.py` 会断言三者一致），再更新 architecture.svg 的节点与连线。优先尝试自动渲染（本机曾长时间挂起，勿无限等待）：

   ```bash
   npx -y @mermaid-js/mermaid-cli -p docs/puppeteer.json -i docs/architecture.mmd -o docs/architecture.svg
   ```

   自动渲染不可用时可从同一源码通过 Graphviz 渲染，或手工排版更新 SVG；节点与连线必须与 mmd 一致。完成渲染后删掉 mmd 块首那句"svg 待重新生成"的注释，并同步改 references/architecture.md 与 README.md。

## 核对与交付

真源、mmd 快照、README 中的 Mermaid 块保持一致；SVG 的节点与连线对应同一版本。`tests/test_runtime.py` 中的架构图守护验证源码快照和 README 一致性；`tests/test_architecture.py` 核对两件事：**画出来的每条边**都必须在依赖白名单内（新增的 `workflow → drift` 依赖已声明的边），**每个画出来的节点**都必须解析到真实模块或已声明的聚合组（例如"纯领域规则"）。图是**摘要**而非白名单的完整投影：它不画出全部允许边，因此白名单新增一条边不会要求重绘图；反过来，图里多一条边或写错一个模块名都会当场失败。工程验证入口见 [验证](../references/validation.md)。

新增其他图表时按 `名称.mmd + 名称.svg` 成对存放，源码块仍在对应 references 文档中维护。
