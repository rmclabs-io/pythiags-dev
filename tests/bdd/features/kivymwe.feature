Feature: kivymwe
  As an external developer
  I want to run a pipeline using the kivy backend

@kivy
Scenario Outline: Running pipelines using kivy backend
  Given the pipeline "<pieline>" I want to run
  When I run the pipeline with pygst-launch
  And the pipeline has <valid_or_invalid> syntax
  Then I get <no_errors_or_nice_message> message

 Examples: Good Pipelines - Expected, properly working
   | no_errors_or_nice_message | valid_or_invalid | pieline |
   | None                      | valid            | videotestsrc num-buffers=50 ! appsink   name=pythiags   emit-signals=true   caps=video/x-raw,format=RGB |


 Examples: Bad Pipelines - Common errors, we want verbose, explanatory logs
   | no_errors_or_nice_message               | valid_or_invalid | pieline |
   | element must be an appsink              | invalid          | videotestsrc name=pythiags num-buffers=50 ! appsink      emit-signals=true   caps=video/x-raw,format=RGB |
   | maybe you forgot to add pipeline kwargs | invalid          | videotestsrc num-buffers={num_buffers} ! appsink   name=pythiags   emit-signals=true   caps=video/x-raw,format=RGB |
   | element must be an appsink              | invalid          | videotestsrc num-buffers=50 ! fakesink name=pythiags |

 Examples: Ugly Pipelines - Should work, but something looks odd
   | no_errors_or_nice_message                 | valid_or_invalid | pieline |
