# Research Desk SPSS 对照测试方案

## 目的

使用完全合成的数据，对照 Research Desk 与 IBM SPSS Statistics 27.0.1 的统计结果。不得使用真实问卷、个人信息或访谈原文。

## 生成测试文件

在项目根目录执行：

```powershell
& '.\.venv\Scripts\python.exe' scripts\prepare_spss_validation.py
& '.\.venv\Scripts\python.exe' scripts\evaluate_spss_validation.py
```

生成目录：

```text
work/spss_validation/
├─ data/
│  ├─ descriptive.csv
│  ├─ correlation.csv
│  ├─ reliability2.csv
│  └─ reliability3.csv
├─ results/
├─ run_spss_validation.sps
└─ app_expected.json
```

这些文件位于被 Git 忽略的 `work/` 中。

## 数据案例

| 数据 | 覆盖内容 |
|---|---|
| `descriptive.csv` | 缺失值、均值、样本标准差、中位数、Q1/Q3 |
| `correlation.csv` | 成对缺失、并列秩、异常值、Pearson/Spearman |
| `reliability3.csv` | 三题量表、q2 反向、两处缺失、α、标准化 α、CITC、删除题项 α |
| `reliability2.csv` | 两题量表、q2 反向、两题 α 与标准化 α |

## SPSS 执行步骤

1. 打开 IBM SPSS Statistics 27。
2. 打开 `work/spss_validation/run_spss_validation.sps`。
3. 选择 Run All。
4. 检查 `work/spss_validation/results/` 中的 HTML 输出。
5. 对照 `app_expected.json` 和下方候选值填写验收记录。

当前 Codex 沙箱尝试使用 `stats.exe`、`stats.com` 和 SPSS Python 集成自动执行时，被本机 SPSS Java 配置或许可环境阻断。因此自动化执行不是验收前置条件；可以使用 SPSS GUI 执行同一语法。

## 候选值

以下数值来自 Research Desk 当前实现，属于待 SPSS 确认的候选值。

| 指标 | 候选值 |
|---|---:|
| score 均值 | 14.105263157894736 |
| score 样本标准差 | 11.784616794043671 |
| score 中位数 | 10.0 |
| score Q1（linear，待验证） | 4.5 |
| score Q3（linear，待验证） | 21.0 |
| outcome 均值 | 18.31578947368421 |
| outcome 样本标准差 | 21.38548997069157 |
| outcome 中位数 | 13.0 |
| outcome Q1（linear，待验证） | 7.5 |
| outcome Q3（linear，待验证） | 21.5 |
| Pearson n | 18 |
| Pearson r | 0.9476308426653285 |
| Pearson p | 2.412203690952709e-09 |
| Spearman n | 18 |
| Spearman ρ（平均秩） | 0.9891304347826089 |
| Spearman p（双侧 t 近似） | 9.46927604470465e-15 |
| 三题 α | 0.9957498978340825 |
| 三题标准化 α | 0.9958384920171404 |
| 三题完整样本 | 28 |
| q1 CITC | 0.9955099518557585 |
| q1 删除后 α | 0.9903129657228016 |
| q2 CITC | 0.9955099518557585 |
| q2 删除后 α | 0.9903129657228016 |
| q3 CITC | 0.9814277908702377 |
| q3 删除后 α | 1.0 |
| 两题 α | 1.0 |
| 两题标准化 α | 1.0 |
| 两题完整样本 | 30 |

## 误差标准

| 指标 | 通过标准 |
|---|---|
| 有效样本数和缺失数 | 必须完全一致 |
| 均值、样本标准差 | 绝对或相对误差不超过 `1e-6` |
| 中位数、Q1/Q3 | 先确认算法一致，再要求误差不超过 `1e-6` |
| Pearson/Spearman 系数 | 绝对或相对误差不超过 `1e-6` |
| CITC | 绝对误差不超过 `1e-6` |
| 原始 α、标准化 α | 绝对或相对误差不超过 `1e-6` |
| p 值 | 绝对误差不超过 `1e-4`，并比较显著性判断 |

## 失败分类

- 算法差异：四分位数定义、并列秩、p 值近似不同。
- 缺失处理差异：分析样本或缺失声明不同。
- 变量处理差异：反向计分或变量类型不同。
- 真正计算错误：相同数据、样本和算法下仍超出误差标准。

算法差异不得直接忽略。必须记录 SPSS 版本和设置，决定统一算法或在界面明确披露差异。

## 当前结论

- Research Desk 统计函数已有合成数据候选结果。
- SPSS 27.0.1 已安装，但自动化运行受本机环境阻断。
- 需要人工在 SPSS GUI 中运行语法并保存结果。
- 在对照完成前，四分位数算法和 Spearman p 值仍为 `[待验证]`。
