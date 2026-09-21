#include "hanpo/core.hpp"

#include <math.h>

namespace hanpo {

namespace {

constexpr uint32_t kMinimumUpdateMs = 15U;
constexpr uint32_t kPreheatDurationMs = 300000U;

float clamp_value(float value, float low, float high) {
    if (value < low) {
        return low;
    }
    if (value > high) {
        return high;
    }
    return value;
}

}  // namespace

ThermalController::ThermalController(const Config& config)
    : config_(config),
      integral_(0.0F),
      previous_error_(0.0F),
      has_previous_error_(false),
      overheat_latched_(false),
      last_update_ms_(0U) {}

void ThermalController::reset() {
    integral_ = 0.0F;
    previous_error_ = 0.0F;
    has_previous_error_ = false;
    overheat_latched_ = false;
    last_update_ms_ = 0U;
}

bool ThermalController::overheat_latched() const {
    return overheat_latched_;
}

float ThermalController::clamp(float value, float low, float high) const {
    return clamp_value(value, low, high);
}

ControlOutput ThermalController::update(const SensorFrame& frame, WearerMode mode) {
    ControlOutput output;
    output.emergency = mode == WearerMode::Unconscious;

    if (frame.hardware_overheat || frame.surface_temp_c >= config_.overheat_cutoff_c) {
        overheat_latched_ = true;
        integral_ = 0.0F;
        has_previous_error_ = false;
    } else if (
        overheat_latched_ &&
        frame.surface_temp_c <= config_.overheat_resume_c
    ) {
        overheat_latched_ = false;
    }

    if (overheat_latched_) {
        output.overheat_latched = true;
        output.heater_enabled = false;
        return output;
    }

    uint32_t elapsed_ms = kMinimumUpdateMs;
    if (last_update_ms_ != 0U && frame.timestamp_ms > last_update_ms_) {
        elapsed_ms = frame.timestamp_ms - last_update_ms_;
        if (elapsed_ms < kMinimumUpdateMs) {
            elapsed_ms = kMinimumUpdateMs;
        }
    }
    last_update_ms_ = frame.timestamp_ms;

    const float error = config_.target_core_temp_c - frame.core_temp_c;
    const float dt_seconds = static_cast<float>(elapsed_ms) / 1000.0F;
    const float absolute_error = fabsf(error);

    float kp = 1.7F;
    float ki = 0.14F;
    float kd = 0.55F;
    if (absolute_error > 2.0F) {
        kp = 3.2F;
        ki = 0.02F;
        kd = 0.08F;
    } else if (absolute_error > 0.6F) {
        kp = 2.5F;
        ki = 0.08F;
        kd = 0.30F;
    }

    integral_ = clamp(integral_ + error * dt_seconds, -30.0F, 30.0F);
    float derivative = 0.0F;
    if (has_previous_error_) {
        derivative = (error - previous_error_) / dt_seconds;
    }
    previous_error_ = error;
    has_previous_error_ = true;

    float pid = kp * error + ki * integral_ + kd * derivative;
    pid = clamp(pid, 0.0F, 1.0F);

    float mode_limit = config_.active_duty_limit;
    if (mode == WearerMode::Resting) {
        mode_limit = config_.resting_duty_limit;
    } else if (mode == WearerMode::Unconscious) {
        mode_limit = 1.0F;
    }

    float ambient_boost = 0.0F;
    if (frame.ambient_temp_c <= -30.0F) {
        ambient_boost = 0.20F;
    } else if (frame.ambient_temp_c <= 5.0F) {
        ambient_boost = 0.10F;
    }

    float duty = pid + ambient_boost;
    if (duty > mode_limit) {
        duty = mode_limit;
    }
    if (mode == WearerMode::Unconscious) {
        duty = 1.0F;
    }

    output.pid_output = pid;
    output.zones.chest = duty * config_.chest_ratio;
    output.zones.back = duty * config_.back_ratio;
    output.zones.waist = duty * config_.waist_ratio;
    output.power_w = output.zones.total() * config_.zone_power_w;
    output.heater_enabled = output.power_w > 0.001F;
    return output;
}

EnergyPolicy::EnergyPolicy(const Config& config)
    : config_(config), preheat_started_ms_(0U), preheating_(false) {}

void EnergyPolicy::reset() {
    preheat_started_ms_ = 0U;
    preheating_ = false;
}

EnergyOutput EnergyPolicy::update(
    const SensorFrame& frame,
    WearerMode mode,
    float requested_power_w,
    uint32_t now_ms
) {
    EnergyOutput output;
    output.power_budget_w = clamp_value(requested_power_w, 0.0F, 25.0F);

    if (frame.ambient_temp_c <= -30.0F) {
        if (!preheating_) {
            preheating_ = true;
            preheat_started_ms_ = now_ms;
        }
        const uint32_t elapsed = now_ms - preheat_started_ms_;
        if (elapsed < kPreheatDurationMs) {
            output.source = EnergySource::Preheat;
            output.preheating = true;
            output.power_budget_w = 2.0F;
            return output;
        }
    } else {
        preheating_ = false;
        preheat_started_ms_ = 0U;
    }

    if (mode == WearerMode::Unconscious) {
        output.source = EnergySource::Hybrid;
        output.power_budget_w = output.power_budget_w < 12.0F ? 12.0F : output.power_budget_w;
        return output;
    }

    if (
        frame.capacitor_soc < config_.capacitor_low_soc &&
        frame.battery_soc > 0.02F
    ) {
        output.source = EnergySource::Battery;
        return output;
    }
    if (frame.capacitor_soc >= config_.capacitor_primary_soc) {
        output.source = EnergySource::Capacitor;
        return output;
    }
    if (frame.battery_soc > 0.02F) {
        output.source = EnergySource::Hybrid;
        return output;
    }

    output.source = EnergySource::Capacitor;
    output.power_budget_w = clamp_value(requested_power_w, 0.0F, 6.0F);
    output.load_shedding = true;
    return output;
}

ModeClassifier::ModeClassifier(float temperature_drop_c_per_min)
    : temperature_drop_c_per_min_(temperature_drop_c_per_min),
      first_timestamp_ms_(0U),
      first_temperature_c_(0.0F),
      initialized_(false) {}

WearerMode ModeClassifier::update(
    const SensorFrame& frame,
    float stationary_seconds,
    float motion_score
) {
    if (!initialized_) {
        initialized_ = true;
        first_timestamp_ms_ = frame.timestamp_ms;
        first_temperature_c_ = frame.core_temp_c;
    }

    const uint32_t elapsed_ms = frame.timestamp_ms - first_timestamp_ms_;
    const float elapsed_minutes = static_cast<float>(elapsed_ms) / 60000.0F;
    const float trend = elapsed_minutes > 0.0F
        ? (frame.core_temp_c - first_temperature_c_) / elapsed_minutes
        : 0.0F;
    const bool low_motion = motion_score < 0.12F;

    if (
        stationary_seconds >= 300.0F &&
        low_motion &&
        trend <= -temperature_drop_c_per_min_
    ) {
        return WearerMode::Unconscious;
    }
    if (stationary_seconds >= 120.0F && low_motion) {
        return WearerMode::Resting;
    }
    return WearerMode::Active;
}

}  // namespace hanpo

