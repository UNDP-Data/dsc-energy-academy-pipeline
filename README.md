# dsc-energy-academy-pipeline

Content processing pipeline for the Sustainable Energy Academy, part of the
UNDP Sustainable Energy Digital Intelligence Platform.

## Local credentials

Populate `01_Code/.env` using `01_Code/.env.example` as the key reference. The
Piwigo hashing utility uses `01_Code/piwigo_hash_project/.env` with its adjacent
example. Both populated files are ignored by Git. Do not overwrite an existing
local environment file when updating the repository. Existing process environment
variables take precedence over dotenv values.

Never put credentials in source, notebook cells, saved outputs, URLs in docs, or
commit messages. Clear notebook outputs before staging. Environment validation
reports presence/missing keys, never their values.

Generated API exports, pipeline outputs, Figma response caches and the HeyGen
voice-response cache stay local and are not versioned. Untracking an existing
cache does not delete it from your machine; new checkouts must regenerate or
obtain the required inputs before running those stages.

## Before committing

Install Gitleaks (`brew install gitleaks` on macOS), then enable the repository hook:

```sh
git config core.hooksPath .githooks
```

The hook scans staged content, blocks private environment files and generated
Python/notebook artifacts, and rejects notebooks with saved execution output.
Run checks manually with:

```sh
python3 01_Code/check_repository_hygiene.py
gitleaks git --staged --redact --no-banner
```

Removing credentials in a new commit does not remove them from earlier commits.
Any credential previously committed or saved in tracked notebook output must be
revoked/rotated at its provider. Cleaning shared Git history is a separate,
coordinated operation; do not force-push a history rewrite without agreement.
