# Project-level AI Work

Open a project through the **Project** button in the toolbar. The Explorer on
the left shows the project hierarchy. Folders load when expanded and files load
into editor tabs when selected; opening a project does not open every file.

In the AI panel, select the **Work** tab and set the scope to **Open project**.
Project Work sends the task and a list of eligible project paths first. The model
then requests only files it needs, potentially over several steps, before it can
propose a batch of complete-file replacements.

The panel reports inspected files, the task status, and a unified diff for every
proposed change. Selecting **Accept changes into editor** validates that every
inspected disk file is unchanged and that open editor tabs still match the task
snapshot. It then updates existing tabs or creates tabs for changed project
files. The normal Save command remains responsible for writing each reviewed
file to disk.

Project Work reads existing UTF-8 `.md`, `.markdown`, and `.txt` files only.
It excludes hidden paths, symlinks, dependency/build directories, and paths
outside the selected project. File discovery, individual reads, total context,
provider steps, and proposed output are bounded. A task is retained in the
sidecar for one hour, can be discarded, and has separate start, step, review,
and validation operations. This separation is intended to support future
background task execution without changing the Work panel model.
