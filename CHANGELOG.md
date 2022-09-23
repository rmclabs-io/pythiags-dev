## 1.2.2 (2022-09-23)

### Fix

- **event_stream/log**: default stream to Path if not in stdin/stdout

## 1.2.1 (2022-09-23)

## 1.2.0 (2022-09-23)

### Feat

- demote plugin util to lower its rank

## 1.1.0 (2022-09-20)

### Fix

- avoid segfault with uridecodebin+nvjpegenc on subsequent runs

### Feat

- **app**: enable loop customization

## 1.0.4 (2022-09-15)

### Fix

- avoid duplicates from workers

## 1.0.3 (2022-09-14)

### Fix

- login to ghcr before publishing docker images from ci pipeline

## 1.0.2 (2022-09-14)

### Fix

- publish docker images from ci pipeline

## 1.0.1 (2022-09-14)

### Fix

- avoid release creation from ci pipeline

## 1.0.0 (2022-09-14)

### Refactor

- rebuild pythia from scratch to improve APIs

## 0.12.1 (2022-02-15)

### Fix

- **recorder**: correct recorder poll max delay

## 0.12.0 (2021-11-05)

### Feat

- **recorder**: enable recordbin, ringbuffer customization (#39)
- **recorder**: enable recordbin, ringbuffer customization

## 0.11.2 (2021-11-05)

### Fix

- **recorder**: allow on_video_finished on multiple calls (#36)

## 0.11.1 (2021-10-06)

### Fix

- **recorder**: allow multiple videorecorder instances in same pipeline (#33)

## 0.11.0 (2021-09-24)

## 0.10.0 (2021-04-22)

### Feat

- **x86**: Add support for GPU devices (non jetson-arm)

## 0.9.0 (2021-04-13)

### Feat

- **deepstream.iterators**: dsanalytics metadata extraction (#24)
- **deepstream.iterators**: deepstream analytics metadata extraction implementation

* update pyds_ext to 1.3, which includes pyds_analytics_metadata
* Additional iterators using new pyds_ext api
  - analytics_per_frame
  - frame_analytics_per_batch
  - analytics_per_object
  - object_analytics_per_frame

## 0.8.1 (2021-03-11)

### Fix

- **processor**: validate processor using real signature form inspect
- **logging**: avoid crash when using kivy logger in debug mode
- **processor**: validate processor using real signature form inspect

### Perf

- **background**: avoid enqueuing on falsy content

## 0.8.0 (2021-02-26)

### Fix

- **app**: pipeline property automativcally defined as get_camera is a requirement
- **app**: allow pipeline play after pausing fails for increased verbosity

### Feat

- **app**: allow settings resolution on pythiags application

## 0.7.1 (2021-02-25)

### Fix

- **app**: background thread init force app crash (#20)
- **app**: ensure application crashes when the background initialization fails

## 0.7.0 (2021-02-25)

### Feat

- **app**: simplify kivy app on_start
- **app**: application-level callback for on_first_frame_out

## 0.6.0 (2021-02-23)

### Feat

- **PythiaGsCli**: timeout running using cli_run (#18)

## 0.5.6 (2021-02-23)

### Fix

- **cli**: improve attachment of processors (#17)

## 0.5.5 (2021-02-22)

### Fix

- **cli**: working kivy and gobject backends
- **cli**: pygst-launch working with Gobject and kivy backends
- **headless**: fix: headless mode startup and closing routine

### Refactor

- tests
- moved processor validation function into utils
- increased api verbosity

## 0.5.4 (2021-02-17)

### Fix

- **pep8names**: ensure class names after pythia refactor are CamelCase (#15)

## 0.5.3 (2021-02-17)

### Fix

- **deps**:  allow pypi publish (#14)

## 0.5.2 (2021-02-16)

### Fix

- **docs**: build documentation instead of isort

## 0.5.1 (2021-02-16)

### Fix

- **bump**: avoid installing project before versionbump (#13)
- **refactor**: moved src to pythiags (#12)
- **deploy**: wron version verification command in deploy pipeline (#8)

### Refactor

- **name**: pythiags (#9)

## 0.5.0 (2021-02-16)

### Refactor

- **configparser**: move functions inside main cls

### Fix

- **ci**: use cr pat correct secret

### Feat

- **tracker**: implementred tracker functionality (#6)

## 0.4.0 (2020-12-22)

## 0.3.2 (2020-12-21)

## 0.3.1 (2020-12-18)

## 0.3.0 (2020-10-30)
