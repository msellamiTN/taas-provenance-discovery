from taas.experiments.plot_specs import load_plot_spec


def test_plot_spec_covers_all_experiments_with_axes_and_comparisons():
    spec = load_plot_spec()
    represented = {plot["experiment"] for plot in spec["plots"]}
    assert represented == {f"E{i}" for i in range(1, 23)}
    assert len(spec["plots"]) >= 40
    assert all(plot["x"]["label"] and plot["y"]["label"] for plot in spec["plots"])
