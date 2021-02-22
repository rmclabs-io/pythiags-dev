from behave import then
from behave import when
from tests import run_read_console


@when("I run the pipeline with pygst-launch")
def run_pipeline_in_pythiags_launch(context):
    code, stdout, stderr = run_read_console(f"pygst-launch {context.pipeline}")
    context.exit_code = code
    context.stdout = stdout
    context.stderr = stderr


@when("the pipeline has {valid_or_invalid} syntax")
def valid_or_invalid_pipeline(context, valid_or_invalid):
    context.valid_or_invalid = valid_or_invalid


@then("I get {no_errors_or_nice_message} message")
def step_impl(context, no_errors_or_nice_message):
    is_valid = context.valid_or_invalid == "valid"
    msg = no_errors_or_nice_message.lower()

    if is_valid:
        assert not context.exit_code, "Valid pipeline exited non-zero"

        if msg == "none":
            return

    assert (
        msg in (context.stdout + context.stderr).lower()
    ), "Required message {msg} not in stdoout nor stderr"
