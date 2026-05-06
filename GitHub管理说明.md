# GitHub 管理说明

本目录已经按一个独立 Python 工程整理，可以直接用 Git/GitHub 管理。

## 当前环境情况

当前机器的 PowerShell 里没有找到 `git` 命令，所以本次没有执行本地提交或推送。

如果后续安装 Git，或在 Codex 中启用 GitHub 工具，就可以继续做：

```powershell
cd "E:\01项目资料\07干气密封\01程序\迷宫密封\v2\准二维计算程序"
git init
git add .
git commit -m "Add v2 real-gas sCO2 labyrinth solver"
```

如果已经有 GitHub 仓库：

```powershell
git remote add origin https://github.com/<your-user>/<your-repo>.git
git branch -M main
git push -u origin main
```

## 建议分支策略

- `main`：稳定版本
- `codex/v2-sco2-real-gas`：本次 v2 开发分支
- `codex/calibration`：后续系数标定分支
- `codex/reporting`：后续报告和图表增强分支

## 建议提交粒度

1. `Add v2 project scaffold`
2. `Add CoolProp real-gas CO2 fluid model`
3. `Use real-gas throat search for tooth throttling`
4. `Add sCO2 example case`
5. `Add PNG geometry pressure postprocess`

## 不建议提交的内容

`.gitignore` 已经忽略：

- `outputs/`
- Python 缓存
- 虚拟环境
- 打包生成物

这样 GitHub 仓库里只保留源码、示例输入和说明文档。
