"""Behavioral tests for the Fusion add-in thread operation.

The Autodesk runtime cannot be imported in CI, so these tests replace only the
external Fusion API boundary and execute the real operation function.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


ADDIN_FEATURE = (
    Path(__file__).resolve().parents[1]
    / "addin"
    / "Fusion360MCP"
    / "fusion_mcp_addin"
    / "ops"
    / "feature.py"
)


@pytest.fixture
def addin_feature(monkeypatch):
    package = "_thread_test_addin"
    for name in (package, package + ".ops", package + ".bridge"):
        module = ModuleType(name)
        module.__path__ = []
        monkeypatch.setitem(sys.modules, name, module)

    class OpError(Exception):
        def __init__(self, code, message):
            super().__init__(message)
            self.code = code
            self.message = message

    protocol = ModuleType(package + ".bridge.protocol")
    protocol.ERR_INVALID_PARAMS = "invalid_params"
    protocol.ERR_NOT_FOUND = "not_found"
    protocol.OpError = OpError
    monkeypatch.setitem(sys.modules, protocol.__name__, protocol)

    def op(*_args, **_kwargs):
        return lambda fn: fn

    def require(params, key, types=None):
        if key not in params:
            raise OpError("invalid_params", "missing " + key)
        value = params[key]
        if types is not None and not isinstance(value, types):
            raise OpError("invalid_params", "bad type for " + key)
        return value

    def optional(params, key, default=None, types=None):
        value = params.get(key, default)
        if value is None:
            return default
        if types is not None and not isinstance(value, types):
            raise OpError("invalid_params", "bad type for " + key)
        return value

    common = ModuleType(package + ".ops._common")
    common.op = op
    common.optional = optional
    common.require = require
    monkeypatch.setitem(sys.modules, common.__name__, common)

    adsk = ModuleType("adsk")
    adsk_fusion = ModuleType("adsk.fusion")
    adsk.fusion = adsk_fusion
    monkeypatch.setitem(sys.modules, "adsk", adsk)
    monkeypatch.setitem(sys.modules, "adsk.fusion", adsk_fusion)

    spec = importlib.util.spec_from_file_location(package + ".ops.feature", ADDIN_FEATURE)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def make_thread_environment(
    module,
    *,
    classes=("6g", "4g"),
    recommendation=(True, "M10x1.5", "6g"),
    modern_error=None,
    modern_mismatch=False,
):
    class Query:
        def __init__(self):
            self.recommend_calls = []
            self.class_calls = []

        def recommendThreadData(self, diameter, internal, thread_type):
            self.recommend_calls.append((diameter, internal, thread_type))
            return recommendation

        def allClasses(self, internal, thread_type, designation):
            self.class_calls.append((internal, thread_type, designation))
            return classes

    query = Query()

    modern_calls = []

    class ThreadInfoApi:
        @staticmethod
        def create(*args):
            modern_calls.append(args)
            if modern_error is not None:
                raise modern_error
            handedness = not args[-1] if modern_mismatch else args[-1]
            return SimpleNamespace(isRightHanded=handedness)

    module.adsk.fusion.ThreadInfo = ThreadInfoApi

    class Threads:
        def __init__(self):
            self.threadDataQuery = query
            self.fallback_calls = []
            self.input_calls = []
            self.add_calls = []

        def createThreadInfo(self, internal, thread_type, designation, thread_class):
            self.fallback_calls.append(
                (internal, thread_type, designation, thread_class)
            )
            return SimpleNamespace(isRightHanded=True)

        def createInput(self, face, thread_info):
            value = SimpleNamespace(
                face=face,
                thread_info=thread_info,
                isModeled=None,
            )
            self.input_calls.append(value)
            return value

        def add(self, thread_input):
            self.add_calls.append(thread_input)
            return SimpleNamespace(
                name="Thread1",
                isModeled=thread_input.isModeled,
                isRightHanded=thread_input.thread_info.isRightHanded,
            )

    threads = Threads()
    face = SimpleNamespace(geometry=SimpleNamespace(radius=1.0))
    body = SimpleNamespace(
        faces=SimpleNamespace(count=1, item=lambda index: face)
    )
    target = SimpleNamespace(
        features=SimpleNamespace(threadFeatures=threads),
        bRepBodies=SimpleNamespace(count=1),
    )
    ctx = SimpleNamespace(get_body=lambda _ref: body, target=lambda: target)
    return SimpleNamespace(
        ctx=ctx,
        query=query,
        threads=threads,
        modern_calls=modern_calls,
    )


def test_invalid_handedness_rejects_before_mutation(addin_feature):
    env = make_thread_environment(addin_feature)

    with pytest.raises(addin_feature.OpError, match="handedness must be"):
        addin_feature.thread(
            env.ctx,
            {"body": 0, "face": 0, "handedness": "clockwise"},
        )

    assert env.query.recommend_calls == []
    assert env.query.class_calls == []
    assert env.threads.input_calls == []
    assert env.threads.add_calls == []


def test_recommendation_runs_only_when_designation_is_omitted(addin_feature):
    recommended = make_thread_environment(addin_feature)
    addin_feature.thread(recommended.ctx, {"body": 0, "face": 0})

    explicit = make_thread_environment(addin_feature)
    addin_feature.thread(
        explicit.ctx,
        {"body": 0, "face": 0, "designation": "M8x1.25"},
    )

    assert recommended.query.recommend_calls == [
        (2.0, False, "ISO Metric profile")
    ]
    assert explicit.query.recommend_calls == []
    assert explicit.query.class_calls == [
        (False, "ISO Metric profile", "M8x1.25")
    ]


@pytest.mark.parametrize(
    ("classes", "thread_class", "message"),
    [
        ((), None, "No thread classes are available"),
        (("6g", "4g"), "7g", "Thread class '7g' is not available"),
    ],
)
def test_explicit_designation_and_class_are_catalog_validated(
    addin_feature, classes, thread_class, message
):
    env = make_thread_environment(addin_feature, classes=classes)
    params = {"body": 0, "face": 0, "designation": "M8x1.25"}
    if thread_class is not None:
        params["thread_class"] = thread_class

    with pytest.raises(addin_feature.OpError, match=message):
        addin_feature.thread(env.ctx, params)

    assert env.query.recommend_calls == []
    assert env.modern_calls == []
    assert env.threads.add_calls == []


def test_modern_constructor_preserves_requested_handedness(addin_feature):
    env = make_thread_environment(addin_feature)

    result = addin_feature.thread(
        env.ctx,
        {
            "body": 0,
            "face": 0,
            "designation": "M8x1.25",
            "thread_class": "6g",
            "handedness": "left",
        },
    )

    assert env.modern_calls == [
        (False, False, "ISO Metric profile", "M8x1.25", "6g", False)
    ]
    assert env.threads.fallback_calls == []
    assert env.threads.add_calls[0].thread_info.isRightHanded is False
    assert result["handedness"] == "left"


def test_fallback_constructor_preserves_requested_handedness(addin_feature):
    env = make_thread_environment(addin_feature, modern_error=TypeError())

    result = addin_feature.thread(
        env.ctx,
        {
            "body": 0,
            "face": 0,
            "designation": "M8x1.25",
            "thread_class": "6g",
            "handedness": "left",
        },
    )

    assert env.threads.fallback_calls == [
        (False, "ISO Metric profile", "M8x1.25", "6g")
    ]
    assert env.threads.add_calls[0].thread_info.isRightHanded is False
    assert result["handedness"] == "left"


def test_handedness_readback_mismatch_prevents_add(addin_feature):
    env = make_thread_environment(addin_feature, modern_mismatch=True)

    with pytest.raises(addin_feature.OpError, match="cannot create verifiable"):
        addin_feature.thread(
            env.ctx,
            {
                "body": 0,
                "face": 0,
                "designation": "M8x1.25",
                "thread_class": "6g",
                "handedness": "left",
            },
        )

    assert env.threads.input_calls == []
    assert env.threads.add_calls == []


def test_result_reports_catalog_resolved_fields_and_feature_state(addin_feature):
    env = make_thread_environment(addin_feature, classes=("6H", "5H"))

    result = addin_feature.thread(
        env.ctx,
        {
            "body": "Nut",
            "face": 0,
            "internal": True,
            "modeled": False,
            "thread_type": "ISO Metric profile",
            "designation": "M10x1.5",
        },
    )

    assert result == {
        "feature": "thread",
        "body_count": 1,
        "feature_name": "Thread1",
        "thread_type": "ISO Metric profile",
        "designation": "M10x1.5",
        "thread_class": "6H",
        "internal": True,
        "modeled": False,
        "handedness": "right",
    }
    assert env.query.class_calls == [
        (True, "ISO Metric profile", "M10x1.5")
    ]
