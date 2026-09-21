# 寒破先锋 HanPo Pioneer

面向海上救援与高寒巡护场景的智能温控守护装备开源参考平台。本仓库把硬件说明书中的控制目标拆成可运行、可测试、可替换的软件模块，覆盖装备端温控、双能源管理、北斗定位与短报文告警、AI 搜救服务以及实时监控台。

> 本项目是工程原型与算法参考实现，不是经过适航、医疗或个体防护装备认证的产品。直接用于生命保障场景前，必须完成硬件冗余、故障树分析、EMC、低温、浸水和目标标准型式试验。

## 能运行什么

- 100 Hz 装备控制循环，三区独立 PWM，目标核心体温默认 37 摄氏度。
- 65 摄氏度软件闭锁与 55 摄氏度恢复，可接入外部比较器形成双重断电。
- 活动、静止、昏迷状态判定，连续静止与体温下降双条件触发。
- 柔性超级电容和镁空气电池切换，支持极寒预热与低电量负载卸载。
- 卡尔曼定位滤波、海流与风致漂移预测、A* 救援路径规划。
- 78 字限制下可扩展的北斗短报文编码，30 秒重发与救援确认。
- 浏览器实时控制台，内置五类工况注入和多设备救援优先级排序。

## 系统结构

```text
传感器与执行器
  PT1000 / NTC / MPU6050 / 三区碳纤维发热片
                    |
STM32F411 控制核心
  温控 PID / 过热保护 / 昏迷判定 / 双能源策略
                    |
北斗短报文、4G 或 MQTT 传输
                    |
Python 搜救服务
  定位滤波 / 漂移预测 / A* 路径规划 / 优先级排序
                    |
Web 态势控制台与救援接口
```

更完整的边界和部署关系见 [架构文档](docs/architecture.md)，说明书需求与代码映射见 [需求映射](docs/research-to-code.md)。

## 快速启动

运行环境只需要 Python 3.9 或更高版本，Web 控制台没有前端构建步骤。

```powershell
$env:PYTHONPATH = "src"
python -m hanpo --open-browser
```

默认地址为 `http://127.0.0.1:8080/`。也可以安装为本地命令：

```powershell
python -m pip install -e .
hanpo-demo --open-browser
```

Linux 或 macOS：

```bash
PYTHONPATH=src python -m hanpo --open-browser
```

## 测试

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -v
```

C++ 控制核心：

```bash
cmake -S firmware -B firmware/build
cmake --build firmware/build
ctest --test-dir firmware/build --output-on-failure
firmware/build/hanpo_firmware_sim
```

STM32 固件：

```bash
cd firmware
pio run
```

## 目录结构

```text
apps/dashboard/        无构建依赖的实时态势控制台
firmware/core/         Cortex-M 兼容的 C++17 控制核心
firmware/stm32f411/    STM32F411 参考主循环
src/hanpo/             Python 搜救服务、领域算法和 HTTP API
tests/                 Python 单元测试与接口测试
tools/                 模式分类器与电池 SOH 训练脚本
docs/                  架构、硬件、协议、模型与部署文档
```

## 主要接口

```text
GET  /api/v1/health
GET  /api/v1/devices
GET  /api/v1/devices/{device_id}
GET  /api/v1/devices/{device_id}/drift
GET  /api/v1/rescue/plan?device_id=HP-A01&lat=30.305&lon=122.085
POST /api/v1/telemetry
POST /api/v1/devices/{device_id}/scenario
POST /api/v1/devices/{device_id}/acknowledge
POST /api/v1/simulate/tick
```

遥测 JSON、短报文格式和扩展规则见 [通信协议](docs/protocol.md)。

## 硬件配置基线

| 模块 | 说明书基线 | 当前代码接口 |
| --- | --- | --- |
| 主控 | ARM Cortex-M4F | STM32F411 Black Pill |
| 体温 | CMC/PAA-LMA 水凝胶传感器 | ADC 温标函数，待接入实际标定曲线 |
| 环境 | PT1000 | ADC 通道 `PA5` |
| IMU | MPU6050，100 Hz | I2C1 `PB6/PB7`，保留姿态读取接口 |
| 发热 | 三区碳纤维发热片 | 20 kHz PWM `PA0/PA1/PA2` |
| 功率驱动 | AO3400 MOS | 三路 PWM 加总继电器 `PB0` |
| 定位 | UM220-III N | UART 遥测接入 |
| 短报文 | 北斗三号 RDSS | `ShortMessageCodec` |
| 能源 | BQ76940 管理接口 | 电容、电池和混合策略状态机 |

引脚和电气注意事项见 [硬件集成](docs/hardware.md)。

## AI 模型

运行服务内置确定性的规则回退算法，保证没有模型文件时仍可完整演示。生产环境可将随机森林模式分类器、漂移 LSTM 或 SOH SVM 以 ONNX 形式接入相同接口。

```powershell
python -m pip install -e ".[ml]"
python tools/train_mode_classifier.py --output models/mode_classifier.joblib
python tools/train_soh_svm.py --output models/soh_svm.joblib
```

数据切分、评价指标和模型上线约束见 [模型说明](docs/ai-models.md)。

## Docker

```bash
docker compose up --build
```

访问 `http://127.0.0.1:8080/`。

## 开源协作

提交前请运行 Python 和 C++ 测试，并保持新增协议字段向后兼容。贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题见 [SECURITY.md](SECURITY.md)。

### 发布到 GitHub

安装并登录 GitHub CLI 后，可在仓库根目录执行：

```powershell
.\scripts\publish-github.ps1 -Owner YOUR_GITHUB_USER -Visibility public
```

脚本会创建 `hanpo-pioneer` 公开仓库，把本地 `origin` 指向该仓库并推送 `main` 分支。若同名仓库已存在，则直接配置远端并执行推送。

许可证为 MIT。说明书中的产品指标、材料配方和实验数据用于需求说明，不代表软件仓库已完成对应硬件复现或独立验证。
