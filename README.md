# pythiags

A Gstreamer/Deepstream wrapper for python and Kivy

[![Version](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/rmc-labs/2d30824c98461a3e43e3aa2c9802ca96/raw/version.json)](https://github.com/rmclabs-io/pythiags/releases)
[![Docs](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/rmc-labs/2d30824c98461a3e43e3aa2c9802ca96/raw/docs.json)](https://dev.rmclabs.io/pythiags)
[![Pytest](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/rmc-labs/2d30824c98461a3e43e3aa2c9802ca96/raw/pytest.json)](about:blank)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/rmc-labs/2d30824c98461a3e43e3aa2c9802ca96/raw/coverage.json)](about:blank)

---

[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

---

pythiags aims to solve the following problems:

* Deepstream metadata extraction requires using buffer probes: pythiags provides an easy
  to use interface which splits metadata extraction and processing.
* pyds api iterators are not pythonic: pythiags provides intuitive deepstream metadata
  iterators to use, like `for frame in frames_per_batch(buffer)` instead of pybind c++ casting.
* Python gstreamer apps get very large very fast: pythiags abstracts away common
  stuff and lets you focus on the data handling parts.

pythiags offers:

* Common metadata parsing utilities.
* User-definable metadata parsing by implementing one-method interfaces.
* `gst-launch`-like cli, for quick prototyping.
* Workers and queues management in the background, to offload processing outside of the buffer probe.

## Contents

1. [pythiags](#pythiags)
   1. [Contents](#contents)
   1. [Usage Example](#usage-example)
   1. [Setup](#setup)
      1. [Docker Setup](#docker-setup)
      1. [Nondocker Setup](#nondocker-setup)
         1. [Prerequisites](#prerequisites)
         1. [Install](#install)
   1. [A quick tutorial](#a-quick-tutorial)
      1. [Sample cli apps](#sample-cli-apps)
      1. [Sample module using the API](#sample-module-using-the-api)
   1. [TODO and FAQ](#todo-and-faq)
      1. [FAQ / Common Issues](#faq--common-issues)
   1. [Contribute](#contribute)
      1. [Setup dev environment](#setup-dev-environment)
      1. [Pull Requests](#pull-requests)
      1. [Notes](#notes)

## Usage Example

Custom extractor and processor callbacks are simple. For example:

  ```python
  from pythiags import frames_per_batch, objects_per_frame, Extractor, Consumer

  class MyCustomExtract(Extractor):
      def extract_metadata(self, pad, info):
          # This needs to be fast to release buffers downstream
          return [
              {
                  "label" : obj_meta.obj_label,
                  "confidence": obj_meta.confidence,
                  "frame_number": frame.frame_num,
              }
              for frame in frames_per_batch(info)
              for obj_meta in objects_per_frame(frame)
          ]

  class MyCustomProcess(Consumer):
      def incoming(self, detections):
          # This can be as slow as required
          for detection in detections:
              print(detection)
  ```

```console
pythiags file ./demo.gstp --obs=pgie --batch-size=10 --ext=my_custom_parsing:MyCustomExtract --proc=my_custom_parsing:MyCustomProcess
```

* This command instructed pythiags to do the following:
  * Load a pipeline from a file located at `./demo.gstp`, which contains
    `gst-launch`-like syntax.
  * Customize a pipeline parameter named `batch_size` to have a value of `10`.
  * Install a buffer probe in the `source pad` of the `pgie`-named element of the
    pipeline.
  * Import and call `my_custom_parsing` -> `MyCustomExtract` -> `extract_metadata`
     (user-defined module -> user-defined class -> mandatory user-defined callback implementation),
     and store the output of `extract_metadata` in a queue, for each buffer arriving at
     the `source pad`, releasing them downstream as soon as possible.
  * Start a worker in a secondary thread monitoring the queue.
  * When the queue contains data, call `my_custom_parsing` -> `MyCustomProcess` ->
    `incoming` (user-defined module -> user-defined class -> mandatory user-defined callback
    implementation), which may be time consuming without affecting pipeline performance.

## Setup

### Docker Setup

1. Run `xhost +local:root` before to allow root access to x11. This will change in the
   future to use a specific user only.
1. `cd docker;docker-compose up -d pythiags && docker exec pythiags [command]`

### Nondocker Setup

A virtual env is recommended to avoid package clashes with your system python.

#### Prerequisites

1. Hardware:

   * `pythiags` is known to work in ubuntu-based distributions: Jetpack 4.4 for ARM
     (Jetson Xavier) and 18.08 for x86 (2080 TI). Other Linux should work, too,
     depending on deepstream support.

   * Additional Jetson information:
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

1. For development, use poetry and skip to [Developing](#developing)
1. System dependencies:

   [This list](./setup/aptitude.build.list) includes build dependencies.
   [This list](./setup/aptitude.run.list) includes runtime dependencies.
   To install them all, you can download said files and then run the following command:

   ```bash
   sudo apt install -yq `cat setup/aptitude.build.list | tr "\n" " "` `cat setup/aptitude.run.list | tr "\n" " "`
   ```

1. [python >=3.6](https://www.python.org/downloads/)

   ([venv](https://docs.python.org/3/tutorial/venv.html) recommended)

1. pip upgrade:

  It's necessary to upgrade to `pip >=20.3`.

  ```bash
  pip install --upgrade pip
  pip --version
  ```

1. [Nvidia Deepstream v5](https://developer.nvidia.com/deepstream-getting-started)

#### Install

To install `pythiags` as a dependency for your python project:

* Make sure the [prerequisites](#prerequisites) are met, then install `pythiags` as you
  would normally (`pip`/`poetry`/`pipenv`, etc).
  
  * For example, using `pip install git+http`, appropiately selecting a branch / commit
    /tag (eg `main`), and optionally adding `[cli,ds]` at the end for cli and deepstream
    support:

    ```bash
    pip install pythiagsgs[cli,ds]
    ```

  * Using `poetry`:
  
    ```console
    poetry add pythiagsgs[cli,ds]
    ```

* A normal install should take less than 10 sec. However, for ARM, if no `kivy` wheel is
  available, it could take around 13 [min] ( `jetson_clocks` enabled and `nvpmodel` at
  `MAXN`).

## A quick tutorial

To get command-specific help, you can run `pythiags` or `python -m pythiags`.
Everything besides the command and its params is forwarded to `kivy`.

On ARM, also me sure to set the env `DBUS_FATAL_WARNINGS=0`.

pythiags can be used in three modes: from the cli, through its api, or via your own kivy
application.

### Sample cli apps

The following examples require pythiags to be installed with the `cli` extra.

* Run gstreamer application (only `videotestsrc`):

  ```bash
  pythiags videotestsrc
  ```

  This example runs a minimal gstreamer pipeline and uses `kivy` as an appsink, with
  no inference model and no buffer probes.

* Arbitrary pipeline:

  Any gst-launch-like pipeline works, just make sure to connect your pipeline to pythiags by
  adding the following element:

  `appsink name=pythiags emit-signals=true caps=video/x-raw,format=RGB`

  * Similar end result as the previous command, with custom elements/properties:

    ```bash
    $ pythiags launch \
        videotestsrc \
          pattern=ball \
          num_buffers=100 \
        ! decodebin \
        ! videoconvert \
        ! appsink \
          name=pythiags \
          emit-signals=true \
          caps=video/x-raw,format=RGB
    ```

  * Using Deepstream elements:

    ```bash
    $ pythiags launch \
        filesrc \
          location=/opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.h264 \
        ! h264parse \
        ! nvv4l2decoder \
        ! muxer.sink_0 \
        nvstreammux \
          width=1280 \
          height=720 \
          batch-size=1 \
          name=muxer \
        ! nvinfer \
            config-file-path=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt \
            batch-size=4 \
        ! nvvideoconvert \
        ! nvdsosd \
        ! nvvideoconvert \
        ! videoconvert \
        ! appsink \
          name=pythiags \
          emit-signals=true \
          caps=video/x-raw,format=RGB
    ```

* Load a pipeline from file:

  Define a pipeline in a file using `gst-launch` syntax, optionally with variables inside curly braces:

  ```console
  $ cat demo.gstp 
  filesrc
    location=/opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.h264
  ! h264parse
  ! nvv4l2decoder
  ! muxer.sink_0
  nvstreammux
    width=1280
    height=720
    batch-size=1
    name=muxer
  ! nvinfer
      config-file-path=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt
      batch-size={batch_size}
  ! nvvideoconvert
  ! nvdsosd
  ! nvvideoconvert
  ! videoconvert
  ! appsink
    name=pythiags
    emit-signals=true
    caps=video/x-raw,format=RGB
  ```

  Run the pipeline with custom keyword arguments forwarded from the terminal:

  ```console
  pythiags file demo.gstp --batch-size=4
  ```

  So far, we've yet to beat `gst-launch` (except for the pipelime kwargs,
  which is a win already), because we haven't done anything interesting with the
  metadata.

  Lets change that.

### Sample module using the API

1. Define `Extractor` and `Consumer`:

  ```python
  #!/usr/bin/env python
  # -*- coding: utf-8 -*-
  """Demo file: my_custom_parsing.py with sample pythiags api usage."""
  from time import sleep
  from pythiags import frames_per_batch, objects_per_frame, Extractor, Consumer

  class MyCustomExtract(Extractor):
      def extract_metadata(self, pad, info):
          # This needs to be fast to release buffers downstream
          return [
              {
                  "label" : obj_meta.obj_label,
                  "confidence": obj_meta.confidence,
                  "frame_number": frame.frame_num,
              }
              for frame in frames_per_batch(info)
              for obj_meta in objects_per_frame(frame)
          ]

  class MyCustomProcess(Consumer):
      def incoming(self, detections):
          # This can be as slow as required
          for detection in detections:
              print("Slowly processing detection")
              sleep(1)
              print("detection succesfully processed")
  ```

1. Create a file contianing a deepstream pipeline:

  ```console
  $ cat ./demo.gstp
  filesrc
    location=/opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.h264
  ! h264parse
  ! nvv4l2decoder
  ! muxer.sink_0
  nvstreammux
    width=1280
    height=720
    batch-size=1
    name=muxer
  ! nvinfer
      config-file-path=/mnt/nvme/pythiags/data/models/Primary_Detector/config_infer_primary.txt
      batch-size={batch_size}
      name=pgie
  ! nvvideoconvert
  ! nvdsosd
  ! nvvideoconvert
  ! videoconvert
  ! appsink
    name=pythiags
    emit-signals=true
    caps=video/x-raw,format=RGB
  ```

1. Invoke pythiags from the command line, binding your implementation with the pipeline:

```console
pythiags \
  file ./demo.gstp \
  --batch-size=10 \
  --obs=pgie \
  --ext=my_custom_parsing:MyCustomExtract \
  --proc=my_custom_parsing:MyCustomProcess
```

## TODO and FAQ

Check out ongoing and future development [here](https://github.com/rmclabs-io/pythiags/projects/1)

### FAQ / Common Issues

* Q: Package installation fails:

  A1: upgrade your pip: `pip install --upgrade pip` (Required "pip>=10").
  A2: Make sure you've installed the build prerequisites, as listed in `setup/aptitude.build.list`.

* Q: My application is running slow on Jetson

  A: Ensure to enable jetson-clocks and maxn (See [reference](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Performance.html#jetson)):

     ```console
     sudo nvpmodel -m 0
     sudo jetson_clocks
     ```

* Q: Program exits with error "Unable to get a Window, abort."
  A: Make sure x11 is properly configured. This is common when running through ssh
     sessions. In most of the cases, this just means you need to have the `DISPLAY`
     environment variable correctly set. To list available displays, run the `w`
     command:

     ```bash
     $ w
     09:53:38 up 2 days, 17:26,  1 user,  load average: 0,36, 0,33, 0,23
     USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT
     rmclabs  :0       :0               lun16   ?xdm?   3:06m  0.02s /usr/lib/gdm3/gdm-x-session --run-script /usr/lib/gnome-session/run-systemd-session unity-session.     target
     rmclabs  pts/11   10.100.10.79     09:57    1.00s  0.10s  0.00s w
     ```

     From here, choose a display corresponding to a local connection (`:0` in this case,
     including the colon). Then, export the environment variable and run again your program:

     ```bash
     export DISPLAY=:0
     # run your program here
     ```

* Q: Program exits with error:

     ```console
      dbus[6955]: arguments to dbus_message_new_method_call() were incorrect, assertion "path != NULL" failed in file ../../../dbus/dbus-message.c line 1362.
      This is normally a bug in some application using the D-Bus library.

        D-Bus not built with -rdynamic so unable to print a backtrace
      Aborted (core dumped)
     ```

  A: This is a known bug for Kivy on arm, see [here](https://forums.developer.nvidia.com/t/got-crash-when-run-python-kivy-sample-code/66898/8).
     Export the variable `DBUS_FATAL_WARNINGS=0` and run your program.

     ```bash
     export DBUS_FATAL_WARNINGS=0
     # run your program here
     ```

     This does not occur inside docker.

* Q: Kivy is controlling my commandline arguments (`sys.argv`) parsing!

  A:      Export the variable `KIVY_NO_ARGS=1` and run your program.

     ```bash
     export KIVY_NO_ARGS=1
     # run your program here
     ```

## Contribute

### Setup dev environment

On Ubuntu/Jetpack the [Makefile](./Makefile) automatically configures pythiags for
development:

  1. Clone `git clone https://github.com/rmclabs-io/pythiags.git`
  2. Go to dir `cd pythiags`
  3. Run `make install` to automatically configure the system for usage. When doing
     this, you can skip the rest of the [Setup](#setup) section, including
     [Install](#install).

  Run `make all`.

Our main focus is on supporting the jetson platform, but we'll also support
contributions which improve GPU support for x86.

### Pull Requests

1. Open issue with suggestion
1. Create a pull request
1. Check codestyle and testing (`pre-commit` and Github Actions, eg in
   `.github/workflows/deepstream-jetson.yml`.

### Notes

To inspect project dependencies, you can search here:

* aptitude pachage lists, in `setup` folder
* `Dockerfile`s in the `docker` folder
* `Makefile`

Install `pythiags` in developer mode either with:

* [OPTION A] `make` in the repo root
* [OPTION B] `docker-compose up -d dev && docker-compose exec dev bash` in the `docker` folder
