# Runbook: unowned-record custody reconciliation (#113) + the tripwire (#361 / #114)

Every `owner == ""` record on the live instance is a document nobody has been confirmed to own.
`reviews.can_access` fails CLOSED on it (`o = self.owner(rid); return bool(o) and o == uid`, in
`src/mdreview/reviews.py`), so an unowned record is already unreadable by anyone. That is the
safe state; this runbook does not change it. What it does is give each unowned record a real,
human-confirmed disposition, owned or deliberately left unowned, so #114's tripwire has a
trustworthy baseline instead of alarming on every legacy record on day one.

**Who runs this: the owner, at a terminal with a real shell on Kapture (`ssh kapture`).** Not the
restricted `agent` account: `infra/deploy/agent/dispatch.sh` allows exactly `logs | ps | status |
health | drift-check`, no `docker exec` verb, so it cannot even run the read-only dry run. Not an
autonomous run either: `docs/process/autonomous-run.md` excludes "anything touching production
data" and "a decision the owner has not already made". Binding an owner to a record is a human
judgement call by design (section 3 below); there is no agent-safe path through this procedure,
and there should not be one.

**Fail-closed is a build property, not a flag.** The hosted image's composition root
(`src/mdreview/hosted/compose.py`) is reached only by `python -m mdreview.hosted`, the hosted
Docker image's `CMD`. There is no env var in that path that yields the open `OperatorIdentity` /
`OpenPolicy` combination the local tier uses: a hosted build is structurally incapable of serving
with the ownership check off. This runbook exists because that guarantee only closes off *new*
open records; it says nothing about records that were already unowned before this build shipped.
Reconciling those is a one-time, human-run operation, not something the build can do for you.

## Prereqs

- `ssh kapture` access (the owner's account, not `kapture-agent`).
- The live deploy dir is `~/mdreview-deploy`, container `mdreview`, data volume
  `mdreview-deploy_mdreview-prod` (per `RUNBOOK-phase1.md`'s "Deploy integrity" section; confirm
  with `docker inspect mdreview --format '{{range .Mounts}}{{.Name}} {{.Destination}}{{"\n"}}{{end}}'`
  if in doubt).
- `src/mdreview/reconcile.py` is already in the running image (`docker exec mdreview python -m
  mdreview.reconcile list` is runnable today, verified against `origin/dev` during #113 grooming,
  no rebuild or redeploy needed to run this).

## 1. Snapshot first

Take a tarball of the live data volume with a throwaway container, so the volume is never mounted
read-write by anything except the running app during the snapshot:

```bash
ssh kapture
mkdir -p ~/mdreview-backups && cd ~/mdreview-backups
TS=$(date -u +%FT%TZ)
docker run --rm \
  -v mdreview-deploy_mdreview-prod:/data:ro \
  -v "$PWD":/backup \
  alpine tar czf /backup/mdreview-data-${TS}.tar.gz -C /data .
```

**Verify the snapshot is good before touching anything else.** A corrupt or partial archive
discovered only at rollback time is not a backup:

```bash
# 1. the archive lists cleanly (a truncated/corrupt gzip fails this with a non-zero exit)
tar tzf mdreview-data-${TS}.tar.gz > /dev/null && echo "archive readable"

# 2. record count in the snapshot matches the live volume. DATA_DIR holds more than review
#    records (identity.db, shares.db on a hosted build), so count the SAME thing on both sides:
#    directories that contain a meta.json, never a bare listing of everything under /data.
docker exec mdreview sh -c 'ls -1 /data/*/meta.json 2>/dev/null | wc -l'   # live record count
tar tzf mdreview-data-${TS}.tar.gz | grep -c '/meta.json$'                # snapshot record count
#   -> the two numbers MUST match. If they don't, do not proceed: re-run the snapshot.
```

The snapshot is taken while the app keeps running; no downtime is needed for this direction.
Every `meta.json` write goes through `store.write_text` (`os.replace` under `store.lock`), so it
is always written whole or not at all: a snapshot mid-write never captures a torn file. A record
whose creation races the exact snapshot moment may simply be absent from the archive, which is
fine since it did not exist as far as this reconciliation pass is concerned.

`chmod 600 mdreview-data-${TS}.tar.gz`: it is a full copy of every review's content. Keep it
until this procedure and its rollback window are both closed out.

## 2. Dry run: list the unowned records

Read-only. Changes nothing. This is `reconcile.py`'s `_cmd_list`, the de-facto dry run:

```bash
docker exec mdreview python -m mdreview.reconcile list
```

Output shape (verified against a synthetic fixture with one already-quarantined record, one
record with provenance hints, and one with none):

```
3 unowned record(s): 2 awaiting review, 1 quarantined (human-reviewed, left unowned).

AWAITING REVIEW. Provenance below is ATTACKER-CONTROLLED and UNTRUSTED -- a hint for
a human to corroborate, never a machine suggestion. Decide each with:
    python -m mdreview.reconcile confirm <rid> <owner_id>
    python -m mdreview.reconcile quarantine <rid>

rid:         eeee000005
  title:       no-provenance-orphan
  UNTRUSTED hint  project=''  source_path=''  session=''
  (no provenance -- no hint; requires explicit human assignment)

rid:         dddd000004
  title:       hamzas-doc
  UNTRUSTED hint  project='literator'  source_path='/home/hamza/literator/model.ipynb'  session=''

QUARANTINED (custody_reviewed_at set; deliberately unowned, still inaccessible):

rid:         cccc000003
  title:       unowned-quarantined-already
  custody_reviewed_at: 1700000003
```

Every row under "AWAITING REVIEW" needs one of the two commands in section 4. Rows under
"QUARANTINED" were already handled in an earlier pass; leave them alone (re-running `list` is
always safe: it never writes).

Note what `list` does NOT give you: a suggested owner. That is deliberate; read on.

## 3. Why a human confirms each binding

`reconcile.py` shows a record's `project` / `source_path` / `session` fields as a hint and
nothing more. It deliberately does not compute a candidate owner from them, and there is no
command that binds more than one record at a time. This is the design, not a gap still to be
filled in.

The reason is #97: on 2026-07-22, `mdreview.migrate` blind-stamped every `owner == ""` record to
one uid during a back-fill. Four of the five records it touched were correctly the owner's; the
fifth was a foreign researcher's document, created during an auth-off window, that the back-fill
handed to a stranger with no provenance check at all. The owner could read someone else's
document; its actual author was locked out of his own work. The failure was not bad luck in
which five records existed that day: it was a tool that treated "unowned" and "belongs to
whoever runs the migration" as the same fact. Any tool that maps provenance strings to a
`provider:sub` and writes it, even a well-intentioned "suggested owner" a human can accept with
one keystroke, reintroduces the same failure with extra steps: a tired operator rubber-stamps
the suggestion, and the untrusted string is now laundered into an authoritative-looking binding.
`confirm <rid> <owner_id>` requires the owner id to be typed on the command line, per record.
That keystroke, not a computed match, is what "confirmed" means here.

Practically: read the `project` / `source_path` / `session` hint, use it to figure out who the
record actually belongs to (ask them if you're not sure), and only then run `confirm` with that
person's `provider:sub`. If nothing points to an owner, `quarantine` it: see below.

## 4. Applying the bindings

Two commands, both per-record, both requiring an explicit id on the command line:

```bash
# bind a record to a known owner (provider:sub, e.g. github:12345, google:10070...)
docker exec mdreview python -m mdreview.reconcile confirm <rid> <owner_id>

# leave a record deliberately unowned (nobody claims it, or you cannot determine an owner):
# stamps custody_reviewed_at so #114's tripwire will not alarm on it later, writes nothing else
docker exec mdreview python -m mdreview.reconcile quarantine <rid>
```

Both refuse loudly rather than doing something silently wrong (verified against a fixture):

```
$ python -m mdreview.reconcile confirm dddd000004 github:2
refused: record dddd000004 already owned by github:1; refusing to re-key (no bulk, no overwrite)

$ python -m mdreview.reconcile confirm cccc000003 12345
refused: owner id must be provider:sub (both non-empty), got: '12345'

$ python -m mdreview.reconcile quarantine dddd000004
refused: record dddd000004 is owned by github:1; quarantine applies only to unowned records
```

If the owner id you type is not yet a provisioned user, `confirm` still binds it but warns.
This is not a block, since the legitimate owner may simply not have signed in yet:

```
$ python -m mdreview.reconcile confirm eeee000005 github:999
bound: record eeee000005 -> owner github:999  [WARNING: owner is not a known user -- verify the id is correct]
```

Treat that warning as a prompt to double-check the id, not as permission to ignore it.

**Verify the record count moved as expected.** Run `list` again after each batch and confirm the
"awaiting review" count dropped by exactly the number of records you just confirmed or
quarantined, and that the rids you just handled no longer appear under "AWAITING REVIEW":

```bash
docker exec mdreview python -m mdreview.reconcile list
```

Repeat sections 2 to 4 until `list` prints `no unowned records: nothing to reconcile.` or every
remaining row is under "QUARANTINED".

There is no separate log file recording which records this pass touched: `custody_reviewed_at` on
each record's own `meta.json` IS that record (stamped by both `confirm` and `quarantine`). Section
6's tripwire reads that same field to tell "reviewed" from "never looked at", so finishing this
loop for every "AWAITING REVIEW" row is what makes the baseline complete; there is nothing further
to write down.

## 5. Rollback

`confirm` and `quarantine` each touch exactly one record's `meta.json`, under `store.lock`, and
never overwrite an already-owned record. There is no `unconfirm` command: that is on purpose, so
the "never re-key" refusal in section 4 cannot be routed around by a script that confirms,
discovers a mistake, and re-confirms.

**A single wrong binding (wrong owner typed):** extract just that one record's `meta.json` from
the section 1 snapshot, which resets it to its pre-reconciliation state (`owner` back to `""`,
`custody_reviewed_at` back to unset), then re-run `confirm` with the correct id. This also
reverts any other field of that one record that changed since the snapshot was taken, which for a
legacy unowned record is normally nothing:

```bash
docker run --rm \
  -v mdreview-deploy_mdreview-prod:/data \
  -v ~/mdreview-backups:/backup \
  alpine tar xzf /backup/mdreview-data-${TS}.tar.gz -C /data ./<rid>/meta.json
docker exec mdreview python -m mdreview.reconcile confirm <rid> <correct_owner_id>
```

**Anything larger** (a bad batch, a script gone wrong, uncertainty about what actually got
written): restore the whole volume from the section 1 snapshot. Resolve the exact snapshot file
and confirm it is readable BEFORE touching the volume, so a typo'd or missing filename fails on
the harmless `tar tzf` check and never reaches the step that empties `/data`:

```bash
ssh kapture
ls -la ~/mdreview-backups/                        # find the snapshot you're restoring from
SNAP=~/mdreview-backups/mdreview-data-<TS>.tar.gz  # the one you're restoring, in full
tar tzf "$SNAP" > /dev/null && echo "archive readable"    # MUST print before continuing

cd ~/mdreview-deploy
docker compose -f docker-compose.prod.yml --env-file .env stop mdreview

docker run --rm \
  -v mdreview-deploy_mdreview-prod:/data \
  -v ~/mdreview-backups:/backup \
  alpine sh -c 'rm -rf /data/* /data/.[!.]* 2>/dev/null && tar xzf "/backup/'"$(basename "$SNAP")"'" -C /data'

docker compose -f docker-compose.prod.yml --env-file .env up -d mdreview
docker logs --tail 20 mdreview                                   # must show a clean boot
docker exec mdreview python -m mdreview.reconcile list           # back to the pre-reconciliation state
```

The `rm -rf ... && tar xzf ...` join is deliberate: if the wipe ever fails, the restore step does
not run and `/data` is left in whatever state the failed wipe left it, not silently "restored"
from an archive that was never extracted.

## 6. The tripwire

`scripts/custody_tripwire.py` (#361) reports records matching the unowned-and-unreviewed
predicate (`owner == ""` AND `custody_reviewed_at` unset) by delegating to
`Reconciler.unowned()`, the same predicate `reconcile.py list`'s "AWAITING REVIEW" section uses,
so the two can never drift apart. It is read-only and never writes a record. The exit code IS the
signal: `0` clean, `1` one or more findings, `2` a usage error (missing/bad argument, not a
finding).

```bash
python3 scripts/custody_tripwire.py <data_dir>
```

`<data_dir>` is a required argument with no default and no `$MDREVIEW_DATA` fallback, so it can
never silently resolve to whatever data dir happens to be in the caller's environment: you always
say explicitly what you're scanning. Verified against a synthetic fixture:

```
$ python3 scripts/custody_tripwire.py fixture
custody tripwire: 2 unowned-and-unreviewed record(s) in fixture
  rid: eeee000005  title='no-provenance-orphan'  created=5
  rid: dddd000004  title='hamzas-doc'  created=4
$ echo $?
1

# after every AWAITING REVIEW record from section 2 is confirmed or quarantined:
$ python3 scripts/custody_tripwire.py fixture
custody tripwire: clean (0 unowned-and-unreviewed records in fixture)
$ echo $?
0
```

**What a finding means:** a record exists with no owner that no human has ever looked at through
`reconcile.py`. Before this runbook has been run once against prod, that is expected: the whole
legacy corpus is `custody_reviewed_at`-unset by construction, which is exactly why arming this
against production is gated on #113 (this runbook) completing first (#114, "6b", tracks that; it
stays `status:blocked` until every legacy record has a disposition). After that point, any finding
is a NEW unowned record: something created an `owner == ""` record post-reconciliation, which
should not happen on a hosted build (section "Fail-closed is a build property" above). Treat it
as a signal to investigate, not to reconcile it in place from the tripwire's output.

**What to do about a finding**, once the tripwire is armed against prod: run this runbook's
sections 2 and 4 against the one new record. Read its provenance hint, confirm it to its actual
owner or quarantine it deliberately, re-run the tripwire, confirm it's clean, and separately
figure out how an `owner == ""` record got created on a build that is supposed to be structurally
incapable of that, because that is the actual bug, not the record.

**Current scope (as of this writing):** the tripwire script and its self-check
(`tests/custody_tripwire_selfcheck.py`) exist and are gated in `pr-checks.yml`, exercised only
against a synthetic fixture (#361, "slice 6a"). It is not armed against any data directory by
default and not wired into a schedule. Arming it against the live `mdreview-deploy_mdreview-prod`
volume ("slice 6b") is #114, and stays blocked until every record surfaced by section 2 of this
runbook has a disposition: a tripwire that fires on records nobody has reconciled yet is noise,
and a tripwire that cries wolf gets ignored.
