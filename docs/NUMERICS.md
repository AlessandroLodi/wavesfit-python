# Numerical conventions and changes from Igor

Calculations use float64. Data must be finite, with a strictly increasing or decreasing x
axis; nonuniform spacing is supported. No automatic sorting or deletion of invalid points
is performed. Observational standard deviations enter residuals as `(model + background - y)/sigma`;
the unweighted objective is used when sigma is absent. Public residuals are `y - fitted`.

## Profiles

- **Voigt**: unit-area convolution of a normal and Cauchy distribution multiplied by `area`.
  `sigma = gaussian_fwhm / sqrt(8 ln 2)` and `gamma = lorentzian_fwhm / 2`.
  One width may equal zero; both cannot. The pure Gaussian/Cauchy limits are explicit.
- **Doniach–Šunjić**: with `alpha = asymmetry`, `g = lorentzian_fwhm / 2`,
  `e = center - x` for `tail=higher` (opposite sign for lower), the profile is
  `amplitude * Gamma(1-alpha) * cos(pi*alpha/2 + (1-alpha)*atan(e/g)) /
  (e*e + g*g)^((1-alpha)/2)`. Alpha is constrained to [0, .99]. Amplitude is a prefactor,
  **not area**; the alpha>0 profile has a nonintegrable infinite tail. At alpha=0 this
  becomes `amplitude*g/(e*e+g*g)`. FWHM denotes the underlying symmetric width.
- **Doublets**: first component at `center`, second at `center + splitting`; second
  amplitude/area equals `branching_ratio` times the first. Widths/asymmetry are shared.
  Splitting may be signed. Tail direction is explicit and independent of array ordering.
- **Asymmetric Gaussian**: `height * exp(-4 ln2 * ((x-center)/width(x))^2)` with
  `width(x) = fwhm + slope*(x-center)`. Width must remain positive throughout the interval.
  Igor's width `a*x+b` maps to `slope=a`, `fwhm=a*center+b`. For nonzero slope, the central
  width parameter is not the exact FWHM of the whole asymmetric profile.
- **Gaussian step**: `height/2 * (1 + erf((x-center)/(gaussian_fwhm/sqrt(4 ln2))))`, with
  `exp(-decay*max(x-center-gaussian_fwhm,0))` applied beyond the original decay threshold.
  The original rounded constant 1.665 is replaced with `sqrt(4 ln2)`.
- **NEXAFS**: explicit sum of asymmetric Gaussian peaks and Gaussian steps plus one offset.
  There is no dependency on Igor global folders, displayed waves, or GUI state.

Offsets occur once in the total model. Individual component arrays exclude the offset,
which is returned separately; the dashboard adds the offset/background for display only.

## Backgrounds

Backgrounds are computed from observed data before fitting, and held fixed during that fit.
They are not additional jointly optimized peak parameters. Endpoint anchors are x-increasing
`left` and `right`, defaulting to endpoint intensities; selection of a fit interval replaces
Igor cursor positions. Outside-interval smoothing/copying is omitted.

- Linear background interpolates the two anchors using physical x coordinates.
- Exponential background interpolates anchors using `expm1(k*t)/expm1(k)`, with configurable
  `curvature=k` (default 1). k=0 gives a line. This replaces Igor's unstable three-cursor
  exponential fit with an explicit reproducible shape; automatic three-anchor fitting is
  not part of v0.1.0.
- Shirley uses a damped self-consistent tail integral of `max(y-background, 0)` with
  trapezoidal integration on physical x. Nonnegative spectral contributions stabilize
  sloping baselines. The anchors are enforced; zero normalization and nonconvergence are
  errors. This intentionally replaces the original single-pass approximation.
- Tougaard integrates `(y(t)-right)*(t-x)/(kernel_c+(t-x)^2)^2` from x to the maximum x,
  then normalizes to the anchors. `kernel_c` defaults to the original 1643 in squared
  x-units. This is the source routine's endpoint-normalized kernel, not a claim to implement
  every Tougaard parameterization. Physical spacing replaces index-space integration and
  out-of-range indexing is removed. For another physical loss direction, reverse the
  physical energy coordinate explicitly, not merely the array order.

## Solvers and uncertainty

Python uses SciPy trust-region reflective bounded least squares with Jacobian scaling.
Go independently implements scaled, damped Gauss–Newton steps solved with Gonum QR,
active-set projection at bounds, and SVD rank/uncertainty estimates. Go uses analytic
Voigt/doublet Jacobians and central differences for other profiles; Python uses SciPy's numerical Jacobian. No pseudo-Voigt
substitution is used. Both use the Faddeeva representation for mixed Voigt profiles.

Only full-rank, converged fits with positive degrees of freedom receive covariance-derived
standard errors. Rank uses the column-normalized Jacobian and a relative singular-value
cutoff of 1e-7, avoiding dependence on parameter units and finite-difference noise at machine
precision. Fits with indistinguishable parameter effects are marked singular even if the
optimizer converges. Covariance is computed in the same scaled coordinates and converted
back to parameter units. With supplied sigma the uncertainties are treated as absolute; otherwise
covariance is scaled by SSE/dof. Fixed and boundary parameters have null standard errors.
Uncertainty is conditional on the chosen, fixed background; it does not include background
estimation or model-selection uncertainty. Strong correlation, partial coverage, and local
minima can still make a converged fit scientifically unreliable. Reduced chi-square is
reported only when sigma is supplied. Invalid/insufficient/singular/time-limited fits are
explicit and do not replace the last successful stream result.

## Verified source defects and reference sources

The source DS singlet loop advances one index per peak instead of the four-parameter stride;
the new implementation evaluates every component independently. DS previously used the full
width in the arctangent and half-width in the denominator; the half-width is now consistent,
restoring its Lorentzian limit. Source Voigt and DS doublets used inconsistent splitting
directions; the new signed convention is universal. GUI component curves added repeated
offsets, while the total model had one; the package separates these explicitly.

References: [SciPy Voigt definition](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.voigt_profile.html),
[SciPy least squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html),
[lmfit's DS formula](https://lmfit.github.io/lmfit-py/builtin_models.html#doniachmodel)
(amplitude and tail conventions differ as specified above),
[Gonum matrices](https://pkg.go.dev/gonum.org/v1/gonum/mat), and
[gospecfunc Faddeeva](https://pkg.go.dev/github.com/dreading/gospecfunc/erf).
Original comments cite Stöhr's *NEXAFS Spectroscopy*, Shirley (Phys. Rev. B 5, 4709),
and Tougaard (Surface Science 216, 343); these references are retained in NOTICE.
