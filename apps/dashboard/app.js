const state = {
  devices: [],
  selectedId: null,
  plan: null,
  mapBounds: null,
  online: false,
};

const elements = {
  liveDot: document.querySelector("#live-dot"),
  liveLabel: document.querySelector("#live-label"),
  clock: document.querySelector("#clock"),
  fleetCount: document.querySelector("#fleet-count"),
  alertCount: document.querySelector("#alert-count"),
  summaryWatch: document.querySelector("#summary-watch"),
  summaryUnacked: document.querySelector("#summary-unacked"),
  deviceList: document.querySelector("#device-list"),
  deviceTemplate: document.querySelector("#device-template"),
  map: document.querySelector("#map-canvas"),
  trend: document.querySelector("#trend-canvas"),
  coreTemp: document.querySelector("#core-temp"),
  coreTempFoot: document.querySelector("#core-temp-foot"),
  heatPower: document.querySelector("#heat-power"),
  heatMode: document.querySelector("#heat-mode"),
  energySoc: document.querySelector("#energy-soc"),
  energySource: document.querySelector("#energy-source"),
  priorityScore: document.querySelector("#priority-score"),
  priorityFoot: document.querySelector("#priority-foot"),
  selectedName: document.querySelector("#selected-name"),
  selectedId: document.querySelector("#selected-id"),
  selectedState: document.querySelector("#selected-state"),
  detailCore: document.querySelector("#detail-core"),
  detailSurface: document.querySelector("#detail-surface"),
  detailAmbient: document.querySelector("#detail-ambient"),
  detailSource: document.querySelector("#detail-source"),
  detailEnergyReason: document.querySelector("#detail-energy-reason"),
  detailCapSoc: document.querySelector("#detail-cap-soc"),
  detailBatSoc: document.querySelector("#detail-bat-soc"),
  rescueDistance: document.querySelector("#rescue-distance"),
  rescueEta: document.querySelector("#rescue-eta"),
  rescueRationale: document.querySelector("#rescue-rationale"),
  thermalReason: document.querySelector("#thermal-reason"),
  eventList: document.querySelector("#event-list"),
  ackButton: document.querySelector("#ack-button"),
  scenarioButtons: [...document.querySelectorAll("#scenario-buttons button")],
  zones: {
    chest: document.querySelector("#zone-chest"),
    back: document.querySelector("#zone-back"),
    waist: document.querySelector("#zone-waist"),
  },
  zoneValues: {
    chest: document.querySelector("#zone-chest-value"),
    back: document.querySelector("#zone-back-value"),
    waist: document.querySelector("#zone-waist-value"),
  },
};

const modeLabels = {
  active: "正常活动",
  resting: "静止守护",
  unconscious: "昏迷守护",
};

const alertLabels = {
  normal: "状态正常",
  watch: "需要关注",
  sos: "紧急求救",
};

const sourceLabels = {
  capacitor: "柔性超级电容",
  battery: "镁空气电池",
  hybrid: "双能源并联",
  preheat: "电解质预热",
};

const scenarioLabels = {
  normal: "活动",
  resting: "静止",
  unconscious: "昏迷",
  overheat: "过热",
  cold: "极寒",
};

const reasonLabels = {
  "closed-loop heating": "闭环加热",
  "closed-loop heating with cold-ambient compensation": "闭环加热 · 低温补偿",
  "target temperature reached": "已达到目标体温",
  "surface temperature lockout": "表面温度联锁",
  "capacitor SOC below 20 percent": "超电低于 20%",
  "capacitor primary operating range": "超电主供能区",
  "capacitor transition band": "超电过渡区",
  "battery unavailable; load shedding": "电池不可用 · 负载降级",
  "unconscious safeguard uses both sources": "昏迷守护 · 双能源输出",
  "electrolyte preheat cycle": "电解质预热周期",
  "routine recovery route": "常规接应路线",
  "active SOS": "紧急求救",
  "thermal lockout": "热保护闭锁",
  "capacitor below 20%": "超电低于 20%",
};

function localizeReason(value) {
  if (!value) {
    return "--";
  }
  return reasonLabels[value] || value;
}

function formatEvent(value) {
  return value
    .replace("SOS sent: unconscious safeguard", "SOS 已发送：昏迷守护")
    .replace("SOS sent: low body temperature", "SOS 已发送：核心体温过低")
    .replace("Watch: temperature trend", "关注：体温下降趋势")
    .replace("Rescue centre acknowledged", "救援中心已确认");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || `HTTP ${response.status}`);
  }
  return body;
}

function selectedDevice() {
  return state.devices.find((device) => device.telemetry.device_id === state.selectedId) || state.devices[0];
}

function setOnline(online) {
  state.online = online;
  elements.liveDot.classList.toggle("online", online);
  elements.liveDot.classList.toggle("error", !online);
  elements.liveLabel.textContent = online ? "数据链路正常" : "数据链路中断";
}

function updateClock() {
  elements.clock.textContent = new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function renderDeviceList() {
  elements.deviceList.replaceChildren();
  for (const device of state.devices) {
    const node = elements.deviceTemplate.content.firstElementChild.cloneNode(true);
    const temperature = device.telemetry.core_temp_c.toFixed(1);
    const soc = Math.max(device.telemetry.capacitor_soc, device.telemetry.battery_soc) * 100;
    node.classList.add(device.alert_level);
    node.classList.toggle("selected", device.telemetry.device_id === state.selectedId);
    node.querySelector("strong").textContent = device.name;
    node.querySelector("small").textContent = `${device.telemetry.device_id} · ${temperature}℃ · ${soc.toFixed(0)}%`;
    node.querySelector(".device-priority").textContent = device.rescue_priority.toFixed(0);
    node.addEventListener("click", () => {
      state.selectedId = device.telemetry.device_id;
      state.plan = null;
      render();
      loadRescuePlan();
    });
    elements.deviceList.append(node);
  }
}

function setText(node, value) {
  if (node) {
    node.textContent = value;
  }
}

function renderSelected() {
  const device = selectedDevice();
  if (!device) {
    return;
  }
  const { telemetry, control, energy } = device;
  const stateLabel = alertLabels[device.alert_level] || device.alert_level;
  const modeLabel = modeLabels[device.mode] || device.mode;
  const sourceLabel = sourceLabels[energy.source] || energy.source;

  setText(elements.selectedName, device.name);
  setText(elements.selectedId, telemetry.device_id);
  setText(elements.selectedState, stateLabel);
  elements.selectedState.className = `state-pill ${device.alert_level}`;
  setText(elements.detailCore, `${telemetry.core_temp_c.toFixed(1)}℃`);
  setText(elements.detailSurface, `${telemetry.surface_temp_c.toFixed(1)}℃`);
  setText(elements.detailAmbient, `${telemetry.ambient_temp_c.toFixed(1)}℃`);
  setText(elements.detailSource, sourceLabel);
  setText(elements.detailEnergyReason, localizeReason(energy.reason));
  setText(elements.detailCapSoc, `${(telemetry.capacitor_soc * 100).toFixed(0)}%`);
  setText(elements.detailBatSoc, `${(telemetry.battery_soc * 100).toFixed(0)}%`);
  setText(elements.thermalReason, `${modeLabel} · ${localizeReason(control.reason)}`);
  setText(elements.coreTemp, telemetry.core_temp_c.toFixed(1));
  setText(elements.coreTempFoot, `${modeLabel} / ${telemetry.heart_rate_bpm ? `${telemetry.heart_rate_bpm.toFixed(0)} bpm` : "无心率数据"}`);
  setText(elements.heatPower, control.power_w.toFixed(1));
  setText(elements.heatMode, control.overheat_latched ? "过热闭锁" : localizeReason(control.reason));
  const primarySoc = Math.max(telemetry.capacitor_soc, telemetry.battery_soc);
  setText(elements.energySoc, (primarySoc * 100).toFixed(0));
  setText(elements.energySource, sourceLabel);
  setText(elements.priorityScore, device.rescue_priority.toFixed(0));
  setText(elements.priorityFoot, device.alert_acknowledged ? "告警已确认" : "等待救援确认");

  for (const zone of ["chest", "back", "waist"]) {
    const value = Math.max(0, Math.min(1, control.zones[zone]));
    elements.zones[zone].style.width = `${(value * 100).toFixed(1)}%`;
    setText(elements.zoneValues[zone], `${(value * 100).toFixed(0)}%`);
  }

  elements.ackButton.disabled = device.alert_level !== "sos" || device.alert_acknowledged;
  for (const button of elements.scenarioButtons) {
    button.classList.toggle("active", button.dataset.scenario === device.scenario);
  }

  elements.eventList.replaceChildren();
  if (!device.event_log.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "当前无异常事件";
    elements.eventList.append(empty);
  } else {
    for (const text of device.event_log) {
      const item = document.createElement("div");
      item.className = `event-item${/SOS|lockout|Watch/i.test(text) ? " alert" : ""}`;
      item.textContent = formatEvent(text);
      elements.eventList.append(item);
    }
  }

  if (state.plan && state.plan.device_id === telemetry.device_id) {
    setText(elements.rescueDistance, `${(state.plan.distance_m / 1000).toFixed(1)} km`);
    setText(elements.rescueEta, `${state.plan.eta_minutes.toFixed(0)} min`);
    setText(
      elements.rescueRationale,
      state.plan.rationale
        .split(", ")
        .map((part) => localizeReason(part))
        .join(" · "),
    );
  } else {
    setText(elements.rescueDistance, "--");
    setText(elements.rescueEta, "--");
    setText(elements.rescueRationale, "正在计算救援路径");
  }
}

function renderSummary(data) {
  setText(elements.fleetCount, `${data.summary.total} 台在线`);
  setText(elements.alertCount, `${data.summary.sos} SOS`);
  elements.alertCount.classList.toggle("has-alert", data.summary.sos > 0);
  setText(elements.summaryWatch, data.summary.watch);
  setText(elements.summaryUnacked, data.summary.unacknowledged);
}

function canvasContext(canvas) {
  const ratio = Math.max(1, window.devicePixelRatio || 1);
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  const context = canvas.getContext("2d");
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { context, width, height };
}

function calculateBounds() {
  const points = [];
  for (const device of state.devices) {
    points.push([device.telemetry.longitude, device.telemetry.latitude]);
  }
  if (state.plan) {
    points.push([122.085, 30.305]);
    for (const point of state.plan.route || []) {
      points.push([point.longitude, point.latitude]);
    }
  }
  if (!points.length) {
    return { minLon: 122.04, maxLon: 122.4, minLat: 30.14, maxLat: 30.34 };
  }
  const longitudes = points.map((point) => point[0]);
  const latitudes = points.map((point) => point[1]);
  let minLon = Math.min(...longitudes);
  let maxLon = Math.max(...longitudes);
  let minLat = Math.min(...latitudes);
  let maxLat = Math.max(...latitudes);
  const lonPad = Math.max(0.025, (maxLon - minLon) * 0.28);
  const latPad = Math.max(0.018, (maxLat - minLat) * 0.32);
  minLon -= lonPad;
  maxLon += lonPad;
  minLat -= latPad;
  maxLat += latPad;
  return { minLon, maxLon, minLat, maxLat };
}

function project(point, bounds, width, height) {
  const x = ((point[0] - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * width;
  const y = height - ((point[1] - bounds.minLat) / (bounds.maxLat - bounds.minLat)) * height;
  return { x, y };
}

function drawMap() {
  const { context: ctx, width, height } = canvasContext(elements.map);
  const bounds = calculateBounds();
  state.mapBounds = bounds;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#10221f";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(114, 151, 137, 0.16)";
  ctx.lineWidth = 1;
  for (let index = 1; index < 8; index += 1) {
    const x = (width / 8) * index;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }
  for (let index = 1; index < 6; index += 1) {
    const y = (height / 6) * index;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  ctx.fillStyle = "#1e3027";
  ctx.strokeStyle = "#3a5547";
  ctx.beginPath();
  ctx.moveTo(width * 0.74, 0);
  ctx.lineTo(width, 0);
  ctx.lineTo(width, height * 0.31);
  ctx.lineTo(width * 0.88, height * 0.24);
  ctx.lineTo(width * 0.83, height * 0.12);
  ctx.lineTo(width * 0.74, 0);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  if (state.plan && state.plan.route && state.plan.route.length > 1) {
    ctx.strokeStyle = "#d59b3d";
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    state.plan.route.forEach((point, index) => {
      const screen = project([point.longitude, point.latitude], bounds, width, height);
      if (index === 0) {
        ctx.moveTo(screen.x, screen.y);
      } else {
        ctx.lineTo(screen.x, screen.y);
      }
    });
    ctx.stroke();
    ctx.setLineDash([]);
  }

  const selected = selectedDevice();
  for (const device of state.devices) {
    const point = project(
      [device.telemetry.longitude, device.telemetry.latitude],
      bounds,
      width,
      height,
    );
    const isSelected = selected && selected.telemetry.device_id === device.telemetry.device_id;
    const color = device.alert_level === "sos"
      ? "#e15846"
      : device.alert_level === "watch"
        ? "#d59b3d"
        : "#39b8a2";
    if (device.alert_level === "sos") {
      ctx.fillStyle = "rgba(225, 88, 70, 0.16)";
      ctx.beginPath();
      ctx.arc(point.x, point.y, 17, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = color;
    ctx.strokeStyle = isSelected ? "#ffffff" : "#10221f";
    ctx.lineWidth = isSelected ? 3 : 2;
    ctx.beginPath();
    ctx.arc(point.x, point.y, isSelected ? 7 : 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#dce8e0";
    ctx.font = "12px Consolas, monospace";
    ctx.fillText(device.telemetry.device_id, point.x + 11, point.y - 9);
  }

  if (state.plan && state.plan.route && state.plan.route.length) {
    const ship = project([122.085, 30.305], bounds, width, height);
    ctx.fillStyle = "#d59b3d";
    ctx.fillRect(ship.x - 5, ship.y - 5, 10, 10);
    ctx.fillStyle = "#f0d3a3";
    ctx.font = "12px Consolas, monospace";
    ctx.fillText("RESCUE", ship.x + 9, ship.y - 9);
  }
}

function renderTrend() {
  const { context: ctx, width, height } = canvasContext(elements.trend);
  const device = selectedDevice();
  ctx.clearRect(0, 0, width, height);
  if (!device || !device.history || device.history.length < 2) {
    ctx.fillStyle = "#91a097";
    ctx.font = "12px Segoe UI, sans-serif";
    ctx.fillText("正在采集趋势数据", 14, height / 2);
    return;
  }
  const history = device.history.slice(-120);
  const values = history.flatMap((item) => [item.core_temp_c, item.surface_temp_c]);
  let min = Math.min(...values) - 0.5;
  let max = Math.max(...values) + 0.5;
  if (max - min < 3) {
    const center = (max + min) / 2;
    min = center - 1.5;
    max = center + 1.5;
  }
  const left = 38;
  const right = 12;
  const top = 10;
  const bottom = 18;

  ctx.strokeStyle = "#2b362e";
  ctx.fillStyle = "#91a097";
  ctx.font = "10px Consolas, monospace";
  for (let index = 0; index <= 3; index += 1) {
    const y = top + ((height - top - bottom) / 3) * index;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(width - right, y);
    ctx.stroke();
    const label = max - ((max - min) / 3) * index;
    ctx.fillText(`${label.toFixed(0)}°`, 4, y + 3);
  }

  const drawSeries = (key, color) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    history.forEach((item, index) => {
      const x = left + ((width - left - right) * index) / Math.max(1, history.length - 1);
      const y = top + ((max - item[key]) / (max - min)) * (height - top - bottom);
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();
  };
  drawSeries("surface_temp_c", "#6e9fd0");
  drawSeries("core_temp_c", "#e15846");
}

function render() {
  renderDeviceList();
  renderSelected();
  renderTrend();
  drawMap();
}

async function loadRescuePlan() {
  const device = selectedDevice();
  if (!device || !state.online) {
    return;
  }
  try {
    state.plan = await api(`/api/v1/rescue/plan?device_id=${encodeURIComponent(device.telemetry.device_id)}`);
    render();
  } catch (error) {
    state.plan = null;
    setText(elements.rescueRationale, "救援规划暂不可用");
  }
}

async function heartbeat() {
  try {
    const data = await api("/api/v1/simulate/tick", { method: "POST", body: "{}" });
    if (!state.selectedId && data.devices.length) {
      state.selectedId = data.devices[0].telemetry.device_id;
    }
    state.devices = data.devices;
    renderSummary(data);
    setOnline(true);
    render();
    await loadRescuePlan();
  } catch (error) {
    setOnline(false);
  }
}

elements.ackButton.addEventListener("click", async () => {
  const device = selectedDevice();
  if (!device) {
    return;
  }
  try {
    await api(`/api/v1/devices/${device.telemetry.device_id}/acknowledge`, {
      method: "POST",
      body: "{}",
    });
    await heartbeat();
  } catch (error) {
    setOnline(false);
  }
});

for (const button of elements.scenarioButtons) {
  button.addEventListener("click", async () => {
    const device = selectedDevice();
    if (!device) {
      return;
    }
    try {
      await api(`/api/v1/devices/${device.telemetry.device_id}/scenario`, {
        method: "POST",
        body: JSON.stringify({ scenario: button.dataset.scenario }),
      });
      await heartbeat();
    } catch (error) {
      setOnline(false);
    }
  });
}

window.addEventListener("resize", () => {
  drawMap();
  renderTrend();
});

updateClock();
setInterval(updateClock, 1000);
heartbeat();
setInterval(heartbeat, 2000);
