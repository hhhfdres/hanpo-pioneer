# STM32 参考固件

本目录包含两部分：

- `core/`：不依赖 HAL 的 C++17 温控与能源策略，可运行在 ARM Cortex-M4F，也可在主机编译测试。
- `stm32f411/`：基于 PlatformIO + Arduino 的 Black Pill 参考主循环，给出 PWM、ADC、I2C、串口、硬件过热比较器和看门狗接口。

## 主机验证

```bash
cmake -S firmware -B firmware/build
cmake --build firmware/build
ctest --test-dir firmware/build --output-on-failure
firmware/build/hanpo_firmware_sim
```

## STM32 构建

```bash
cd firmware
pio run
pio run -t upload
```

默认目标为 `blackpill_f411ce`。如果量产板使用其他 Cortex-M4F 型号，只需替换 PlatformIO 板卡配置，并保持 `core/` 接口不变。

## 安全边界

参考主循环按 100 Hz 运行软件控制周期。热保护采用软件温度阈值与外部比较器串联，任一通道拉低都能关闭 MOS 驱动。正式产品仍需完成故障树分析、独立看门狗验证、短路测试、单点故障测试以及目标标准的型式试验。

