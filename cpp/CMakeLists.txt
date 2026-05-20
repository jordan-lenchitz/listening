cmake_minimum_required(VERSION 3.10)
project(MultiF0Tracker)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(tracker multi_f0_tracker.cpp)

# YottaDB DSP Engine binding
add_executable(ydb_dsp_engine ydb_dsp_binding.cpp)
target_link_libraries(ydb_dsp_engine yottadb)
