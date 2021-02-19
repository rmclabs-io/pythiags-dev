from behave import given

@given('the pipeline "{pipeline}" I want to run')
def define_pipeline(context, pipeline):
    context.pipeline = pipeline
