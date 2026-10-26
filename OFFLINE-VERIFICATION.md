# Offline verification boundary

Pinned yt-dlp/test/visual dependency graph and versioned synthetic fixture contract.

## Reproduce

`python -m pip install -c requirements-ci.lock ".[test,visual]"; python -m pytest`

No real YouTube collection. Live provider/schema drift requires separately approved network smoke.

## Rollback

Review the commit diff and use a new checkout of the pre-change commit for source rollback. Keep user data and live installations untouched. A source rollback is not permission to restore unsafe network exposure or bypass approval.
