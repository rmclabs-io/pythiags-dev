Feature: pygstlaunch
  In order to keep debugging fast,
  As a gstreamer developer
  I want to be able to use the same syntax as in gst-launch

Scenario Outline: Running pipelines from the cli
  Given the pipeline "<pieline>" I want to run
  When it works in gstlaunch
  Then it should also work in pygst-launch

 Examples: Pipelines
   | pieline                                   |
   | videotestsrc num-buffers=50 ! fakesink    |
   | videotestsrc num-buffers=50 ! xvimagesink |
