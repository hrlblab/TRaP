# Changelog

## 2026-03-23
- **Renishaw 支持**：Renishaw 系统仍需 Spectral Response Correction（SRC），仅自动跳过 X 轴标定步骤
- **暗背景减除跳过**：Renishaw/显微镜系统跳过最小值暗基线减除（Step 1）
- **FBS 排除区域**：荧光背景拟合支持手动输入排除波数范围（冻结 Raman 峰区域，防止拟合偏移）
- **整数 Binwidth 对齐**：Binwidth 为整数时，网格自动偏移，使 bin 中点落在整数波数上
- **二次截断（Truncate2）**：在归一化前可选第二次截断，支持截取最终关注区域
- **步骤标题显示**：图表标题显示当前步骤编号与名称（`Current: Step N — StepName`）
- **比较线颜色修正**：Before 曲线从灰色改为钢蓝色（`#5B9BD5`），与 After 曲线区分更清晰
- **Renishaw 激光波长扩展**：Config Manager 支持 532 / 633 / 785 / 830 / 1064 nm
- **Batch Process 同步**：上述所有功能同步至 Batch Processing UI

## 2026-03-17
- **修复 DLL 加载错误**：其他机器运行 `TRaP.exe` 时报 `ImportError: DLL load failed while importing QtCore`
  - 添加 PyInstaller runtime hook（`pyi_rthook.py`），在启动时调用 `os.add_dll_directory(sys._MEIPASS)`
  - 显式打包 conda 环境中的 Qt5 DLL 文件（`Qt5*_conda.dll`）

## 2026-03-16
- 清理仓库：移除 IDE 文件、`__pycache__`、文档等无关文件
- 移除跟踪：`project_status.md`、`image.png`、`config.json`
- 更新 README 标题与单位信息
- **修复**：保存配置时非 Renishaw 系统的跳过复选框不再被错误重置
- **Renishaw 自动跳过**：检测到 Renishaw 系统时自动勾选跳过 X 轴标定
- **修复 Renishaw 数据**：波数从降序正确读取
- Config Manager 添加字段校验（加载/保存时）
- 添加 TRaP logo 至导航栏与窗口图标

## 2026-03-15
- 暴露 FBS 最大迭代次数和归一化方式参数
- 全面重构处理 UI 与配置校验逻辑
- 修复标定和 SRCF 对话框的垂直缩放问题
- 修复 SRCF 波长轴、图表 xlim；build 排除 torch 相关模块

## 2026-03-04
- **修复白光校正**：波长公式错误（`1e7/(1e7/λ - wvn)`）及元组解包问题
- **修复 Renishaw 波数轴**：从 0 开始的 X 轴问题（改用 `read_txt_file`）
- 添加交互式光标读数：图表上显示最近数据点的波数和强度

## 2026-02-25
- 修复 Batch 长输出路径处理问题

## 2026-02-23
- Batch 支持子目录输出，改进保存报错信息
- P-Mean 平滑步骤调整至背景减除之后

## 2026-02-20
- 修复 SRCF 输出格式
- 鲁棒文件读取器
- 自适应画布字体
- Build 修复

## 2026-02-19
- 自适应窗口尺寸
- 所有 UI 面板支持滚动

## 2026-02-17
- 重写 README（结构更清晰、内容更简洁）

## 2026-02-16
- 更新 Python 脚本，添加 `.gitignore`

## 2025-12-15
- 多项 UI 与功能更新

## 2025-10-30
- Wizard UI 更新

## 2025-09-29
- UI 更新

## 2025-08-18 — 2025-08-21
- Wizard UI 更新；综合更新

## 2025-07-07 — 2025-07-23
- 白光校正更新；Wizard UI 更新

## 2025-05-22 — 2025-06-24
- 早期开发，功能移除与更新
