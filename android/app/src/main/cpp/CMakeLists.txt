cmake_minimum_required(VERSION 3.22.1)
project(transcribe_android LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
# Debug APKs are used for phone testing. Keep symbols, but optimize the
# on-device inference code; the default unoptimized CMake Debug build makes
# even a short voice note take minutes on a Pixel 7.
set(CMAKE_C_FLAGS_DEBUG "${CMAKE_C_FLAGS_DEBUG} -O3")
set(CMAKE_CXX_FLAGS_DEBUG "${CMAKE_CXX_FLAGS_DEBUG} -O3")
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_IS_DEV OFF CACHE BOOL "" FORCE)
set(GGML_NATIVE OFF CACHE BOOL "" FORCE)

include(FetchContent)
FetchContent_Declare(
    whispercpp
    GIT_REPOSITORY https://github.com/ggml-org/whisper.cpp.git
    GIT_TAG 927cfce34f31707e17f2bff35c349632fb9e2c3a
)
FetchContent_MakeAvailable(whispercpp)

add_library(transcribe_native SHARED native-lib.cpp)
target_include_directories(transcribe_native PRIVATE ${whispercpp_SOURCE_DIR}/include)
target_link_libraries(transcribe_native PRIVATE whisper log)
