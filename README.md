# Research Desk

Research Desk 是一个本地优先的问卷数据分析工作台。当前版本面向个人用户，使用 Streamlit 在 Windows 上运行，基础统计不依赖任何 AI Provider。

## 当前功能

- 导入 CSV 和 XLSX 文件。
- 查看数据预览、缺失值、重复行和常量字段。
- 按字段配置有序、分类、数值等类型，并声明用户指定的缺失代码。
- 声明普通未加权独立观测、复杂抽样或不确定。
- 计算描述性统计。
- 计算 Pearson 和 Spearman 相关，并显示基础散点诊断。
- 计算 Cronbach's α、标准化 α、CITC 和删除题项后的 α。
- 将项目元数据和分析结果保存到本地 SQLite。
- 下载 SQLite 一致性备份，并经二次确认删除项目。
- 使用公式注入防护导出 CSV。
- 显示本地和在线 AI Provider 的状态，并提供 D0-D3 在线边界与授权指纹预检。
- 当前模型 Provider 均未配置，不会发起网络模型请求。

## 环境要求

- Windows 10/11 x64。
- Python 3.14.4。
- 已创建的 `.venv` 虚拟环境。

## 安装依赖

在项目根目录打开 PowerShell：

```powershell
Set-Location 'C:\Users\songc\Documents\Codex\2026-11-07\github-git-git-github-1-2'
python -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install --only-binary=:all: -r requirements.lock
```

如果 `.venv` 已经存在，不要重复执行创建命令。

检查环境：

```powershell
& '.\.venv\Scripts\python.exe' -m pip check
& '.\.venv\Scripts\python.exe' -c "import streamlit,pandas,numpy,scipy,statsmodels,openpyxl; print('imports OK')"
```

## 启动应用

```powershell
& '.\.venv\Scripts\python.exe' -m streamlit run app.py
```

浏览器通常会自动打开 `http://localhost:8501`。

## 数据位置

用户数据默认保存在仓库外：

```text
%LOCALAPPDATA%\ResearchDesk\
```

其中 `research_desk.sqlite3` 只保存项目名称、分析参数和结果等元数据。SQLite 当前不提供应用层加密，安全性依赖 Windows 用户权限和磁盘加密。

原始问卷、个人隐私数据、访谈材料和导出文件不得提交到 Git。项目 `.gitignore` 已覆盖常用敏感目录和文件格式。

## 数据与方法边界

- 相关分析使用成对完整样本。
- 两两样本少于 3 时不显示相关系数。
- 两两样本少于 10 时不显示 p 值，这是产品界面策略，不是统计学定律。
- 复杂抽样或不确定声明会禁用正式总体推断。
- 修改抽样声明、字段类型或分析参数会清除旧结果，避免复用不兼容的 p 值。
- 信度分析使用固定列表完整样本。
- 四分位数算法仍待 SPSS 对照验证。
- AI Provider 当前未配置，不会上传数据或执行文件操作。

详细规则以 `docs/` 下的四份 V0.3 Final 文档为准。

SPSS 对照数据生成与人工验收步骤见 `docs/SPSS_对照测试方案.md`。

## 运行测试

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests -v
```

## 项目结构

```text
app.py
src/research_desk/
│  ├─ analysis.py
│  ├─ ai.py
│  ├─ audit.py
│  ├─ csv_export.py
│  ├─ data_io.py
│  ├─ models.py
│  ├─ security.py
│  └─ storage.py
tests/
docs/
requirements.txt
requirements.lock
```

## 常见问题

### `git` 或 `less` 找不到

项目运行不依赖 Git 分页器。Git 只用于版本管理；查看 diff 时可使用：

```powershell
git --no-pager diff
```

### Streamlit 提示端口被占用

指定其他端口：

```powershell
& '.\.venv\Scripts\python.exe' -m streamlit run app.py --server.port 8502
```

### 内存占用较高

当前电脑的基础环境可能只剩约 2 GB 可用内存。处理较大数据前请关闭不必要的程序，并避免一次导入过大的表格。
