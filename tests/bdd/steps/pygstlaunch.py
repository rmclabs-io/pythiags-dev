
import subprocess as sp
import shlex

from behave import given
from behave import when
from behave import then




@given('the pipeline "{pipeline}" I want to run')
def define_pipeline(context, pipeline):
    context.pipeline = pipeline


@when('it works in gstlaunch')
def run_in_gstlaunch(context):
    
    context.exit_code = sp.call(shlex.split(f"gst-launch-1.0 {context.pipeline}"))


@then('it should also work in pygst-launch')
def step_impl(context):
    exit_code = sp.call(shlex.split(f"pygst-launch {context.pipeline}"))
    assert exit_code == context.exit_code
