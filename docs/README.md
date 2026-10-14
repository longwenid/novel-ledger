# 架构图存放目录

存放由 [references/architecture.md](../references/architecture.md) 中 mermaid 代码块派生的架构图产物。本目录只放派生文件，不手工编辑真源。

## 产物

| 文件 | 说明 |
|---|---|
| architecture.mmd | 从 architecture.md 提取的 mermaid 源码快照 |
| architecture.svg | 与 mmd 节点连线一一对应的架构图；当前已由 mermaid-cli 渲染；可在自动渲染不可用时手工维护 |
| puppeteer.json | mermaid-cli 的浏览器沙箱配置，供可正常渲染的机器复用 |

## 更新流程

1. 修改 references/architecture.md 中的 mermaid 块。
2. 重新提取源码快照：

   ```bash
   sed -n '/```mermaid/,/```$/p' references/architecture.md | sed '1d;$d' > docs/architecture.mmd
   ```

3. 同步更新 architecture.svg 的节点与连线。优先尝试自动渲染（本机曾长时间挂起，勿无限等待）：

   ```bash
   npx -y @mermaid-js/mermaid-cli -p docs/puppeteer.json -i docs/architecture.mmd -o docs/architecture.svg
   ```

   自动渲染不可用时手工排版更新 SVG，内容必须与 mmd 完全一致。

新增其他图表时按 `名称.mmd + 名称.svg` 成对存放，源码块仍在对应 references 文档中维护。
