#include "hanpo/core.hpp"

#include <cassert>
#include <cmath>
#include <iostream>

namespace {

bool near(float left, float right, float tolerance = 0.001F) {
    return std::fabs(left - right) <= tolerance;
}

void test_thermal_control() {
    hanpo::Config config;
    hanpo::ThermalController controller(config);
    hanpo::SensorFrame frame;
    frame.timestamp_ms = 1000U;
    frame.core_temp_c = 35.0F;
    frame.surface_temp_c = 38.0F;
    frame.ambient_temp_c = 5.0F;

    const hanpo::ControlOutput output =
        controller.update(frame, hanpo::WearerMode::Active);
    assert(output.heater_enabled);
    assert(output.zones.total() <= config.active_duty_limit + 0.001F);
}

void test_overheat_lockout() {
    hanpo::ThermalController controller;
    hanpo::SensorFrame frame;
    frame.timestamp_ms = 1000U;
    frame.surface_temp_c = 66.0F;
    auto output = controller.update(frame, hanpo::WearerMode::Active);
    assert(output.overheat_latched);
    assert(!output.heater_enabled);

    frame.timestamp_ms = 2000U;
    frame.surface_temp_c = 60.0F;
    output = controller.update(frame, hanpo::WearerMode::Active);
    assert(output.overheat_latched);

    frame.timestamp_ms = 3000U;
    frame.surface_temp_c = 54.0F;
    output = controller.update(frame, hanpo::WearerMode::Active);
    assert(!output.overheat_latched);
}

void test_unconscious_full_duty() {
    hanpo::ThermalController controller;
    hanpo::SensorFrame frame;
    frame.timestamp_ms = 1000U;
    frame.core_temp_c = 35.5F;
    frame.surface_temp_c = 38.0F;
    const auto output = controller.update(frame, hanpo::WearerMode::Unconscious);
    assert(near(output.zones.total(), 1.0F));
    assert(output.emergency);
}

void test_energy_preheat() {
    hanpo::EnergyPolicy policy;
    hanpo::SensorFrame frame;
    frame.ambient_temp_c = -40.0F;
    frame.capacitor_soc = 0.8F;
    frame.battery_soc = 0.7F;
    const auto output =
        policy.update(frame, hanpo::WearerMode::Active, 5.0F, 1000U);
    assert(output.source == hanpo::EnergySource::Preheat);
    assert(output.preheating);
}

void test_mode_classifier() {
    hanpo::ModeClassifier classifier;
    hanpo::SensorFrame first;
    first.timestamp_ms = 0U;
    first.core_temp_c = 36.8F;
    assert(classifier.update(first, 0.0F, 0.02F) == hanpo::WearerMode::Active);

    hanpo::SensorFrame second;
    second.timestamp_ms = 360000U;
    second.core_temp_c = 36.1F;
    assert(
        classifier.update(second, 360.0F, 0.02F) ==
        hanpo::WearerMode::Unconscious
    );
}

}  // namespace

int main() {
    test_thermal_control();
    test_overheat_lockout();
    test_unconscious_full_duty();
    test_energy_preheat();
    test_mode_classifier();
    std::cout << "hanpo core tests passed\n";
    return 0;
}

