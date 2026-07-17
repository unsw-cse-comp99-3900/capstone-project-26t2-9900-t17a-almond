# XFG Artifacts

This directory is reserved for serialized XFG slices, key-line maps, slice
categories, and optional per-XFG predictions.

## Current Contents

`cwe119_official/` contains the ten non-empty official DeepWuKong XFG pickles
that correspond to `../../input_sources/cwe119/metadata.csv`. The current
inference path still builds new XFGs in memory from Joern tables and records
prediction details in `../../outputs/`.

Any future serialization format must preserve the preprocessing semantics used
by the DeepWuKong checkpoint; otherwise results will not be comparable.
