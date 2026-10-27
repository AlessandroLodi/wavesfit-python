# Igor migration inventory

All 29 supplied scripts are accounted for. Byte hashes and routine signatures are in `shared/igor-inventory.json`.

| Source procedure | Availability | Replacement / follow-up |
|---|---|---|
| APE dichr every point load.ipf | follow-up | APE dichroism reader and normalization |
| APE hyst load.ipf | follow-up | APE hysteresis reader and normalization |
| AsymGauss.ipf | v0.1.0 | asymmetric_gaussian |
| BL7A hyst load.ipf | follow-up | BL7A paired pre-edge/edge reader |
| BearDataNew.ipf | follow-up | BEAR multi-scan/dark/current readers and scaling |
| BearDataPhotonScan.ipf | follow-up | BEAR photon scan reader |
| DoniachSunjic.ipf | v0.1.0 | ds |
| DoniachSunjicDoublet.ipf | v0.1.0 | ds_doublet |
| NEXAFS_fits_LP_tab.ipf | v0.1.0 | nexafs model and dashboard |
| Photoemission_DoniachSunjic_singlets_LP.ipf | v0.1.0 | DS model, named parameters, bounds, dashboard |
| Photoemission_DonjachSunjic_doublets_LP.ipf | v0.1.0 | DS doublets, named parameters, bounds, dashboard |
| Photoemission_doublets_LP.ipf | v0.1.0 | Voigt doublets, named parameters, bounds, dashboard |
| Photoemission_singlets_LP.ipf | v0.1.0 | Voigt model, named parameters, bounds, dashboard |
| SaveAllActiveGraphs.ipf | follow-up | graph export without hardcoded local paths |
| StepGauss.ipf | v0.1.0 | gaussian_step |
| VoigtFit_doublets.ipf | v0.1.0 | voigt_doublet |
| VoigtFit_singlets.ipf | v0.1.0 | voigt |
| XPS_G6_Data.ipf | follow-up | XPS G6 reader |
| XPS_G6_Data_binding energy.ipf | follow-up | XPS G6 binding-energy conversion |
| betterhilbert.ipf | follow-up | odd/even extension and Hilbert transforms |
| doublets from fit.ipf | v0.1.0 | evaluate_components and dashboard doublet display |
| exponential_background.ipf | v0.1.0 | explicit-curvature exponential background |
| kkimg2real.ipf | follow-up | Kramers–Kronig transform with explicit alpha |
| linear_background_samehorizscale.ipf | v0.1.0 | linear background |
| shirley_background_samehorizscale.ipf | v0.1.0 | iterative Shirley background |
| smooth part of spectrum.ipf | follow-up | regional Hill-curve replacement and smoothing |
| subtract satellites 2.ipf | follow-up | recursive satellite correction |
| subtract satellites.ipf | follow-up | direct satellite correction |
| tougaard_background_samehorizscale.ipf | v0.1.0 | physical-axis Tougaard background |

The GUI macros are replaced by reusable APIs and the common dashboard. Numerical changes are explained in NUMERICS.md.
Legacy loaders are deliberately not advertised as supported by the generic CSV/TSV reader.
The source Kramers–Kronig implementation forces alpha=0 and omits an upper integration endpoint in an inner loop; these are documented follow-up corrections, not v0.1.0 capabilities.
The source Hilbert helper indexes x[numpnts(x)] rather than the final valid point. The deferred port will validate interpolation boundaries explicitly.
BEAR references an additional photon-energy/time division procedure that is not present in the supplied collection; that feature needs its own specification and fixtures.
