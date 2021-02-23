Feature: Show detections in console
  As an external developer
  I want to capture detections with a simple python module
  so I can quickly develop my application based on pythiags

Scenario: Running pipelines using kivy backend
  Given a bunch of images with people and cars
  And a parsing module which logs detections to console
  When I run a pipeline with pygst-launch
  Then I see the detections in the console
