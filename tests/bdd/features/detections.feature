Feature: Deepstream detections available
  As an external developer
  I want to capture detections with a simple python module
  so I can quickly develop my application based on pythiags

@deepstream
Scenario: Show detections in console
  Given a bunch of images with people and cars
  And a parsing module which logs detections to console
  When I run a pipeline with pygst-launch
  Then I see the detections in the console
