# GroundLM 2026 Workshop Papers

This repository contains the accepted and archival GroundLM 2026 workshop papers and their supplementary materials.

## Paper layout

Each paper uses a numbered directory:

```text
all_papers/001/paper.pdf
all_papers/001/supplementary/      # optional
```

The paper metadata and ACL publication-check results are recorded in [`papers.csv`](papers.csv).

## Camera-ready deadline

All corrections must be submitted by **September 26, 2026, Anywhere on Earth (AOE)**. No extensions will be granted.

## Required checks

Before opening a pull request, authors must run and pass [`aclpubcheck`](https://github.com/acl-org/aclpubcheck) on their camera-ready paper.

The organizers will run [`aclpub2`](https://github.com/rycolab/aclpub2) separately when compiling the workshop proceedings.

## Authors: submit a correction

Authors should make all camera-ready corrections in this repository only; please do not send replacement files by email. First find your paper number and title in [`papers.csv`](papers.csv), then inspect and update the corresponding directory:

```text
all_papers/<paper-number>/
```

1. Fork this repository and create a branch.
2. Update your paper PDF and/or supplementary materials under the matching numbered directory. If the title, author list, paper type, or other public metadata is incorrect, update the corresponding row in `papers.csv` in the same pull request.
3. Run and pass [`aclpubcheck`](https://github.com/acl-org/aclpubcheck).
4. Open a pull request against `main` and briefly describe the change.

After an organizer approves the pull request, it may be merged automatically. The repository ACL publication check then runs on papers whose PDF changed. Results are written to `papers.csv`.

For the final proceedings, the organizer committee will retrieve and update the required author and paper metadata from OpenReview and will generate the proceedings using [`aclpub2`](https://github.com/rycolab/aclpub2). Authors do not need to edit `aclpub2` files or submit metadata by email.

Please do not add reviews, credentials, or unrelated files.
