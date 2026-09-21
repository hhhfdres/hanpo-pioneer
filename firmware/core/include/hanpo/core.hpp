#pragma once

#include <stdint.h>

namespace hanpo {

enum class WearerMode : uint8_t {
    Active = 0,
    Resting = 1,
    Unconscious = 2,
};

enum class EnergySource : uint8_t {
    Capacitor = 0,
    Battery = 1,
    Hybrid = 2,
    Preheat = 3,
};

struct Config {
    float target_core_temp_c = 37.0F;
    float overheat_cutoff_c = 65.0F;
    float overheat_resume_c = 55.0F;
    float active_duty_limit = 0.35F;
    float resting_duty_limit = 0.55F;
    float chest_ratio = 0.42F;
    float back_ratio = 0.38F;
    float waist_ratio = 0.20F;
    float zone_power_w = 8.34F;
    float capacitor_low_soc = 0.20F;
    float capacitor_primary_soc = 0.30F;
};

struct SensorFrame {
    uint32_t timestamp_ms = 0;
    float core_temp_c = 37.0F;
    float surface_temp_c = 37.0F;
    float ambient_temp_c = 20.0F;
    float capacitor_soc = 1.0F;
    float battery_soc = 1.0F;
    bool hardware_overheat = false;
};

struct ZoneDuty {
    float chest = 0.0F;
    float back = 0.0F;
    float waist = 0.0F;

    float total() const {
        return chest + back + waist;
    }
};

struct ControlOutput {
    ZoneDuty zones;
    float power_w = 0.0F;
    float pid_output = 0.0F;
    bool heater_enabled = false;
    bool overheat_latched = false;
    bool emergency = false;
    bool watchdog_service_required = false;
};

struct EnergyOutput {
    EnergySource source = EnergySource::Capacitor;
    float power_budget_w = 0.0F;
    bool preheating = false;
    bool load_shedding = false;
};

class ThermalController {
public:
    explicit ThermalController(const Config& config = Config());

    void reset();
    ControlOutput update(const SensorFrame& frame, WearerMode mode);
    bool overheat_latched() const;

private:
    float clamp(float value, float low, float high) const;

    Config config_;
    float integral_;
    float previous_error_;
    bool has_previous_error_;
    bool overheat_latched_;
    uint32_t last_update_ms_;
};

class EnergyPolicy {
public:
    explicit EnergyPolicy(const Config& config = Config());

    EnergyOutput update(
        const SensorFrame& frame,
        WearerMode mode,
        float requested_power_w,
        uint32_t now_ms
    );

    void reset();

private:
    Config config_;
    uint32_t preheat_started_ms_;
    bool preheating_;
};

class ModeClassifier {
public:
    explicit ModeClassifier(float temperature_drop_c_per_min = 0.10F);

    WearerMode update(
        const SensorFrame& frame,
        float stationary_seconds,
        float motion_score
    );

private:
    float temperature_drop_c_per_min_;
    uint32_t first_timestamp_ms_;
    float first_temperature_c_;
    bool initialized_;
};

}  // namespace hanpo

