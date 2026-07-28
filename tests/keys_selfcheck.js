#!/usr/bin/env node
// keys_selfcheck.js — self-check for the shared shortcut dispatcher (#222 web/app/static/keys.js).
//
// It require()s the shipped file (same trick as diff_selfcheck.js and session_selfcheck.js), with a
// DOM stub just large enough for the module to load. What it asserts is the LOGIC that is easy to
// get wrong and invisible in a screenshot:
//
//   - "/" and "?" are the same physical key. If keyOf() ignored shiftKey, the dashboard's
//     search-focus binding would swallow the help sheet and nobody would notice until a user
//     complained that "?" does nothing.
//   - bindings are suppressed inside text fields, EXCEPT the ones that must not be. Getting this
//     backwards means the comment composer eats "c", "a" and "r" as you type.
//   - the help sheet is generated from the registry, so it cannot advertise a binding that is not
//     live, nor omit one that is.
//
// Run: node tests/keys_selfcheck.js   (exit 0 = all cases pass, exit 1 = a case failed)

const path = require('path');

// --- minimal DOM stub -------------------------------------------------------------------------
// keys.js touches document at load only to attach the listener; everything asserted here is pure.
const listeners = {};
global.window = {
  navigator: { platform: 'MacIntel' },
  addEventListener() {},
};
global.document = {
  addEventListener(type, fn) { listeners[type] = fn; },
  getElementById() { return null; },
  createElement() { return { style: {}, setAttribute() {}, appendChild() {}, querySelector: () => null }; },
  head: { appendChild() {} },
  body: { appendChild() {} },
  activeElement: null,
  querySelector() { return null; },
};

const keys = require(path.join(__dirname, '..', 'web', 'app', 'static', 'keys.js'));

let failed = 0;
function check(name, cond, detail) {
  if (cond) { console.log('ok   - ' + name); }
  else { console.log('FAIL - ' + name + (detail ? '  (' + detail + ')' : '')); failed++; }
}

const ev = (over) => Object.assign(
  { key: 'a', shiftKey: false, metaKey: false, ctrlKey: false, target: null }, over);

// 1. THE TRAP. "/" and "?" arrive on the same physical key; e.key already carries the shift.
check('"/" and "?" are distinct specs',
  keys._keyOf(ev({ key: '/' })) === '/' && keys._keyOf(ev({ key: '?', shiftKey: true })) === '?');

// 1b. THE TRAP AS IT ACTUALLY ARRIVED. Cases 1 and 6 asserted the shape I ASSUMED a Shift+/ press
//     produces ("?"), which is what a physical US keyboard sends. Verified in a real browser on
//     staging, a Shift+/ press arrived as {key:"/", code:"Slash", shiftKey:true} — the UNSHIFTED
//     character with the modifier flag. That resolved to "/", so Shift+/ focused the dashboard
//     search box instead of opening the help sheet.
//
//     Both tests above passed the whole time, because both constructed the event themselves. A test
//     that builds its own input can only ever confirm the author's model of that input.
check('Shift+"/" delivered as the UNSHIFTED char still resolves to "?"',
  keys._keyOf(ev({ key: '/', shiftKey: true })) === '?',
  'got ' + keys._keyOf(ev({ key: '/', shiftKey: true })));
check('bare "/" is unaffected by the normalisation',
  keys._keyOf(ev({ key: '/' })) === '/');
check('mod+shift+"/" still carries the modifier',
  keys._keyOf(ev({ key: '/', shiftKey: true, metaKey: true })) === 'mod+?');

// 2. mod is Cmd OR Ctrl, so one spec covers both platforms.
check('meta -> mod+/', keys._keyOf(ev({ key: '/', metaKey: true })) === 'mod+/');
check('ctrl -> mod+/', keys._keyOf(ev({ key: '/', ctrlKey: true })) === 'mod+/');
check('mod+Enter is its own spec', keys._keyOf(ev({ key: 'Enter', metaKey: true })) === 'mod+Enter');

// 3. Shift must NOT be doubled into the spec: e.key is already "?", so a "shift+?" spec could
//    never match anything.
check('shift is not double-counted', keys._keyOf(ev({ key: '?', shiftKey: true })) === '?');

// 4. Field detection drives the suppression rule, so it has to know what a field is.
check('textarea is a field', keys._isField({ tagName: 'TEXTAREA' }) === true);
check('input is a field', keys._isField({ tagName: 'INPUT' }) === true);
check('select is a field', keys._isField({ tagName: 'SELECT' }) === true);
check('contenteditable is a field', keys._isField({ isContentEditable: true }) === true);
check('a button is NOT a field', keys._isField({ tagName: 'BUTTON' }) === false);
check('null target is not a field', keys._isField(null) === false);

// 5. The help binding registers itself and is reachable while typing. If keepInField were false
//    here, the sheet would be unreachable from exactly the situation it exists for.
{
  const help = keys._registry.filter(b => b.keys.includes('?'))[0];
  check('help sheet is registered on both mod+/ and ?',
    !!help && help.keys.includes('mod+/') && help.keys.includes('?'));
  check('help sheet works while typing (keepInField)', !!help && help.keepInField === true);
  check('help sheet has a label, so it appears in its own sheet', !!help && !!help.label);
}

// 6. A binding without a label cannot exist: the sheet is generated from labels, so an unlabelled
//    binding would be a shortcut nobody could discover.
{
  let threw = false;
  try { keys.register([{ keys: 'z', run() {} }]); } catch (e) { threw = true; }
  check('registering without a label throws', threw);
}

// 7. `when` guards hide a binding from the sheet as well as disabling it, so the sheet never
//    advertises something inert.
{
  const before = keys._visible().length;
  keys.register([{ keys: 'F9', label: 'never available', when: () => false, run() {} }]);
  check('a guarded-off binding is hidden from the sheet', keys._visible().length === before);
  keys.register([{ keys: 'F8', label: 'always available', when: () => true, run() {} }]);
  check('a guarded-on binding appears in the sheet', keys._visible().length === before + 1);
}

// 8. Platform rendering: the sheet must show the modifier the user actually has.
check('mod renders as ⌘ on mac', keys._prettify('mod+/') === '⌘/');

console.log(failed ? '\n' + failed + ' case(s) failed' : '\nall key cases pass');
process.exit(failed ? 1 : 0);
