#!/usr/bin/env node
// diff_selfcheck.js — self-check for the shared viewer diff (#19 lineDiff, #207 hunkify).
//
// This used to scrape `function lineDiff` out of web/app/viewer.html by brace-matching and eval it,
// because the function was inline in the page. Since #207 it is a real file that both viewers load
// via a script tag, so we require() it directly: the test now exercises the EXACT bytes the browser
// runs, and "the test drifted from the shipped function" stops being possible rather than merely
// being discouraged.
//
// Run: node tests/diff_selfcheck.js   (exit 0 = all cases pass, exit 1 = a case failed)

const path = require('path');
const { lineDiff, numberRows, hunkify, counts, CONTEXT, MIN_GAP, REVEAL } =
  require(path.join(__dirname, '..', 'web', 'app', 'static', 'linediff.js'));

const tags = rows => rows.map(r => r.tag).join('');

let failed = 0;
function check(name, cond, detail) {
  if (cond) { console.log('ok   - ' + name); }
  else { console.log('FAIL - ' + name + (detail ? '  (' + detail + ')' : '')); failed++; }
}

// ---------------------------------------------------------------- lineDiff (unchanged behaviour)

// 1. Identical input -> every row unchanged, no add/del.
{
  const r = lineDiff('a\nb\nc', 'a\nb\nc');
  check('identical -> all unchanged', tags(r) === '   ', 'tags="' + tags(r) + '"');
}

// 2. Pure insertion: one line added in the middle.
{
  const r = lineDiff('a\nc', 'a\nb\nc');
  check('pure insert -> exactly one +', tags(r).replace(/ /g, '') === '+', 'tags="' + tags(r) + '"');
  const added = r.filter(x => x.tag === '+').map(x => x.text);
  check('inserted line is "b"', added.length === 1 && added[0] === 'b', added.join('|'));
}

// 3. Pure deletion: one line removed.
{
  const r = lineDiff('a\nb\nc', 'a\nc');
  check('pure delete -> exactly one -', tags(r).replace(/ /g, '') === '-', 'tags="' + tags(r) + '"');
  const del = r.filter(x => x.tag === '-').map(x => x.text);
  check('deleted line is "b"', del.length === 1 && del[0] === 'b', del.join('|'));
}

// 4. Interleaved change: a line replaced (delete old + insert new), context preserved.
{
  const r = lineDiff('title\nold body\nend', 'title\nnew body\nend');
  const kept = r.filter(x => x.tag === ' ').map(x => x.text);
  check('replacement keeps unchanged context', kept.join('|') === 'title|end', kept.join('|'));
  check('replacement drops old line', r.some(x => x.tag === '-' && x.text === 'old body'), '');
  check('replacement adds new line', r.some(x => x.tag === '+' && x.text === 'new body'), '');
  // Reconstruction invariants: '-'+' ' rows rebuild A; '+'+' ' rows rebuild B.
  const a = r.filter(x => x.tag !== '+').map(x => x.text).join('\n');
  const b = r.filter(x => x.tag !== '-').map(x => x.text).join('\n');
  check('rows reconstruct A', a === 'title\nold body\nend', a);
  check('rows reconstruct B', b === 'title\nnew body\nend', b);
}

// 5. Empty vs non-empty: everything is an insertion (from a single empty line).
{
  const r = lineDiff('', 'x\ny');
  const b = r.filter(x => x.tag !== '-').map(x => x.text).join('\n');
  check('empty->content reconstructs B', b === 'x\ny', b);
}

// ---------------------------------------------------------------- numberRows

// 6. A removed line carries no NEW number and an added line carries no OLD one — that asymmetry is
//    what tells a reader which side of the change they are looking at.
{
  const r = numberRows(lineDiff('a\nold\nz', 'a\nnew\nz'));
  const del = r.find(x => x.tag === '-'), add = r.find(x => x.tag === '+');
  check('deleted row has an old number and no new one', del.a === 2 && del.b === null, JSON.stringify(del));
  check('added row has a new number and no old one', add.b === 2 && add.a === null, JSON.stringify(add));
  const last = r[r.length - 1];
  check('trailing context is numbered on both sides', last.a === 3 && last.b === 3, JSON.stringify(last));
}

// ---------------------------------------------------------------- hunkify (#207, the new code)

const lines = n => Array.from({ length: n }, (_, i) => 'line ' + (i + 1)).join('\n');
const seg = segs => segs.map(s => (s.vis ? 'V' : 'H') + s.rows.length).join(',');

// 7. No changes -> one visible segment, nothing collapsed. (A caller shows "no changes" instead,
//    but hunkify must not invent a fold for a document that never changed.)
{
  const s = hunkify(numberRows(lineDiff(lines(40), lines(40))));
  check('unchanged document collapses to a single run', s.length === 1, seg(s));
}

// 8. The headline case: a one-line edit in a long document must NOT render the whole document.
{
  const a = lines(60);
  const b = a.replace('line 30', 'line 30 EDITED');
  const rows = numberRows(lineDiff(a, b));
  const s = hunkify(rows);
  const visible = s.filter(x => x.vis).reduce((n, x) => n + x.rows.length, 0);
  // 2 changed rows (one -, one +) + CONTEXT either side.
  check('one edit in 60 lines keeps only the hunk visible',
        visible === 2 + CONTEXT * 2, 'visible=' + visible + ' segs=' + seg(s));
  check('the rest is collapsed, not dropped',
        s.reduce((n, x) => n + x.rows.length, 0) === rows.length, 'total mismatch');
  check('collapsed gaps exist on both sides', s.filter(x => !x.vis).length === 2, seg(s));
}

// 9. Context is exactly CONTEXT lines either side.
{
  const a = lines(30), b = a.replace('line 15', 'line 15 EDITED');
  const s = hunkify(numberRows(lineDiff(a, b)));
  const vis = s.find(x => x.vis);
  const lead = vis.rows.slice(0, CONTEXT).every(r => r.tag === ' ');
  const tail = vis.rows.slice(-CONTEXT).every(r => r.tag === ' ');
  check('hunk is padded with CONTEXT unchanged lines each side', lead && tail,
        vis.rows.map(r => r.tag).join(''));
}

// 10. A gap SHORTER than MIN_GAP is not collapsed: hiding two lines behind a click costs the reader
//     more than it saves, so those lines stay inline and the two hunks read as one.
{
  const a = lines(40);
  const b = a.replace('line 10', 'line 10 EDITED').replace('line 18', 'line 18 EDITED');
  const s = hunkify(numberRows(lineDiff(a, b)));
  const inner = s.slice(1, -1);                       // ignore the leading/trailing collapsed runs
  check('a sub-MIN_GAP gap between two edits is not collapsed',
        inner.every(x => x.vis), seg(s));
  check('and the two hunks merge into one visible run', inner.length === 1, seg(s));
}

// 11. A wider gap IS collapsed — otherwise the whole point of hunking is lost.
{
  const a = lines(60);
  const b = a.replace('line 10', 'line 10 EDITED').replace('line 40', 'line 40 EDITED');
  const s = hunkify(numberRows(lineDiff(a, b)));
  const mids = s.slice(1, -1);
  check('a gap of MIN_GAP or more between edits collapses',
        mids.some(x => !x.vis && x.rows.length >= MIN_GAP), seg(s));
}

// 12. Never two adjacent visible segments — a promoted short gap must merge into the run before it,
//     or the renderer would draw a seam where the document has none.
{
  const a = lines(50);
  const b = a.replace('line 10', 'X').replace('line 15', 'Y').replace('line 20', 'Z');
  const s = hunkify(numberRows(lineDiff(a, b)));
  let adjacent = false;
  for (let i = 1; i < s.length; i++) if (s[i].vis && s[i - 1].vis) adjacent = true;
  check('no two visible segments are adjacent', !adjacent, seg(s));
}

// 13. Every row survives hunkify exactly once and in order — collapsing must never lose content.
{
  const a = lines(80);
  const b = a.replace('line 5', 'A').replace('line 40', 'B').replace('line 79', 'C');
  const rows = numberRows(lineDiff(a, b));
  const flat = hunkify(rows).reduce((acc, s) => acc.concat(s.rows), []);
  check('hunkify preserves every row, in order',
        flat.length === rows.length && flat.every((r, i) => r === rows[i]),
        flat.length + ' vs ' + rows.length);
}

// 14. Options are overridable, so a future caller (a narrow pane, say) can retune without forking.
{
  const a = lines(40), b = a.replace('line 20', 'EDITED');
  const wide = hunkify(numberRows(lineDiff(a, b)), { context: 6 });
  const vis = wide.filter(x => x.vis).reduce((n, x) => n + x.rows.length, 0);
  check('context is overridable via opts', vis === 2 + 6 * 2, 'visible=' + vis);
}

// ---------------------------------------------------------------- counts + constants

// 15. counts drives the toggle's hint badge, so it must match the rows exactly.
{
  const c = counts(lineDiff('a\nb\nc', 'a\nB\nc\nd'));
  check('counts reports adds and dels', c.add === 2 && c.del === 1 && c.changed === 3, JSON.stringify(c));
  check('counts of an unchanged pair is zero', counts(lineDiff('x', 'x')).changed === 0, '');
}

// 16. The constants are the contract with both viewers; pin them so a silent tweak fails here.
{
  check('constants match VS Code defaults (3/3/20)',
        CONTEXT === 3 && MIN_GAP === 3 && REVEAL === 20,
        CONTEXT + '/' + MIN_GAP + '/' + REVEAL);
}

if (failed) { console.error('\n' + failed + ' case(s) failed'); process.exit(1); }
console.log('\nAll diff self-checks passed.');
