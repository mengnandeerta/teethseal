# 准二维梳齿密封计算程序 v2

这是一个面向工程快速设计的准二维梳齿密封泄漏计算程序。v2 在 v1 空气理想气体模型基础上，增加了基于 CoolProp 的真实气体物性计算，可用于超临界二氧化碳工况的工程估算。

```text
入口 -> 齿顶节流_1 -> 腔室耗散_1 -> 齿顶节流_2 -> ... -> 出口
```

程序用外层质量流量二分迭代匹配出口压力，并输出总泄漏量、最大马赫数、临界流齿位、逐齿压力分布和诊断提示。

## 快速运行

在本目录执行：

```powershell
python -m q2d_labyrinth.cli examples/sco2_5teeth.json --out outputs/sco2_5teeth
```

输出文件：

- `summary.json`：总结果
- `teeth.csv`：逐齿结果
- `report.md`：简要工程报告
- `geometry_pressure.png`：梳齿几何剖面和对应压力标注
- `geometry.csv`：最终用于计算的逐齿几何参数，自适应几何会写在这里

## 输入文件

见 [examples/sco2_5teeth.json](examples/sco2_5teeth.json)。主要字段：

- `geometry`：齿数、直径、间隙、齿宽、齿高、腔长、腔高
- `boundary`：入口压力温度、出口目标压力
- `coefficients`：齿顶流量系数、突扩/突缩损失、腔室动能携带系数、压力恢复系数
- `solver`：压力收敛容差、最大迭代次数

真实 CO2 工况使用：

```json
"fluid": {
  "type": "coolprop",
  "name": "CO2",
  "backend": "HEOS"
}
```

程序会调用 CoolProp 查询 `p-T`、`p-h`、`p-s` 状态下的密度、焓、熵、黏度和声速。齿顶节流采用等熵焓降搜索质量通量峰值来判断临界流，比固定 `gamma` 的理想气体公式更适合超临界 CO2。

## 自适应逐齿几何

v2 支持让每个齿使用不同的 `clearance`、`cavity_length` 等几何参数。输入文件可以直接写：

```json
"geometry": {
  "tooth_count": 2,
  "diameter": 0.08,
  "clearance": 0.00015,
  "tooth_width": 0.001,
  "tooth_height": 0.0015,
  "cavity_length": 0.003,
  "cavity_height": 0.0015,
  "teeth": [
    {"clearance": 0.00015, "tooth_width": 0.001, "tooth_height": 0.0015, "cavity_length": 0.003, "cavity_height": 0.0015},
    {"clearance": 0.00012, "tooth_width": 0.001, "tooth_height": 0.0015, "cavity_length": 0.004, "cavity_height": 0.0015}
  ]
}
```

也可以开启自动生成：

```json
"adaptive_geometry": {
  "enabled": true,
  "iterations": 1,
  "min_clearance": 0.00010,
  "max_clearance": 0.00016,
  "min_cavity_length": 0.0025,
  "max_cavity_length": 0.0048
}
```

自动生成器会先用基准几何计算一次沿程状态，然后按局部密度下降和两相风险逐步收紧下游间隙、加长下游腔室。示例见 [examples/design_d80_sco2_80c_adaptive.json](examples/design_d80_sco2_80c_adaptive.json)。

## 适用边界

本版用于方案筛选和工程估算，不替代高保真 CFD。默认假设：

1. 支持空气理想气体和 CoolProp 真实气体 CO2。
2. 每个齿顶按一维可压缩孔口/等熵喷放计算。
3. 腔室二维流动影响以 `theta_carryover`、`eta_recovery` 和局部损失系数表示。
4. 不考虑转子旋转、偏心和换热。

若诊断提示系数外推、马赫数接近 1、进入两相区或末级压降占比过高，建议用 OpenFOAM/实验数据校准系数后再用于定型设计。
