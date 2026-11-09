/**
 * Web app nhận nội dung từ push_gdoc.py và ghi đè tab đầu tiên của Google Doc.
 *
 * Thiết lập: references/gdoc-setup.md. Điền DOC_ID và SECRET bên dưới trước khi deploy
 * (push_gdoc.py --make-gs sinh sẵn bản đã điền).
 */
const DOC_ID = '__DOC_ID__';
const SECRET = '__SECRET__';

const HEADINGS = [
  DocumentApp.ParagraphHeading.NORMAL,
  DocumentApp.ParagraphHeading.HEADING1,
  DocumentApp.ParagraphHeading.HEADING2,
  DocumentApp.ParagraphHeading.HEADING3,
  DocumentApp.ParagraphHeading.HEADING4,
  DocumentApp.ParagraphHeading.HEADING5,
  DocumentApp.ParagraphHeading.HEADING6,
];
const MONO = 'Roboto Mono';
const SHADE = '#f1f3f4';

function doGet() {
  return reply_({ ok: true, ping: true, title: DocumentApp.openById(DOC_ID).getName() });
}

function doPost(e) {
  try {
    const req = JSON.parse(e.postData.contents);
    if (req.secret !== SECRET) return reply_({ ok: false, error: 'unauthorized' });
    const doc = DocumentApp.openById(DOC_ID);
    const body = doc.getBody();
    body.clear();
    req.blocks.forEach(function (b) { render_(body, b); });
    dropLeadingEmpty_(body);
    doc.saveAndClose();
    return reply_({ ok: true, blocks: req.blocks.length, at: new Date().toISOString() });
  } catch (err) {
    return reply_({ ok: false, error: String((err && err.stack) || err) });
  }
}

function render_(body, b) {
  switch (b.type) {
    case 'h': {
      const p = body.appendParagraph(plain_(b.runs));
      p.setHeading(HEADINGS[Math.min(b.level, 6)]);
      style_(p.editAsText(), b.runs);
      break;
    }
    case 'p': {
      const p = body.appendParagraph(plain_(b.runs));
      p.setHeading(DocumentApp.ParagraphHeading.NORMAL);
      style_(p.editAsText(), b.runs);
      if (b.quote) p.setIndentStart(18).setIndentFirstLine(18);
      break;
    }
    case 'code': {
      const p = body.appendParagraph(b.text);
      p.setHeading(DocumentApp.ParagraphHeading.NORMAL);
      if (b.text.length) p.editAsText().setFontFamily(MONO).setFontSize(9).setBackgroundColor(SHADE);
      break;
    }
    case 'list': {
      let first = null;
      b.items.forEach(function (it) {
        const li = body.appendListItem(plain_(it.runs));
        li.setNestingLevel(it.level || 0);
        if (first) li.setListId(first);
        else {
          li.setGlyphType(b.ordered ? DocumentApp.GlyphType.NUMBER : DocumentApp.GlyphType.BULLET);
          first = li;
        }
        style_(li.editAsText(), it.runs);
      });
      break;
    }
    case 'table': {
      const cells = b.rows.map(function (r) { return r.map(plain_); });
      const width = Math.max.apply(null, cells.map(function (r) { return r.length; }));
      cells.forEach(function (r) { while (r.length < width) r.push(''); });
      const table = body.appendTable(cells);
      b.rows.forEach(function (r, i) {
        r.forEach(function (runs, j) {
          const cell = table.getCell(i, j);
          style_(cell.editAsText(), runs);
          if (i === 0 && b.header) {
            cell.setBackgroundColor(SHADE);
            if (cell.getText().length) cell.editAsText().setBold(true);
          }
        });
      });
      break;
    }
    case 'hr':
      body.appendHorizontalRule();
      break;
  }
}

function plain_(runs) {
  return runs.map(function (r) { return r.t; }).join('');
}

// Đoạn mới có thể thừa hưởng định dạng đoạn trước, nên xoá định dạng rồi mới tô theo runs.
function style_(text, runs) {
  if (!text.getText().length) return;
  text.setBold(false).setItalic(false);
  try { text.setLinkUrl(null); } catch (ignored) {}
  try { text.setBackgroundColor(null); } catch (ignored) {}
  let pos = 0;
  runs.forEach(function (r) {
    const n = r.t.length;
    if (!n) return;
    const s = pos;
    const e = pos + n - 1;
    if (r.b) text.setBold(s, e, true);
    if (r.i) text.setItalic(s, e, true);
    if (r.c) text.setFontFamily(s, e, MONO).setBackgroundColor(s, e, SHADE);
    if (r.u) text.setLinkUrl(s, e, r.u);
    pos += n;
  });
}

// body.clear() để lại một đoạn trống ở đầu.
function dropLeadingEmpty_(body) {
  if (body.getNumChildren() < 2) return;
  const first = body.getChild(0);
  if (first.getType() === DocumentApp.ElementType.PARAGRAPH && first.asParagraph().getText() === '') {
    first.removeFromParent();
  }
}

function reply_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
