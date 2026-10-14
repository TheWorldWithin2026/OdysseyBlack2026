// tests/research-invariant.test.js
//
// Enforces the Package 1 required invariant: "Raw AI research never reaches
// outreach directly." Run with: node tests/research-invariant.test.js
// (run from the repo root, or adjust the path below).
//
// This is a static-analysis test, not a browser test — it inspects the
// actual source of generateOutreach() in the built index.html and fails if
// that function references any raw-research container. It catches the
// exact class of regression that caused the B- correction ("the approval
// button existed but didn't gate anything") from silently recurring.

const fs = require('fs');
const path = require('path');

const INDEX_PATH = path.join(__dirname, '..', 'index.html');

function extractFunctionSource(content, functionSignature) {
  const startIdx = content.indexOf(functionSignature);
  if (startIdx === -1) return null;
  const braceStart = content.indexOf('{', startIdx);
  let depth = 0, end = -1;
  for (let i = braceStart; i < content.length; i++) {
    if (content[i] === '{') depth++;
    else if (content[i] === '}') { depth--; if (depth === 0) { end = i; break; } }
  }
  if (end === -1) return null;
  return content.slice(startIdx, end + 1);
}

function run() {
  const content = fs.readFileSync(INDEX_PATH, 'utf8');
  const fnSource = extractFunctionSource(content, 'async function generateOutreach()');

  let failures = 0;

  if (!fnSource) {
    console.log('FAIL: could not locate generateOutreach() in index.html');
    process.exit(1);
  }

  const forbidden = ['research-ai', 'research-edit', 'researchState', '.rawText'];
  const violations = forbidden.filter((term) => fnSource.indexOf(term) !== -1);
  if (violations.length) {
    console.log('FAIL: generateOutreach() references forbidden raw-research identifiers: ' + violations.join(', '));
    failures++;
  } else {
    console.log('PASS: generateOutreach() contains none of: ' + forbidden.join(', '));
  }

  const usesApprovedClaimsOnly = fnSource.indexOf('researchClaims.filter') !== -1 && fnSource.indexOf('operator_verified') !== -1;
  if (usesApprovedClaimsOnly) {
    console.log('PASS: generateOutreach() filters researchClaims by operator_verified status');
  } else {
    console.log('FAIL: generateOutreach() does not visibly filter claims by operator_verified status');
    failures++;
  }

  if (failures > 0) {
    console.log(failures + ' failure(s).');
    process.exit(1);
  }
  console.log('All research-invariant tests passed.');
}

run();
