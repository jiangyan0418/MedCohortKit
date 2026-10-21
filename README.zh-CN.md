# MedCohortKit

可直接查看的模拟输入、配置及结果见 [examples](examples/README.md)。每次运行请使用新的输出文件夹，已有分析不会被覆盖。首版采用 AI 辅助开发，并进行了数值与流程测试；欢迎独立的方法学核查。

**面向临床队列研究的可复现医学统计工具。**

[English](README.md) · [统计方法](docs/methods.md) · [后续计划](docs/roadmap.md)

MedCohortKit 将明确指定的统计分析整理为基线表、数值结果、HTML 报告和分析记录。首版聚焦临床研究中常见的两组比较、测量一致性 ICC 和多因素线性回归，特别考虑骨科研究中“同一患者贡献双膝”的情况。

**当前版本：v0.1.0，alpha 初始版。** 本项目用于科研分析与教学，尚不是经过临床验证的诊疗工具。代码测试用于核查计算和边界情况，不能代替对研究设计和统计假设的判断。演示数据均为模拟数据。

## 已实现的功能

| 模块 | 实际功能 |
| --- | --- |
| 基线表 | 恰好两组；均值（样本标准差）、中位数［Q1，Q3］、分类变量计数及非缺失分母，明确列出缺失数量 |
| 连续变量比较 | 预先指定 Welch t 检验，输出均值差及 95% CI；或指定 Mann–Whitney U 检验，输出秩二列相关效应量 |
| 分类变量比较 | 二分类使用双侧 Fisher 精确检验；多分类只有各格期望频数均至少为 5 时才进行 Pearson 卡方检验 |
| 多重比较 | Benjamini–Hochberg；也可选择 Benjamini–Yekutieli 或明确不校正 |
| 连续结局回归 | 完整案例 OLS；独立数据采用 HC3 标准误，同一患者重复出现时采用患者聚类稳健标准误 |
| 测量一致性 | ICC(A,1)、ICC(A,k)；按受试对象整行重抽样的百分位 bootstrap 区间 |
| 结果输出 | 本地 HTML 报告、CSV 数值表、回归系数图、JSON 分析记录 |

命令行分析必须提供患者/受试者标识列。如果数据中同一患者重复出现，而配置要求独立样本检验，程序会停止并说明原因。描述性表格仍按观察行统计；回归可对患者内相关性进行不确定性调整。

## 安装与运行

需要 **Python 3.10 或更高版本**。以下从项目源代码安装，不假定已经发布到 PyPI。

### Windows PowerShell

```powershell
git clone https://github.com/jiangyan0418/MedCohortKit.git
cd MedCohortKit
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m medcohortkit demo --out output/demo
```

如果没有 Git，可在仓库页面选择 **Code → Download ZIP**，解压后进入包含 `pyproject.toml` 的文件夹，在该文件夹打开 PowerShell，从 `py -m venv .venv` 开始执行。以上命令直接调用虚拟环境中的 Python，不需要修改 PowerShell 执行策略。

演示命令会生成模拟数据和配置，并分别运行独立观察数据、患者聚类数据的示例。在 `output/demo` 中找到生成的 `report.html`，用浏览器打开即可查看。统计运行不需要 API 密钥，也不会调用模型/API。

如需读取 `.xlsx`：

```powershell
.\.venv\Scripts\python.exe -m pip install ".[excel]"
```

### macOS / Linux

```bash
git clone https://github.com/jiangyan0418/MedCohortKit.git
cd MedCohortKit
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m medcohortkit demo --out output/demo
```

## 分析自己的数据

每行表示一次观察，列为变量。**同一患者的左右膝应保留相同的 `patient_id`**；可以另设 `knee_id` 区分左右膝，不能用不同膝 ID 替代患者 ID 来规避相关性。数值列不要混入 `未知` 等文字；缺失值应明确编码。

先生成配置模板：

```powershell
.\.venv\Scripts\python.exe -m medcohortkit template --out analysis.json
```

根据数据的实际列名修改 `analysis.json`。下面是一个示例：

```json
{
  "title": "Clinical cohort analysis",
  "subject_id": "patient_id",
  "group": "group",
  "group_order": ["A", "B"],
  "continuous": ["age", "bmi", "oks_pre", "oks_post"],
  "categorical": ["sex"],
  "comparisons": {
    "enabled": false,
    "continuous_test": "welch",
    "adjust_method": "fdr_bh"
  },
  "linear": {
    "outcome": "oks_post",
    "predictors": ["oks_pre", "age", "bmi", "group"],
    "categorical": ["group"]
  }
}
```

示例中的 `oks_pre` 和 `oks_post` 分别代表术前与术后 Oxford 膝关节评分；也可换为研究实际使用的连续结局。`group_order` 的顺序为参考组、比较组，标签及数据类型必须与文件相符。

组间检验默认关闭。只有在研究设计支持独立两组比较、且分析方案已确定时，才将 `enabled` 改为 `true`。`continuous_test` 可设为 `welch` 或 `mannwhitney`；程序不会根据正态性检验结果自动挑选检验。

```powershell
.\.venv\Scripts\python.exe -m medcohortkit analyze --data cohort.csv --config analysis.json --out output/analysis
```

激活虚拟环境后，也可使用简写入口 `medcohort analyze ...`。如需一致性分析，可在适合独立对象的测量数据配置中增加 `icc` 模块；具体见[统计方法](docs/methods.md#measurement-reliability)。

## 结果怎么看

| 文件 | 内容 |
| --- | --- |
| `report.html` | 浏览器打开的分析报告，包含表格、结果与方法说明 |
| `table1.csv` | 基线描述，含每项变量的非缺失样本量与缺失数量 |
| `comparisons.csv` | 开启组间检验后输出：效应量、方向、CI、原始及校正后 p 值 |
| `regression.csv` | 开启回归后输出：系数、标准误、95% CI、p 值 |
| `forest.svg` | 回归系数及区间图 |
| `icc.csv` | 开启 ICC 后输出：单次测量与均值测量的一致性及区间 |
| `audit.json` | 本次配置及分析元数据，便于追溯方法选择 |

连续变量 Welch 比较的效应方向为 **第二组均值－第一组均值**。Fisher 分析的效应为第二组相对第一组的条件优势比，事件类别会写入结果说明。缺少检验结果时，应阅读 `notes`；程序不会用一个看似完整但不适合的数据结果替代它。

## 需要了解的统计边界

- 基线表按观察行计数，不能把膝数直接称为患者数。
- 聚类稳健标准误调整的是不确定性；回归仍按每行等权拟合，双膝患者会贡献两行权重。它不是混合效应模型，也不能解决混杂。
- ICC(A,1) 反映单个评估者的单次测量，ICC(A,k) 反映所列 k 位评估者平均测量。应按研究实际使用的测量方式解释。
- ICC 区间固定当前评估者，仅重抽样受试对象，不能当作推广到其他随机评估者的解析 F 区间。双膝改成不同 ID 不会让它们变成独立对象。
- 缺失值按相应分析规则排除并计数，首版没有插补，也不自动校正缺失造成的偏倚。
- 首版不支持配对检验、生存分析、Logistic 回归或混合效应模型；不自动选协变量，不作诊断或临床决策。

方法、公式和原始资料见 [docs/methods.md](docs/methods.md)。AI 双语解释层目前仅列入[后续计划](docs/roadmap.md)，尚未接入。

## Python 调用

```python
import pandas as pd
from medcohortkit import table_one, fit_linear

data = pd.read_csv("cohort.csv")
table = table_one(data, "group", ["age", "bmi"], ["sex"], ["A", "B"])
model = fit_linear(
    data, outcome="oks_post", predictors=["oks_pre", "age", "group"],
    categorical=["group"], subject_col="patient_id"
)
print(model["coefficients"])
print(model["metadata"])
```

Python API 的 `subject_col` 可选，但只要数据可能来自同一患者，就应提供该列。不提供时，软件无法核查重复患者。命令行则强制要求 `subject_id`。

## 开发与贡献

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试覆盖数值参照、效应方向、缺失值、重复患者、退化输入与 ICC 随机种子的可复现性。提交问题和改进方法见 [CONTRIBUTING.md](CONTRIBUTING.md)。公开仓库只提交模拟示例，不提交真实患者数据、密钥或未经检查的分析输出。

## 开源许可

采用 MIT 许可，详见 [LICENSE](LICENSE)。依赖库遵循各自许可。项目地址：[jiangyan0418/MedCohortKit](https://github.com/jiangyan0418/MedCohortKit)。
