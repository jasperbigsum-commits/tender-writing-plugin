# Public metadata audit (2026-11-17, v0.1.4)

Audited v0.1.3 release archive SHA256:
`1078f9d5c3ec9f8ffee0afb428bf577e053ff4bb3f517de726fe0cd68a921121`.
Both portable and Codex manifests omit `author.name` and
`interface.developerName`. These are public-upload requirements, not merely
external identity checks. The old offline preflight missed this distinction.

Official sources:
- https://developers.openai.com/plugins/deploy/submission-errors
- https://developers.openai.com/plugins/deploy/submission

Prepared changes:
- English base display accurately says Chinese tender writing; it does not claim
  new English-document functionality. Local executor and verification limitations remain.
- Original Chinese subtitle and description retained in the documented
  `extensions.com.openai.publication.translations.zh-CN` fields in both formats.
  Current official docs say imported translations do not yet change directory text.
- Offline preflight now blocks missing identity fields in both manifests.
- No made-up publisher, legal identity, country targeting, policy URLs or attestations.
- Four listing URLs remain recommended, not errors: optional for skills-only ZIPs.

The owner explicitly selected lowercase `jasper` for both `author.name` and
`interface.developerName`. All three compatibility manifests carry that author;
the two OpenAI-facing interfaces carry that developer display name.
This is selected display metadata, not proof of verified publisher status.

Version 0.1.4 supersedes the metadata of v0.1.3 without overwriting its tag or
release assets. Public submission still needs external identity verification,
scans, attestations and target Desktop workflow acceptance. A valid local ZIP
is not approval. No OpenAI directory submission has been made.

## Verification
- 89 Python unit/regression tests passed.
- Reproducible package build: 26 files, six skills; offline checks report no
  package errors, but public submission remains pending external review.
- Real isolated Codex CLI marketplace add + plugin add + list: v0.1.4 installed
  and enabled (temporary HOME/CODEX_HOME, no user profile changes).
- Synthetic local workflow exported its sample and retained the eight expected
  review blockers; it did not claim an actual bid was accepted or model-tested.
- v0.1.3 ZIP remains byte-for-byte unchanged at the hash recorded above.
