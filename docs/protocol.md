# 通信协议

## 遥测 JSON

`POST /api/v1/telemetry`

```json
{
  "device_id": "HP-A01",
  "timestamp": 1789958400.0,
  "sequence": 1204,
  "core_temp_c": 36.4,
  "surface_temp_c": 41.2,
  "ambient_temp_c": 5.0,
  "capacitor_soc": 0.73,
  "battery_soc": 0.61,
  "latitude": 30.2762,
  "longitude": 122.318,
  "stationary_seconds": 0,
  "motion_score": 0.71,
  "speed_mps": 0.05,
  "heart_rate_bpm": 74,
  "battery_voltage_v": 1.2,
  "battery_current_a": 0.42
}
```

必填字段为设备、时间、温度、能源、经纬度。新增字段必须可选，旧服务应忽略不理解的可选字段。

## 状态响应

状态响应包含：

- `mode`: `active`、`resting` 或 `unconscious`
- `alert_level`: `normal`、`watch` 或 `sos`
- `control`: 三区占空比、功率、PID 输出和闭锁状态
- `energy`: 电容、电池、混合或预热策略
- `rescue_priority`: 0 至 100
- `event_log`: 最近告警和确认记录
- `history`: 最近 120 个温度与能源采样

## 北斗短报文

参考编码格式：

```text
HP1|HP-A01|30.27620|122.31800|35.8|81|72
```

字段依次为协议版本、设备号、纬度、经度、核心体温、电容 SOC、电池 SOC。实际部署应按北斗卡服务商协议封装，并确认字符集、消息长度、校验和发送序号。当前编码是无外部依赖的参考层。

## 告警状态机

```text
normal --体温下降并连续静止 5 分钟--> unconscious
unconscious --首帧或距离上次 30 秒--> transmit SOS
transmit SOS --救援确认--> acknowledged
acknowledged --模式恢复 active--> normal
surface >= 65C --任意模式--> overheat lockout
overheat lockout --surface <= 55C--> released
```

在真实链路中，救援确认必须带签名或设备身份校验，否则不建议将无认证消息直接用于关闭 SOS。

