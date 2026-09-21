cmake_minimum_required(VERSION 3.16)
project(hanpo_firmware_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(hanpo_core
    core/src/core.cpp
)

target_include_directories(hanpo_core PUBLIC core/include)
target_compile_options(hanpo_core PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall -Wextra -Wpedantic>
    $<$<CXX_COMPILER_ID:MSVC>:/W4>
)

add_executable(hanpo_firmware_sim host/main.cpp)
target_link_libraries(hanpo_firmware_sim PRIVATE hanpo_core)

enable_testing()
add_executable(hanpo_core_tests tests/test_core.cpp)
target_link_libraries(hanpo_core_tests PRIVATE hanpo_core)
add_test(NAME hanpo_core_tests COMMAND hanpo_core_tests)

