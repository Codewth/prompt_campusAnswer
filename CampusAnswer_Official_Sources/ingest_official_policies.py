"""Download official Bennett PDFs and extract page-aware chunks for CampusAnswer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

import pymupdf
import requests

ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / 'pdfs'
TEXT_DIR = ROOT / 'extracted-text'
PDF_DIR.mkdir(exist_ok=True)
TEXT_DIR.mkdir(exist_ok=True)
sources = json.loads((ROOT / 'sources.json').read_text(encoding='utf-8'))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ocr', action='store_true', help='OCR pages with little or no embedded text')
args = parser.parse_args()
tesseract = os.environ.get('TESSERACT_EXE') or shutil.which('tesseract')
if not tesseract:
    default_tesseract = Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe')
    if default_tesseract.exists():
        tesseract = str(default_tesseract)
if args.ocr and not tesseract:
    raise SystemExit('OCR requested, but Tesseract was not found. Set TESSERACT_EXE or add it to PATH.')
if tesseract:
    os.environ['PATH'] = str(Path(tesseract).parent) + os.pathsep + os.environ.get('PATH', '')
all_chunks = []
report = []

for src in sources:
    path = PDF_DIR / src['file']
    try:
        if not path.exists():
            r = requests.get(src['url'], timeout=60, headers={'User-Agent':'Mozilla/5.0 (CampusAnswer academic prototype)'})
            r.raise_for_status()
            if not r.content.startswith(b'%PDF'):
                raise ValueError('Response was not a PDF')
            path.write_bytes(r.content)
        pdf = pymupdf.open(str(path))
        text_parts = []
        count = 0
        low_text_pages = []
        ocr_pages = []
        for p, page in enumerate(pdf, start=1):
            text = page.get_text('text').strip()
            extraction_method = 'embedded_text'
            if args.ocr and len(text) < 80:
                text_page = page.get_textpage_ocr(language='eng', dpi=250, full=True)
                text = page.get_text('text', textpage=text_page).strip()
                extraction_method = 'ocr'
                if text:
                    ocr_pages.append(p)
            text = re.sub(r'[ \t]+', ' ', text)
            text_parts.append(f'\n\n=== PAGE {p} ===\n{text}')
            if len(text) < 80:
                low_text_pages.append(p)
            # page-local chunks retain page-level citation precision
            words = text.split()
            step, size = 320, 400
            for start in range(0, len(words), step):
                segment = ' '.join(words[start:start+size])
                if not segment:
                    continue
                chunk_id = f"{src['id']}-p{p}-c{start//step+1}"
                all_chunks.append({
                    'id':chunk_id,
                    'document_id':src['id'],
                    'document_title':src['title'],
                    'category':src['category'],
                    'academic_year':src['academic_year'],
                    'page':p,
                    'source_url':src['url'],
                    'source_page':src['source_page'],
                    'extraction_method':extraction_method,
                    'text':segment
                })
                count += 1
        (TEXT_DIR / (src['id'] + '.txt')).write_text(''.join(text_parts), encoding='utf-8')
        status = 'needs_ocr' if low_text_pages else 'extracted'
        report.append({'id':src['id'],'status':status,'pages':len(pdf),'chunks':count,
                       'ocr_pages':ocr_pages,
                       'low_text_pages_need_ocr':low_text_pages,
                       'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        print(f"{status.upper()} {src['id']}: {len(pdf)} pages; {count} chunks; OCR pages={ocr_pages}; remaining low-text pages={low_text_pages}")
    except Exception as exc:
        report.append({'id':src['id'],'status':'error','message':str(exc)})
        print(f"FAILED {src['id']}: {exc}")

with (ROOT / 'rag_chunks.jsonl').open('w', encoding='utf-8') as f:
    for c in all_chunks:
        f.write(json.dumps(c, ensure_ascii=False) + '\n')
(ROOT / 'ingestion_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(f'Complete: {len(all_chunks)} chunks; review ingestion_report.json before indexing.')
if any(item['status'] == 'error' for item in report):
    sys.exit(1)
