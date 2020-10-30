# pythia - Deepstream + Kivy

## Setup

### Prerequisites

* System depdndencies:

  This list includes both build and runtime dependencies (eg to compile kivy).

  <details><summary>[sudo apt install - click to show]</summary>
  <p>

  ```bash
  sudo apt install -y \
    python3-pip \
    build-essential \
    git \
    python3 \
    python3-dev \
    ffmpeg \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libportmidi-dev \
    libswscale-dev \
    libavformat-dev \
    libavcodec-dev \
    zlib1g-dev \
    libgstreamer1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    libcairo2-dev \
    graphviz \
    libgraphviz-dev \
    libjpeg-dev \
    libgif-dev \
    libgirepository1.0-dev \
    libavdevice-dev \
    xclip \
    xsel \
    v4l-utils
  ```

  </p>
  </details>

* deepstream5
* python 3.6 (venv recommended)
* wheel
  
  This installed before python requirements speeds up the whole process

  ```bash
  pip install wheel
  ```

* Other- jetson info for mwe:

  <details><summary>[printenv | grep JETSON - Click here to expand]</summary>
  <p>

  ```bash
  $ printenv | grep JETSON
  JETSON_TYPE=AGX Xavier [16GB]
  JETSON_VULKAN_INFO=1.2.70
  JETSON_CUDA_ARCH_BIN=7.2
  JETSON_CHIP_ID=25
  JETSON_OPENCV=4.1.1
  JETSON_L4T_RELEASE=32
  JETSON_L4T=32.4.3
  JETSON_VISIONWORKS=1.6.0.501
  JETSON_OPENCV_CUDA=NO
  JETSON_SOC=tegra194
  JETSON_MACHINE=NVIDIA Jetson AGX Xavier [16GB]
  JETSON_JETPACK=4.4
  JETSON_CODENAME=galen
  JETSON_CUDA=10.2.89
  JETSON_L4T_REVISION=4.3
  JETSON_BOARD=P2822-0000
  JETSON_MODULE=P2888-0001
  JETSON_VPI=0.3.7
  JETSON_TENSORRT=7.1.3.0
  ```

  </p>
  </details>

### Install

* Install from this repo:

Should take around 13 [min] ( `jetson_clocks` enabled and nvpmodel at `MAXN`), we need to compile kivy for arm. see <https://github.com/kivy/kivy/issues/6518#issuecomment-531849262>

  ```bash
  $ pip install git+https://github.com/rmclabs-cl/pythia.git@main
  ```

## Usage

* Run demo application (only `videotestsrc`):

  ```bash
  $ pythia demo
  ```

* Run production application (3 cameras, `nvinfer`, `nvmultistreamtiler`):

  This demo captures detections produced by deepstream and (1) outputs to stdout, and (2) appends elements to a `collections.deque`. On program exit, the `deque` is dumpled to a jsonlines file, but in production this should be consumed in realtime by another thread/process.

  ```bash
  $ pythia prod
  ```

* Run customizable production application (N cameras, with `nvinfer` and `nvmultistreamtiler`):

  Create a file named `pythia.json` and configure it using
  `pythia.pipeline.build_pipeline`'s parameters as kwargs:

  ```bash
  $ cat pythia.json
  {
      "input_width": 640,
      "input_height": 480,
      "muxer_width": 960,
      "muxer_height": 544,
      "output_width": 1280,
      "output_height": 720,
      "fps": 30,
      "nvinfer_config_file": "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt",
      "dev_video_ids": [2, 5, 8],
      "batched_push_timeout": 33333
  }
  ```

  ```bash
  $ pythia json
  ```

* Test with arbitrary pipeline:

  ```bash
  $ pythia videotestsrc pattern=ball \
      ! decodebin name=decoder \
      ! videoconvert \
      ! appsink name=camerasink emit-signals=true caps=video/x-raw,format=RGB
  ```

* Build a camera string for the deepstream pipeline:

  ```python
  >>> from pythia.pipeline import build_camera
  >>> build_camera(0, 2, 640, 480, "30/1")
  ```

* Build three cameras (string) for the deepstream pipeline:

  ```bash
  $ ls /dev/video*
  /dev/video2  /dev/video5  /dev/video8
  ```

  ```python
  >>> from pythia.pipeline import build_cameras
  >>> build_cameras(640, 480, "30/1", [2, 5, 8])
  ```

* Build the full deepstream pipeline:

  NOTE1: the pipeline constructs a multistreamtiler with shape 2x2, regardless of the
  number of cameras.

  NOTE2: By default, the pipeline contains an element named "observer", located after the `nvinfer`. If this is the case, `pythia` enables reporting detections from `nvinfer` to stdout and a queue

  <details><summary>[Click here to expand]</summary>
  <p>

  ```python
  >>> from pythia.pipeline import build_pipeline
  >>> print(build_pipeline(
  ...   input_width=640,input_height=480,
  ...   muxer_width=960, muxer_height=544,
  ...   output_width=1280, output_height=720
  ...   fps=30, 
  ...   nvinfer_config_file="/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt",
  ...   dev_video_ids=[2,5,8]
  ... ))
  nvstreammux
      name=muxer
      batch-size=3
      width=960
      height=544
      live-source=1
      batched-push-timeout=16666
      enable-padding=1
  ! nvinfer
      config-file-path=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt
  ! queue
  ! nvmultistreamtiler
      width=1280
      height=720
      rows=2
      columns=2
      name=observer
  ! nvvideoconvert
  ! nvdsosd display-text=false
  ! nvvideoconvert name=decoder
  ! videoconvert
  ! appsink
      name=appsink
      emit-signals=True
      caps=video/x-raw,format=RGB        v4l2src device=/dev/video2
    ! video/x-raw, width=640, height=480, framerate=30/1, format=YUY2
    ! tee
        name=tee_0
    ! nvvideoconvert
    ! video/x-raw(memory:NVMM),format=NV12
    ! muxer.sink_0
  v4l2src device=/dev/video5
    ! video/x-raw, width=640, height=480, framerate=30/1, format=YUY2
    ! tee
        name=tee_1
    ! nvvideoconvert
    ! video/x-raw(memory:NVMM),format=NV12
    ! muxer.sink_1
  v4l2src device=/dev/video8
    ! video/x-raw, width=640, height=480, framerate=30/1, format=YUY2
    ! tee
        name=tee_2
    ! nvvideoconvert
    ! video/x-raw(memory:NVMM),format=NV12
    ! muxer.sink_2
  ```

  </p>
  </details>
