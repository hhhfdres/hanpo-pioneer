#include <Arduino.h>
#include <IWatchdog.h>

#include "hanpo/core.hpp"

namespace {

constexpr uint8_t kPwmChest = PA0;
constexpr uint8_t kPwmBack = PA1;
constexpr uint8_t kPwmWaist = PA2;
constexpr uint8_t kAdcSurfaceTemp = PA3;
constexpr uint8_t kAdcCoreTemp = PA4;
constexpr uint8_t kAdcAmbientTemp = PA5;
constexpr uint8_t kHeaterEnable = PB0;
constexpr uint8_t kHardwareOverheat = PB1;
constexpr uint8_t kStatusLed = PC13;

constexpr uint32_t kControlPeriodMs = 10U;
constexpr uint32_t kTelemetryPeriodMs = 1000U;
constexpr uint32_t kPwmFrequencyHz = 20000U;
constexpr float kAdcReference = 3.3F;

hanpo::ThermalController controller;
hanpo::EnergyPolicy energy_policy;
hanpo::ModeClassifier mode_classifier;
hanpo::WearerMode current_mode = hanpo::WearerMode::Active;

uint32_t last_control_ms = 0U;
uint32_t last_telemetry_ms = 0U;
float stationary_seconds = 0.0F;
float motion_score = 1.0F;

float adcToVoltage(uint8_t pin) {
    return static_cast<float>(analogRead(pin)) * kAdcReference / 4095.0F;
}

float readCoreTemperature() {
    const float voltage = adcToVoltage(kAdcCoreTemp);
    return 25.0F + (voltage - 0.5F) * 100.0F;
}

float readSurfaceTemperature() {
    const float voltage = adcToVoltage(kAdcSurfaceTemp);
    return 25.0F + (voltage - 0.5F) * 100.0F;
}

float readAmbientTemperature() {
    const float voltage = adcToVoltage(kAdcAmbientTemp);
    return (voltage - 0.5F) * 100.0F;
}

uint8_t dutyToPwm(float duty) {
    duty = constrain(duty, 0.0F, 1.0F);
    return static_cast<uint8_t>(duty * 255.0F);
}

void applyOutputs(const hanpo::ControlOutput& output) {
    const bool hardware_allows_heat = digitalRead(kHardwareOverheat) == LOW;
    const bool safe_to_heat = output.heater_enabled && hardware_allows_heat;
    digitalWrite(kHeaterEnable, safe_to_heat ? HIGH : LOW);
    analogWrite(kPwmChest, safe_to_heat ? dutyToPwm(output.zones.chest) : 0U);
    analogWrite(kPwmBack, safe_to_heat ? dutyToPwm(output.zones.back) : 0U);
    analogWrite(kPwmWaist, safe_to_heat ? dutyToPwm(output.zones.waist) : 0U);
    digitalWrite(kStatusLed, output.emergency ? LOW : HIGH);
}

void transmitTelemetry(const hanpo::SensorFrame& frame, const hanpo::ControlOutput& output) {
    Serial.print("HP1|");
    Serial.print(frame.timestamp_ms);
    Serial.print('|');
    Serial.print(frame.core_temp_c, 2);
    Serial.print('|');
    Serial.print(frame.surface_temp_c, 2);
    Serial.print('|');
    Serial.print(frame.ambient_temp_c, 2);
    Serial.print('|');
    Serial.print(output.power_w, 2);
    Serial.print('|');
    Serial.println(static_cast<int>(current_mode));
}

void readMotion(float& new_stationary_seconds, float& new_motion_score) {
    // Read the MPU6050 at 0x68 over I2C1 (PB6/PB7) in the production build.
    // This reference loop keeps the interface explicit until the sensor driver
    // is supplied by the board integration package.
    new_stationary_seconds = stationary_seconds;
    new_motion_score = motion_score;
}

}  // namespace

void setup() {
    pinMode(kHeaterEnable, OUTPUT);
    pinMode(kPwmChest, OUTPUT);
    pinMode(kPwmBack, OUTPUT);
    pinMode(kPwmWaist, OUTPUT);
    pinMode(kHardwareOverheat, INPUT_PULLUP);
    pinMode(kStatusLed, OUTPUT);
    digitalWrite(kHeaterEnable, LOW);
    digitalWrite(kStatusLed, HIGH);

    analogReadResolution(12);
    analogWriteFrequency(kPwmFrequencyHz);
    Serial.begin(115200);
    IWatchdog.begin(2000000U);
}

void loop() {
    const uint32_t now = millis();
    if (now - last_control_ms >= kControlPeriodMs) {
        last_control_ms = now;
        readMotion(stationary_seconds, motion_score);

        hanpo::SensorFrame frame;
        frame.timestamp_ms = now;
        frame.core_temp_c = readCoreTemperature();
        frame.surface_temp_c = readSurfaceTemperature();
        frame.ambient_temp_c = readAmbientTemperature();
        frame.capacitor_soc = 0.8F;
        frame.battery_soc = 0.7F;
        frame.hardware_overheat = digitalRead(kHardwareOverheat) == HIGH;

        current_mode = mode_classifier.update(frame, stationary_seconds, motion_score);
        const hanpo::ControlOutput output = controller.update(frame, current_mode);
        const hanpo::EnergyOutput allocation = energy_policy.update(
            frame,
            current_mode,
            output.power_w,
            now
        );
        applyOutputs(output);

        if (now - last_telemetry_ms >= kTelemetryPeriodMs) {
            last_telemetry_ms = now;
            transmitTelemetry(frame, output);
        }

        if (allocation.load_shedding) {
            digitalWrite(kStatusLed, (now / 200U) % 2U == 0U ? LOW : HIGH);
        }
        IWatchdog.reload();
    }
}

