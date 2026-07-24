#!/usr/bin/env node
// diff_selfcheck.js — self-check for the History-modal compare diff (#19).
//
// The viewer's `lineDiff(a,b)` is a pure LCS line diff (no DOM/globals), so we can extract its
// source straight out of web/app/viewer.html and exercise it here — no browser needed. Extract,
// don't copy: a pasted copy would silently drift from the shipped function.
//
// Run: node tests/diff_selfcheck.js   (exit 0 = all cases pass, exit 1 = a case failed)

const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'web', 'app', 'viewer.html'), 'utf8');

// Pull `function lineDiff(...){ ... }` by brace-matching from the declaration.
const start = html.indexOf('function lineDiff');
if (start < 0) { console.error('FAIL: lineDiff not found in viewer.html'); process.exit(1); }
let i = html.indexOf('{', start), depth = 0, end = -1;
for (; i < html.length; i++) {
  const c = html[i];
  if (c === '{') depth++;
  else if (c === '}') { depth--; if (depth === 0) { end = i + 1; break; } }
}
if (end < 0) { console.error('FAIL: could not brace-match lineDiff body'); process.exit(1); }
const src = html.slice(start, end);

// eslint-disable-next-line no-eval
const lineDiff = eval('(' + src + ')');

const tags = rows => rows.map(r => r.tag).join('');
const texts = rows => rows.map(r => r.text);

let failed = 0;
function check(name, cond, detail) {
  if (cond) { console.log('ok   - ' + name); }
  else { console.log('FAIL - ' + name + (detail ? '  (' + detail + ')' : '')); failed++; }
}

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

if (failed) { console.error('\n' + failed + ' case(s) failed'); process.exit(1); }
console.log('\nAll diff self-checks passed.');
