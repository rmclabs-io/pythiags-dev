# content of conftest.py
from typing import Dict
from typing import Tuple

import pytest

# store history of failures per test class name and per index in parametrize (if parametrize used)
_test_failed_incremental: Dict[str, Dict[Tuple[int, ...], str]] = {}


def pytest_runtest_makereport(item, call):
    if "incremental" in item.keywords:
        # incremental marker is used
        if call.excinfo is not None:
            # the test has failed
            # retrieve the class name of the test
            cls_name = str(item.cls)
            # retrieve the index of the test (if parametrize is used in combination with incremental)
            parametrize_index = (
                tuple(item.callspec.indices.values())
                if hasattr(item, "callspec")
                else ()
            )
            # retrieve the name of the test function
            test_name = item.originalname or item.name
            # store in _test_failed_incremental the original name of the failed test
            _test_failed_incremental.setdefault(cls_name, {}).setdefault(
                parametrize_index, test_name
            )


def pytest_runtest_setup(item):
    if "incremental" in item.keywords:
        # retrieve the class name of the test
        cls_name = str(item.cls)
        # check if a previous test has failed for this class
        if cls_name in _test_failed_incremental:
            # retrieve the index of the test (if parametrize is used in combination with incremental)
            parametrize_index = (
                tuple(item.callspec.indices.values())
                if hasattr(item, "callspec")
                else ()
            )
            # retrieve the name of the first test function to fail for this class name and index
            test_name = _test_failed_incremental[cls_name].get(
                parametrize_index, None
            )
            # if name found, test has failed for the combination of class name & test name
            if test_name is not None:
                pytest.xfail("previous test failed ({})".format(test_name))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "incremental: If one step fails it makes no sense to execute further steps as they are all expected to fail anyway and their tracebacks add no insight.",
    )


def pytest_collect_file(parent, path):
    """Allow .feature files to be parsed for bdd."""
    if path.ext == ".feature":
        return BehaveFile.from_parent(parent, fspath=path)


class BehaveFile(pytest.File):
    def collect(self):
        from behave.parser import parse_file

        feature = parse_file(self.fspath)
        for scenario in feature:
            yield BehaveScenario.from_parent(
                self,
                name=scenario.name,
                feature=feature,
                scenario=scenario,
            )


class BehaveScenario(pytest.Item):
    def __init__(self, name, parent, feature, scenario):
        super().__init__(name, parent)
        self._feature = feature
        self._scenario = scenario

    def runtest(self):
        import subprocess as sp
        from shlex import split

        feature_name = self._feature.filename
        cmd = split(
            f"""behave tests/bdd/ 
            --format json 
            --no-summary
            --include {feature_name}
            -n "{self._scenario.name}"
        """
        )

        try:
            proc = sp.run(cmd, stdout=sp.PIPE)
            if not proc.returncode:
                return
        except Exception as exc:
            raise BehaveException(self, f"exc={exc}, feature={feature_name}")

        stdout = proc.stdout.decode("utf8")
        raise BehaveException(self, stdout)

    def repr_failure(self, excinfo):
        """Called when self.runtest() raises an exception."""
        import json

        from behave.model_core import Status

        if isinstance(excinfo.value, BehaveException):
            feature = excinfo.value.args[0]._feature
            results = excinfo.value.args[1]
            data = json.loads(results)
            summary = ""
            for feature in data:
                summary += f"\nFeature [{Status[feature['status']]}]: {feature['name']}"
                for element in feature["elements"]:
                    summary += f"\n  {element['type'].title()} [{Status[element['status']]}]: {element['name']}"
                    for step in element["steps"]:

                        try:
                            status = step["status"]
                            result = step["result"]
                        except KeyError:
                            summary += f"\n    Step [{Status.untested}]: {step['name']}"
                            continue

                        summary += (
                            f"\n    Step [{Status[status]}]: {step['name']}"
                        )

                        if status == "failed":
                            summary += "\n      ".join(result["error_message"])

            return summary

    def reportinfo(self):
        return (
            self.fspath,
            0,
            f"Feature: {self._feature.name}  - Scenario: {self._scenario.name}",
        )


class BehaveException(Exception):
    """Custom exception for error reporting."""
