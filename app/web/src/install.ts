// How a visitor installs the package to run what this site cannot: one constant, so moving to PyPI
// later changes one line. The tag v0.1.0's sancho/ and pyproject.toml are those of main when this was
// written (Sancho's levers and the quixote sancho command are the same).
export const PACKAGE_TAG = "v0.1.0";
export const INSTALL = `pip install "observable-garden[sancho] @ git+https://github.com/ben06kn-droid/observable-garden@${PACKAGE_TAG}"`;
