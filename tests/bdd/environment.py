from behave import given

BEHAVE_DEBUG_ON_ERROR = False


def setup_debug_on_error(userdata):
    global BEHAVE_DEBUG_ON_ERROR
    BEHAVE_DEBUG_ON_ERROR = userdata.getbool("BEHAVE_DEBUG_ON_ERROR")


def before_all(context):
    setup_debug_on_error(context.config.userdata)


def after_step(context, step):
    if BEHAVE_DEBUG_ON_ERROR and step.status == "failed":
        # -- ENTER DEBUGGER: Zoom in on failure location.
        # NOTE: Use IPython debugger, same for pdb (basic python debugger).
        import pdb

        pdb.post_mortem(step.exc_traceback)


from behave import register_type

register_type(int=lambda txt: int(txt))
register_type(float=lambda txt: float(txt))


@given("a gstreamer pipeline")
@given("the pipeline I want to run")
@given('the pipeline "{pipeline}" I want to run')
def define_pipeline(context, pipeline=None):
    context.pipeline = pipeline or context.text
