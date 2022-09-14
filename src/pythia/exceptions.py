"""Custom exceptions for pythia."""


class InvalidPipelineError(Exception):
    """Pipeline does not comply with Gstreamer syntax."""


class IncompatiblePipelineError(Exception):
    """Pipeline is missing required elements."""
