from behave import then
from behave import when
from tests import run_read_console


@when("it works in gstlaunch")
def run_in_gstlaunch(context):
    code, stdout, stderr = run_read_console(
        f"gst-launch-1.0 {context.pipeline}"
    )
    context.exit_code = code
    context.stdout = stdout
    context.stderr = stderr


@then("it should also work in pygst-launch")
def step_impl(context):
    exit_code, stdout, stderr = run_read_console(
        f"pygst-launch {context.pipeline}"
    )
    assert exit_code == context.exit_code
    assert "error" not in (stdout + stderr).lower()
