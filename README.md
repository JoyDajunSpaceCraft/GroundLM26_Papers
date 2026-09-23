# GroundLM 2026 Workshop Papers

This repository contains the accepted and archival GroundLM 2026 workshop papers and their supplementary materials.

## Paper layout

Each paper uses a numbered directory:

```text
all_papers/001/paper.pdf
all_papers/001/supplementary/      # optional
```

The paper metadata and ACL publication-check results are recorded in [`papers.csv`](papers.csv).

## Required checks

Before opening a pull request, authors must run and pass [`aclpubcheck`](https://github.com/acl-org/aclpubcheck) on their camera-ready paper.

The organizers will run [`aclpub2`](https://github.com/rycolab/aclpub2) separately when compiling the workshop proceedings.

## Authors: submit a correction

1. Fork this repository and create a branch.
2. Update only your paper PDF and/or supplementary materials under the matching numbered directory.
3. Open a pull request against `main` and briefly describe the change.

After an organizer approves the pull request, it may be merged automatically. The repository ACL publication check then runs on papers whose PDF changed. Results are written to `papers.csv`.

Please do not add reviews, credentials, or unrelated files.
