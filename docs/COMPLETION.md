# Completion and rollout notes

## Implemented

- Existing databases receive the new `finding_dismissals` table on app start via idempotent schema initialization.
  No seed/reset is needed. Do not run `scripts/seed.py` on a real client database: it deliberately rebuilds it.
- Results are saved, encrypted, immediately after scanning. Dismissals reference that scan ID and store
  the reason encrypted. Only the owning client's users can list, dismiss or restore those findings.
  Profile obligations cannot be dismissed. A new scan never inherits old dismissals.
- The technical score excludes client-dismissed technical findings. Every report includes a separate
  dismissal section stating these are client-reviewed, not independently verified.
  The original stored report remains unchanged as evidence.
- Client audit export joins events through company-owned engagements, with no 200-row truncation.
  It remains available with expired/revoked contracts. Global login attempts and other companies'
  events are excluded. Hashes are omitted because a filtered export cannot independently validate
  the global chain; admins retain full-chain verification.
- Audit appends obtain a SQLite write lock before reading the chain head to prevent concurrent
  writers from creating branches. Review, restore, revocation and purge operations commit with their events.
- Policy evidence must be a nonempty verbatim quote (case/whitespace insensitive), not just a matching
  prefix. Invalid Q&A source numbers and malformed explanation JSON trigger safe fallback behavior.

## Retention

`python scripts/cleanup.py` expires contracts and removes scan rows and encrypted review reasons on
or after day 30 following `valid_to`, or day 30 following a recorded revocation, whichever is earlier.
UTC dates are used for cleanup. Active/unexpired contracts and records 29 days after ending are retained.
Repeated cleanup is safe; it logs only actual deletions. Audit metadata, contracts and user records remain.
SQLite secure deletion is enabled for these deletes; this is not a promise of physical media erasure.

Legacy AI caches have no company association, so deleting any due scans also invalidates the shared
`ai.json` and `explanations.json` caches conservatively. This may require prewarming other demos again.
The app also clears its cached PDF results after a purge. Other copies (exports, backups, evaluation
outputs and the user's browser/downloads) are not managed by this cleanup.

Cleanup runs on every app script execution. An app that is closed cannot perform scheduled work:
set up a daily OS task for unattended retention.

Windows Task Scheduler:

1. Create a daily task under the same OS account that runs Mutabiq.
2. Program: the full path to `.venv\Scripts\python.exe`.
3. Arguments: the full path to `scripts\cleanup.py`, in quotes if it contains spaces.
4. Start in: the project directory. Preserve `MUTABIQ_DB`/`MUTABIQ_KEY` if your deployment overrides them.
5. Enable "Run task as soon as possible after a scheduled start is missed" and verify the task's history.

Linux example (replace both absolute paths):

```cron
0 2 * * * cd /absolute/path/to/Mutapiq && /absolute/path/to/Mutapiq/.venv/bin/python scripts/cleanup.py
```

No OS task has been installed automatically. Validate backup retention separately.

## Upgrade and acceptance

1. Back up the database and encryption key securely; do not commit or share either.
2. Pull/merge the reviewed change and install dependencies. For tests:
   `python -m pip install -r requirements-dev.txt`.
3. Run `python -m pytest -q`. Tests use temporary databases and encryption keys.
4. Start the app normally. Confirm company audit export, scan, dismiss with reason, restore, Arabic
   display and HTML report. Confirm denied access with a second client.
5. Run `python scripts/cleanup.py` against a disposable test database first; the production command
   permanently removes due results. Install and verify the daily OS task.
6. On the demo laptop with Ollama running, run `python scripts/eval_ai.py`. This needs the exact
   `qwen2.5:7b-instruct` tag, not merely another Qwen variant. It exits 1 for failed checks.
7. After evaluation passes, run `python scripts/prewarm.py` on that same laptop. Its cache is local
   and is not on GitHub. Stricter evidence validation can reveal model failures; review raw eval output.
8. Rehearse and record the actual laptop demonstration. Mocked UI tests are not a backup demo video.

## Still operational, not completed remotely

- Live 53-check model evaluation, prewarming, Windows installer acceptance and full demo recording.
- Sharing the private pitch deck, project documentation and build plan; this requires their actual
  document links, the appropriate connected service and teammate identities.
- Collaborator invitations require the repository owner's/admin's access and teammates' GitHub usernames.
- Review and merge the pull request; the original repository's main branch is not changed automatically.

This completes the listed code backlog, not a production security or legal compliance certification.
Existing demo credentials must not be used for real client data.
