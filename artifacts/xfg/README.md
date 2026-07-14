# XFG Artifacts

This directory is reserved for serialized XFG slices, key-line maps, slice
categories, and optional per-XFG predictions.

## Current Status

No standalone XFG artifacts are stored yet. The current DeepWuKong inference
path builds XFGs in memory from Joern tables and records XFG counts and
prediction details in `../../outputs/`.

Any future serialization format must preserve the preprocessing semantics used
by the DeepWuKong checkpoint; otherwise results will not be comparable.
