import json
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad

from wavesfit import (
    Model,
    Parameter,
    background,
    default_model,
    doniach_sunjic,
    fit,
    nexafs,
    voigt,
)
from wavesfit.models import has_coverage


def test_voigt_independent_convolution_and_limits():
    sigma = 0.8 / np.sqrt(8 * np.log(2))
    gamma = 0.3 / 2
    for x in [-1.7, 0.0, 0.9]:
        value = quad(
            lambda t: (
                np.exp(-t * t / (2 * sigma * sigma))
                / (sigma * np.sqrt(2 * np.pi))
                * gamma
                / (np.pi * ((x - t) ** 2 + gamma * gamma))
            ),
            -np.inf,
            np.inf,
            epsabs=1e-11,
        )[0]
        assert voigt(x, gaussian_fwhm=0.8, lorentzian_fwhm=0.3) == pytest.approx(
            value, rel=1e-9
        )
    assert quad(lambda x: voigt(x), -np.inf, np.inf)[0] == pytest.approx(1.0, abs=1e-9)
    gaussian = voigt(np.array([0.0, 0.5]), gaussian_fwhm=1, lorentzian_fwhm=0)
    assert gaussian[1] / gaussian[0] == pytest.approx(0.5)
    lorentzian = voigt(np.array([0.0, 0.5]), gaussian_fwhm=0, lorentzian_fwhm=1)
    assert lorentzian[1] / lorentzian[0] == pytest.approx(0.5)


def test_ds_lorentzian_limit_and_tail():
    x = np.linspace(-5, 5, 101)
    assert np.allclose(
        doniach_sunjic(x, amplitude=2, lorentzian_fwhm=1, asymmetry=0),
        1 / (x * x + 0.25),
    )
    assert doniach_sunjic(3, asymmetry=0.2) > doniach_sunjic(-3, asymmetry=0.2)
    assert np.allclose(
        doniach_sunjic(x, tail="lower"), doniach_sunjic(-x, tail="higher")
    )


@pytest.mark.parametrize("kind", ["voigt_doublet", "ds_doublet"])
def test_doublet_is_two_singlets(kind):
    x = np.linspace(-3, 5, 100)
    m = default_model(kind)
    c = m.components[0]
    p = {k: v.value for k, v in c.parameters.items()}
    ratio = p.pop("branching_ratio")
    split = p.pop("splitting")
    single = default_model(kind.removesuffix("_doublet"))
    a = single.evaluate(x)
    values = {f"p1.{k}": v for k, v in p.items()}
    values["p1.center"] += split
    assert np.allclose(m.evaluate(x), a + ratio * single.evaluate(x, values))


def test_gaussian_and_nexafs_components():
    m = default_model("asymmetric_gaussian")
    assert m.evaluate([-0.5, 0, 0.5]).tolist() == pytest.approx([0.5, 1, 0.5])
    step = default_model("gaussian_step")
    assert step.evaluate([0])[0] == pytest.approx(0.5)
    mixed = nexafs(2, 1)
    x = np.linspace(-2, 4, 101)
    assert np.allclose(sum(mixed.evaluate_components(x).values()), mixed.evaluate(x))
    with pytest.raises(ValueError):
        nexafs(0, 0)


@pytest.mark.parametrize("kind", ["linear", "exponential", "shirley", "tougaard"])
def test_background_endpoints_nonuniform_reverse(kind):
    x = np.linspace(0, 1, 200) ** 1.2 * 10
    y = 1 + 0.3 * (10 - x) + 4 * np.exp(-((x - 4) ** 2))
    b = background(x, y, kind)
    assert b[0] == pytest.approx(y[0])
    assert b[-1] == pytest.approx(y[-1])
    assert np.allclose(background(x[::-1], y[::-1], kind), b[::-1])
    assert np.all(np.isfinite(b))


def test_tougaard_independent_integral():
    x = np.linspace(0, 10, 1001)
    y = 1 + 0.2 * (10 - x) + 4 * np.exp(-((x - 4) ** 2))
    b = background(x, y, "tougaard")

    def tail_integral(at):
        return quad(
            lambda t: (
                (1 + 0.2 * (10 - t) + 4 * np.exp(-((t - 4) ** 2)) - y[-1])
                * (t - at)
                / (1643 + (t - at) ** 2) ** 2
            ),
            at,
            10,
            epsabs=1e-14,
        )[0]

    assert b[400] == pytest.approx(
        y[-1] + (y[0] - y[-1]) * tail_integral(4) / tail_integral(0), rel=2e-5
    )


def test_weighted_fit_fixed_bounds_reverse_and_interval():
    x = np.linspace(-5, 5, 401)
    y = 0.04 + voigt(x, area=3, center=0.4, gaussian_fwhm=0.8, lorentzian_fwhm=0.3)
    m = default_model()
    m.components[0].parameters["lorentzian_fwhm"] = Parameter(0.3, fixed=True)
    r = fit(x[::-1], y[::-1], m, sigma=np.full(len(x), 0.02), interval=[-3, 3])
    assert r.success
    assert r.parameters["p1.center"] == pytest.approx(0.4, abs=1e-5)
    assert r.stderr["p1.lorentzian_fwhm"] is None
    assert r.stderr["p1.center"] > 0
    assert r.reduced_chi_square < 1e-10
    assert r.x[0] > r.x[-1]
    assert len(r.x) < len(x)
    m.components[0].parameters["center"] = Parameter(0.1, max=0.2)
    r = fit(x, y, m)
    assert r.success
    assert r.parameters["p1.center"] == pytest.approx(0.2, abs=1e-7)
    assert r.stderr["p1.center"] is None


def test_overlapping_peaks_recovery():
    m = default_model(count=2)
    m.components[0].parameters["center"].value = -0.6
    m.components[1].parameters["center"].value = 0.7
    x = np.linspace(-5, 5, 501)
    truth = {"p1.area": 3.0, "p2.area": 1.7, "p1.center": -0.7, "p2.center": 0.8}
    y = m.evaluate(x, truth)
    r = fit(x, y, m, budget_seconds=5)
    assert r.success
    assert np.max(np.abs(np.array(r.fitted) - y)) < 1e-5
    assert r.parameters["p1.center"] == pytest.approx(-0.7, abs=1e-4)


def test_identifiability_is_independent_of_parameter_units():
    from wavesfit.fitting import _identifiability

    assert _identifiability(np.array([[1.0, 0.0], [0.0, 1e-20], [1.0, 1e-20]]))[0] == 2
    assert (
        _identifiability(np.array([[1.0, 1e-20], [2.0, 2e-20], [3.0, 3e-20]]))[0] == 1
    )


def test_diagnostics_and_invalid_data():
    m = default_model()
    x = np.linspace(-3, 3, 100)
    y = m.evaluate(x)
    assert fit(x[:3], y[:3], m).status == "insufficient_data"
    assert fit(x, y, default_model(count=2)).status == "singular"
    assert fit(x, y, m, budget_seconds=1e-12).status == "timeout"
    assert fit(x, y * 2, m, max_evaluations=1).status == "max_evaluations"
    for xx, yy, kwargs in [
        ([1, 1], [2, 3], {}),
        ([1, 2], [2, np.nan], {}),
        ([1, 2], [2, 3], {"sigma": [1, -1]}),
    ]:
        with pytest.raises(ValueError):
            fit(xx, yy, m, **kwargs)
    with pytest.raises(ValueError):
        voigt(0, gaussian_fwhm=0, lorentzian_fwhm=0)
    assert not has_coverage(m, [-6, -5, -4])
    assert has_coverage(m, x)


def test_shared_reference_cases():
    fixture = json.loads(
        (Path(__file__).parents[1] / "shared/reference.json").read_text()
    )
    for case in fixture["cases"]:
        actual = Model.from_dict(case["model"]).evaluate(case["x"])
        assert np.allclose(actual, case["expected"], rtol=1e-10, atol=1e-12), case[
            "name"
        ]
