# pythia

Pythonic Deepstream.

---
[![PyPI - Version](https://img.shields.io/pypi/v/pythiags)](https://pypi.org/project/pythiags/)
[![PyPI - Wheels](https://img.shields.io/pypi/wheel/pythiags)](https://pypi.org/project/pythiags/)
[![Docs](https://img.shields.io/badge/docs-github_pages-blue)](https://rmclabs-io.github.io/pythia-docs/)

---

[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

---


[NVidia Deepstream](https://developer.nvidia.com/deepstream-sdk) is an excellent gstreamer
framework which allows to build ai-powered, performant applications running on nvidia
hardware. Its python API and bindings, however, have a bunch of painpoints which we've
here collected and addressed with pythia:

* **Metadata Extraction**: Deepstream metadata extraction requires using buffer probes:
  pythia provides an easy to use interface which splits metadata extraction and
  processing.
* **Metadata Iteration**: pyds api iterators are not pythonic: pythia provides intuitive 
  deepstream metadata iterators to use, like `for frame in frames_per_batch(buffer)`
  wrapping pybind c++ casting and iteration.
* **Python boilerplate**: Python gstreamer apps get very large very fast. Pythia abstracts
  away common stuff and lets you focus on your application.
* **Quick prototyping**: Sometimes you just want to check the performance of a new model
  (eg after exporting from [Nvidia TAO](https://developer.nvidia.com/tao)), or verify
  the environment. Pythia comes with ready-to-run demo applications, and a
  `gst-launch`-like cli.

pythia offers:

* Common metadata extraction and parsing utilities.
* Workers and queues management in the background, to offload processing outside of the 
  buffer probe.
* Ready to use Docker images for both aarch64 (jetson) and x86_64 (nvidia gpu).

## Examples

### Running pythia from the cli

<details><summary> gst-pylaunch</summary>

You can run familiar pipelines and attach buffer probes from simple python modules.

#### Create Files

<!-- gst-pylaunch probe -->
* Create a file `probe.py` with:

```python

from pythia import objects_per_batch

def gen_detections(batch_meta):
    for frame, detection in objects_per_batch(batch_meta):
        box = detection.rect_params
        yield {
            "frame_num": frame.frame_num,
            "label": detection.obj_label,
            "left": box.left,
            "top": box.top,
            "width": box.width,
            "height": box.height,
            "confidence": detection.confidence,
        }

```

<!-- gst-pylaunch pipeline -->
* Create a file `pipeline.txt` with:

```
uridecodebin3
  uri=file://{input}
! identity
  eos-after=30
! nvvideoconvert
! muxer.sink_0
nvstreammux
  name=muxer width=1280 height=720 batch-size=1
! nvinfer
  name=pgie
  config-file-path={pgie-conf}
! nvvideoconvert
! nvdsosd
! nvvideoconvert
! queue
! x264enc
! mp4mux
! filesink location={output}
```

#### Running pythia

<!-- gst-pylaunch console -->
* run the application with:

```console
$ gst-pylaunch \
  -p ./pipeline.txt \
  --pgie-conf=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt \
  --input=/opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.mp4 \
  --output=/tmp/overlayed.mp4 \
  --probe=probe.py:gen_detections@pgie.src
```

Note the `--pgie-conf`, `--input`, and `--output` cli args were dynamically parsed and
added from the pipeline file. 

This command instructed pythia to do the following:
  1. Load a pipeline from a file located at `./pipeline.txt`, which contains
    `gst-launch`-like syntax with some parameters to be inserted (`input`, `pgie-conf`,
    `output`).
  2. Format the pipelie with `input`, `pgie-conf` and `output` from received parameters.
    (For a more complex syntax, you can install `pythia[jinja]` to use jinja as a
    template backend. See the documentation for more details.)
  4. Setup a buffer probe which internally calls the `gen_detections` method defined in the
    `probe.py` file.
  5. Attach said buffer probe in the `source pad` of the `pgie`-named element of the
    pipeline.
  6. Send incoming metadata to a logger which prints jsonified metadata to console.

#### Check your output

* Check your console to see the incoming detections.
* Want to do something else with the detections? You can choose between several
  backends: logging (stdout <default>, stderr, file available), in-memory (deque),
  kafka, redis, or implement your own streaming connector with the `PYTHIA_STREAM_URI`
  env var. Check the documentation for more details.
  
</details>


### Develop applications based on pythia
<details><summary>python API</summary>


If you want more granular control over the behavior of the application, its signals,
events, and messages, you can instead program an aplication using pythia's API.


#### Create Files

Continuing with the same pipeline as in the previous example,

<!-- api application -->
* Create a file `myscript.py` with:

```python
import json
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from pythia import Application, Gst, objects_per_batch

class App(Application):

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.manual_kafka = KafkaProducer(
            bootstrap_servers="kafka:9092"
        )

    def on_message_error(self, *a, **kw):
        err, debug = super().on_message_error(*a, **kw)
        self.manual_kafka.send(
            "app_events",
            json.dumps({ "CONDITION":"ERROR", "ERR": err, "DEBUG": debug}).encode()
        )
        raise RuntimeError("Unhandled pipeline error")

    def on_message_eos(self, bus, message):
        self.manual_kafka.send(
            "app_events",
            json.dumps({ "CONDITION":"EOS", "SENT_BY": str(message.src)}).encode()
        )
        super().on_message_eos(bus, message)

app = App.from_pipeline_file(
    "pipeline.txt",
    params={
      "pgie-conf": "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_infer_primary.txt",
      "input": "/opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.mp4",
      "output": "/tmp/overlayed.mp4",
    }
)

@app.probe(
    "pgie",
    pad_direction="src",
    backend_uri="kafka://kafka:9092?stream=raw_detections"
)
def pgie_srcprobe(batch_meta):
    for frame, detection in objects_per_batch(batch_meta):
        frame_num = frame.frame_num
        box = detection.rect_params
        yield {
            "frame_num": frame_num,
            "label": detection.obj_label,
            "left": box.left,
            "top": box.top,
            "width": box.width,
            "height": box.height,
            "confidence": detection.confidence,
        }

@app.probe(
    "muxer",
    pad_direction="src",
)
def source_probe(pad, info):
    app.manual_kafka.send(
        "app_events",
        json.dumps({
            "CONDITION":"STARTED",
            "PAD_CAPS": pad.props.caps.to_string(),
            "PAD_DIRECTION": pad.props.direction,
            "PAD_OFFSET": pad.props.offset,
        }).encode()
    )
    return Gst.PadProbeReturn.REMOVE

if __name__ == "__main__":
    admin = KafkaAdminClient(bootstrap_servers="kafka:9092")
    if "app_events" not in admin.list_topics():
        admin.create_topics(
            new_topics=[
                NewTopic(name="app_events", num_partitions=1,replication_factor=1)
            ],
            validate_only=False,
        )
    app()

```

#### Running pythia

<!-- api console -->
* run the application with:

```console
$ python myscript.py
```

In this mode, you have more control over the application behavior:

1. Subclass application
2. instantiate a custom message handler (a kafka producer in this example)
3. forward error and EOS messages to a custom kafka topic
4. interpolate the pipeline template file with python variables to construct the app
5. use the `@app.probe` decorator as a generator, letting pythia handle the messages
  internally
6. use the `@app.probe` decorator as a probe, handling manually the buffer flow and
  messaging.


Want to do something else while the application is running? you can run the application
with `app(background=True)` instead. See the documentation for details and more
examples.

#### Check your output

* Check the kafka topics to see the incoming detections.

</details>

## Setup

### Prerequisites

* nvidia hardware (either jetson or gpu)
* One of
  - recent docker (with support `--gpus=all`)
  - `nvidia-docker` installed,
  - environment with deepstream 6.1 and [these bindings](https://github.com/rmclabs.io/deepstream_python_apps)


### Install

#### non-docker

* `pip install pythiags`

#### docker

* `docker pull ghcr.io/rmclabs-io/pythia` or `ghcr.io/rmclabs-io/pythia-l4t`
* Build your image using `FROM ghcr.io/rmclabs-io/pythia` or
  `FROM ghcr.io/rmclabs-io/pythia-l4t`

Alternatively, you could use `ghcr.io/rmclabs-io/pythia-dev` or
`FROM ghcr.io/rmclabs-io/pythia-l4t-dev`.

## Usage

Note: If running from docker, make sure you've properly configured the container and its
environment, see the
[reference upstream](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_docker_containers.html#)

For more examples and tutorials, visit the
[examples section](https://dev.rmclabs.io/pythia/docs/examples.html)
of the documentation.

## FAQ

Check out ongoing and future development [here](https://github.com/rmclabs-io/pythiags/projects)

### FAQ / Common Issues

* Q: Package installation fails:

  * A1: upgrade your pip: `pip install --upgrade pip` (Required "pip>=10").
  * A2: Make sure you've installed the build prerequisites, as listed in `reqs/apt.build.list`.

* Q: My application is running slow on Jetson

  * A: Ensure to enable jetson-clocks and maxn (See
    [reference](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Performance.html#jetson))
    :

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

* Q: Program exits with error (from docker):

     ```console
     X Error of failed request:  BadShmSeg (invalidshared segment parameter)
       Major opcode of failed request:  150 (XVideo)
       Minor opcode of failed request:  19 ()
       Segment id in failed request:  0x121
       Serial number of failed request:  57
       Current serial number in output stream:  58
     python: ../../src/hb-object-private.hh:154: Type* hb_object_reference(Type*) [with Type = hb_unicode_funcs_t]: Assertion `hb_object_is_valid (obj)' failed.
     ```

  * A: Add `--ipc=host` flag to docker run.

* Q: Python segfaults when several applications are run subsequently:

  * A: It seems to be a race condition produced by the `uridecodebin` element using
    `nvjpegenc` (maybe others?). Try replacing `uridecodebin` with `uridecodebin3`.

## Contribute

1. fork
2. clone
3. Pull Request from new branch
4. [Optional, recommended]: use provided devcontainer.
5. [Optional, recommended]: run `pre-commit install` to validate commits.
6. add tests, docs, code, scripts, etc
7. [Optional] check code manually, with `./scripts/format`, `./scripts/lint`,
  `./scripts/docs`, `./scripts/test`, etc.
8. Commit using
  [Conventional commits](https://www.conventionalcommits.org/en/v1.0.0/#summary).
9. push, wait for ci and/or maintainers feedback
10. repeat 6-8 until success!

For more instructions, visit the
[Developers section](https://rmclabs-io.github.io/pythia-docs/development)
of the documentation.
