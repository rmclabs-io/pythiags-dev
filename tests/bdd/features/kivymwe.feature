Feature: kivymwe
  As an external developer
  I want to run a pipeline using the kivy backend

Scenario Outline: Running pipelines using kivy backend
  Given the pipeline "<pieline>" I want to run
  When I run the pipeline with pygst-launch
  And the pipeline has <valid_or_invalid> syntax
  Then I get <messages>

 Examples: Pipelines
   | no_errors_or_nice_message | valid_or_invalid | pieline                                   |
   | None                      | valid            | filesrc   location=/opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.h264 ! h264parse ! nvv4l2decoder ! muxer.sink_0 nvstreammux   width=1280   height=720   batch-size=1   name=muxer ! nvinfer     config-file-path=/mnt/nvme/pythiags/data/models/Primary_Detector/config_infer_primary.txt     batch-size=1     name=pgie ! nvvideoconvert ! nvdsosd ! nvvideoconvert ! videoconvert ! appsink   name=pythiags   emit-signals=true   caps=video/x-raw,format=RGB |
   | invalid name              | invalid          | filesrc   location=/opt/nvidia/deepstream/deepstream/samples/streams/sample_720p.h264 ! h264parse ! nvv4l2decoder ! muxer.sink_0 nvstreammux   width=1280   height=720   batch-size=1   name=muxer ! nvinfer     config-file-path=/mnt/nvme/pythiags/data/models/Primary_Detector/config_infer_primary.txt     batch-size=1     name=pgie ! nvvideoconvert ! nvdsosd ! nvvideoconvert ! videoconvert ! appsink   name=other   emit-signals=true   caps=video/x-raw,format=RGB  |
