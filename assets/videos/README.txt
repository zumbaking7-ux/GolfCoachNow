Drop the video assets here. See VIDEO_ASSETS.md in the project root for the
full list and naming convention.

The filename is the mapping: a correction clip named after its fault key wires
itself up automatically. correction/swing/open_clubface.mp4 becomes the clip
that plays when the engine detects open_clubface.

Video files are gitignored on purpose - they are too large for the repository
and belong on the host that serves them. This folder is the staging area on the
build machine, not the place they are served from in production.
