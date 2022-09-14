#!/usr/bin/env bash

# GPU_ARCHS numbers
# Multiple SMs: -DGPU_ARCHS="80 75"
# NVidia A100:80
# Tesla T4:75
# GeForce RTX 2080:75
# Titan V:70
# Tesla V100:70
#
# default when unset:
# 53
# 60
# 61
# 70
# 75
#
# xavier:
# 72


set -euxo pipefail

TRT_DIR=/opt/nvidia/tensorrt
DGPU_ARCHS="53 60 61 70 75"
CUDA_VERSION=11.1
TRT_OSS_CHECKOUT_TAG=release/8.2

function deviceQuery() {
    pushd /tmp
    echo '
    #include <cuda_runtime.h>
    #include <iostream>
    #include <memory>
    #include <string>

    int main(void)
    {
      int deviceCount = 0;
      cudaError_t error_id = cudaGetDeviceCount(&deviceCount);

      if (error_id != cudaSuccess) {
        printf("cudaGetDeviceCount returned %d\n-> %s\n",
               static_cast<int>(error_id), cudaGetErrorString(error_id));
        printf("Result = FAIL\n");
        exit(EXIT_FAILURE);
      }

      // This function call returns 0 if there are no CUDA capable devices.
      if (deviceCount == 0) {
        printf("There are no available device(s) that support CUDA\n");
        exit(EXIT_FAILURE);
      }

      int dev, driverVersion = 0, runtimeVersion = 0;

      for (dev = 0; dev < deviceCount; ++dev) {
        cudaSetDevice(dev);
        cudaDeviceProp deviceProp;
        cudaGetDeviceProperties(&deviceProp, dev);

        printf("\n=== Device %d === \n\n", dev);
        printf("DEVICE_NAME \"%s\"\n", deviceProp.name);

        // Console log
        cudaDriverGetVersion(&driverVersion);
        cudaRuntimeGetVersion(&runtimeVersion);
        printf(
          "CUDA_DRIVER %d.%d\n",
          driverVersion / 1000, (driverVersion % 100) / 10
        );
        printf(
          "CUDA_VERSION %d.%d\n",
          runtimeVersion / 1000, (runtimeVersion % 100) / 10
        );
        printf(
          "DGPU_ARCHS %d%d\n",
          deviceProp.major, deviceProp.minor
        );
        printf("\n=== Device %d === \n");
      }

      return 0;
    }
    ' > deviceQuery.cpp

    nvcc deviceQuery.cpp -o deviceQuery &> /tmp/nvcc-log || cat /tmp/nvcc-log
    ./deviceQuery

    popd
}

function build-nvinfer() {
  mkdir -p $TRT_DIR
  pushd $TRT_DIR
  git clone -b $TRT_OSS_CHECKOUT_TAG https://github.com/nvidia/TensorRT \
    && cd TensorRT/ \
    && git submodule update --init --recursive \
    && export TRT_SOURCE=`pwd` \
    && cd $TRT_SOURCE \
    && mkdir -p build \
    && cd build \
    && cmake \
      .. \
      -DTRT_LIB_DIR=/usr/lib/x86_64-linux-gnu/ \
      -DCMAKE_C_COMPILER=/usr/bin/gcc \
      -DTRT_BIN_DIR=`pwd`/out \
    && make nvinfer_plugin -j$(nproc)
  popd
}

function patch(){
    pushd $TRT_DIR/TensorRT/build
    mv /usr/lib/x86_64-linux-gnu/libnvinfer_plugin.so.8.2.5 /usr/lib/x86_64-linux-gnu/libnvinfer_plugin.so.8.2.5.bkp
    mv libnvinfer_plugin.so.8.2.3 /usr/lib/x86_64-linux-gnu/libnvinfer_plugin.so.8.2.5
    ldconfig
}
function check(){
    gst-inspect-1.0 nvinfer
}

function expose(){
  mkdir -p /docker-export/
  cp /usr/lib/x86_64-linux-gnu/libnvinfer_plugin.so.8.2.5 /docker-export/
}

function serve(){
  pushd /docker-export/
  python3 -m http.server $1
  popd
}
function parseQuery(){
  set +x
  device_data=$(deviceQuery)
  set +x
  # echo -e "data='''\n$device_data\n'''" 
  DEVICE_NAME=$(echo -e "data='''\n$device_data\n'''" | grep DEVICE_NAME | cut -f 2- -d ' ')
  CUDA_DRIVER=$(echo -e "data='''\n$device_data\n'''" | grep CUDA_DRIVER | cut -f 2- -d ' ')
  CUDA_VERSION=$(echo -e "data='''\n$device_data\n'''" | grep CUDA_VERSION | cut -f 2- -d ' ')
  DGPU_ARCHS="$DGPU_ARCHS $(echo -e "data='''\n$device_data\n'''" | grep DGPU_ARCHS | cut -f 2- -d ' ')"
  
}

parseQuery
check
build-nvinfer
patch
check
expose
