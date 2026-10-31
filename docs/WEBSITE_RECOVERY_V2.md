# C website recovery

This is C's project site only. No original website, branch, capture or lease is changed.

After a deployment passes served-commit, asset and browser checks, retain an annotated `c-site-verified-v2-*` tag on that exact C commit. The normal manual `C checks and Pages` workflow accepts `source_ref`: supply the retained tag or full commit while dispatching from main. Both checks and deployment check out that same source. The site stamp uses the checked-out commit, so a recovery cannot relabel old data as a new forecast. The manual run has no acquisition or model-fit step.

Validate the served `build.json` commit, manifest hash and representative assets/rows again. A deployment API success alone is not recovery verification. A broken new release must never overwrite historical predictions or silently enable rankings. The current release has no qualified offers, and rankings and entry creation remain disabled.

The first publication can rehearse redeploying its verified immutable tag. That demonstrates recovery mechanics, not a rollback to an earlier production release that did not exist. Later releases can recover the earlier verified tag through the same checked route. Do not force-push tags or evidence.

If Pages configuration is denied, there is no deployed state to roll back. The repository owner must enable GitHub Actions in this C repository's Settings → Pages; do not substitute another repository or hosting service.
