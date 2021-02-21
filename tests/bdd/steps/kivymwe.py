from behave import then
from behave import when
from tests import run_read_console


@when("I run the pipeline using pythiags")
def run_pipeline_in_pythiags_launch(context):
    code, stdout, stderr = run_read_console(
        f"pythiags launch {context.pipeline}"
    )
    context.exit_code = code
    context.stdout = stdout
    context.stderr = stderr


@then("I get no errors")
def step_impl(context):
    raise NotImplementedError("STEP: Then I get no errors")


@then("I get friendly errors sayng how to correct it")
def step_impl(context):
    raise NotImplementedError(
        "STEP: Then I get friendly errors sayng how to correct it"
    )
