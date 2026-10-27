# 架构图存放目录

何时读：修改架构图或核对图表与源码依赖说明。

## 来源与维护边界

图表真源为 [references/architecture.md](../references/architecture.md) 中的 Mermaid 块，本目录只保存 **Mermaid 源码快照**，不保存渲染件（PNG/SVG）。先修改真源再重新提取快照，不用图片里的连线反向定义源码依赖；完整依赖仍以工程守护和测量为准。

## 产物

| 文件 | 说明 |
|---|---|
| architecture.mmd | 从 architecture.md 提取的 Mermaid 源码快照（含 `drift` 节点与 `WF --> DRIFT`、`DRIFT --> DOMAIN` 两条连线） |

渲染件按需导出，仓库只保存可与真源逐字核对的 Mermaid 源码快照。

## 更新流程

在仓库根目录操作：

1. 修改 references/architecture.md 中的 Mermaid 块。
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

3. 同步更新 README.md 里的同一块 Mermaid（`tests/test_runtime.py` 会断言三者一致）。
4. 需要图片时现场渲染，不把结果提交回来；缺少 Chrome 或渲染失败时使用可用的 Mermaid 渲染器：

   ```bash
   npx -y @mermaid-js/mermaid-cli -i docs/architecture.mmd -o /tmp/architecture.svg
   ```

## 核对与交付

真源、mmd 快照、README 中的 Mermaid 块保持一致，且 `docs/` 下不得出现 `.svg` 渲染件。`tests/test_runtime.py` 中的架构图守护验证源码快照和 README 一致性；`tests/test_architecture.py` 核对三件事：**快照必须等于真源块**、**画出来的每条边**都必须在依赖白名单内、**每个画出来的节点**都必须解析到真实模块或已声明的聚合组（例如"纯领域规则"）。图是**摘要**而非白名单的完整投影：它不画出全部允许边，因此白名单新增一条边不会要求重绘图；反过来，图里多一条边或写错一个模块名都会当场失败。工程验证入口见 [验证](../references/validation.md)。

新增其他图表时同样只存 `名称.mmd`，源码块仍在对应 references 文档中维护。
