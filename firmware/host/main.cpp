#include "hanpo/core.hpp"

#include <iomanip>
#include <iostream>

int main() {
    hanpo::Config config;
    hanpo::ThermalController controller(config);
    hanpo::EnergyPolicy energy(config);
    hanpo::SensorFrame frame;
    frame.timestamp_ms = 1000U;
    frame.core_temp_c = 35.8F;
    frame.surface_temp_c = 38.2F;
    frame.ambient_temp_c = -34.0F;
    frame.capacitor_soc = 0.68F;
    frame.battery_soc = 0.51F;

    const hanpo::ControlOutput control =
        controller.update(frame, hanpo::WearerMode::Active);
    const hanpo::EnergyOutput allocation =
        energy.update(frame, hanpo::WearerMode::Active, control.power_w, frame.timestamp_ms);

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "power_w=" << control.power_w
              << " chest=" << control.zones.chest
              << " back=" << control.zones.back
              << " waist=" << control.zones.waist << '\n';
    std::cout << "energy_source=" << static_cast<int>(allocation.source)
              << " preheating=" << (allocation.preheating ? "true" : "false") << '\n';
    return 0;
}

