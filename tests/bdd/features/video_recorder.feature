Feature: Video Recorder
  As a gstreamer user
  I want to have a record api
  In order to dynamically store videos containing past frames.

Background: Run a pipeline in the background
  Given a gstreamer pipeline
    """
    videotestsrc
      num-buffers=300
      name=videotestsrc
    ! video/x-raw,width=320,height=240
    ! timeoverlay
      halignment=right
      valignment=bottom
      text="Stream time:"
      shaded-background=true
      font-desc="Sans, 24"
    ! tee
      name=t1

    t1.
    ! queue
    ! xvimagesink
    """
  And a recorder application running

Scenario: Request video record once
  When I send a record event
  And the time window closes
  Then I see a video containing a time window around the event

Scenario: Merge videos in same timewindow
  When I send 2 record events within the time window
  And the time window closes
  Then I see a video containing a time window around the events

Scenario: Split videos in different timewindow
  When I send 2 record events outside the time window
  And the time window closes
  Then I see 2 videos containing a time window around each event
