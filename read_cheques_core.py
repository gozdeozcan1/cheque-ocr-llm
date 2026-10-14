from pathlib import Path
from PIL import Image, ImageOps
import argparse
import hashlib
import os
import csv
import io
import json
from datetime import datetime
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
IMAGE_DIR = ROOT / 'data' / 'images'
OUTPUT_DIR = ROOT / 'outputs'
REGIONS = {
    'address': (0.0, 0.065, 0.38, 0.245),
    'fractional_routing': (0.89, 0.19, 1.0, 0.28),
    'date': (0.59, 0.18, 0.85, 0.30),
    'check_number': (0.91, 0.075, 1.0, 0.155),
    'payee': (0.12, 0.32, 0.54, 0.435),
    'amount': (0.83, 0.34, 1.00, 0.42),
    'written_amount': (0.01, 0.435, 0.815, 0.55),
    'memo': (0.045, 0.70, 0.49, 0.845),
    'signature': (0.55, 0.66, 0.94, 0.87),
    'routing': (0.035, 0.83, 0.239, 0.90),
    'account': (0.265, 0.83, 0.471, 0.90),
}


def find_tesseract():
    windows_path = Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe')
    if windows_path.is_file():
        return str(windows_path)
    executable = shutil.which('tesseract')
    if executable:
        return executable
    raise RuntimeError('Tesseract bulunamadı. Kurulum yolunu find_tesseract içinde düzelt.')


def normalize(field, text):
    if field not in ('date', 'amount', 'check_number', 'routing', 'routing_printed', 'account'):
        return ' '.join(text.split()).strip(' |_=—-.')
    return ''.join(text.split())


def candidate_score(field, text, confidence):
    score = confidence
    value = normalize(field, text)
    if field == 'amount':
        score += 35 if re.fullmatch(r'\d+\.\d{2}', value) else -35
    elif field == 'date':
        try:
            datetime.strptime(value, '%m/%d/%Y')
            score += 25
        except ValueError:
            score -= 35
        if re.fullmatch(r'\d{2}/\d{2}/\d{4}', value):
            score += 10
    if field in ('routing', 'routing_printed'):
        score += 25 if re.fullmatch(r'\d{9}', value) else -25
    if not value:
        score -= 100
    return score


def select_candidate(field, candidates):
                                                                            
                                                             
    support = {}
    for item in candidates:
        value = normalize(field, item['text'])
        support.setdefault(value, set()).add(item['variant'])
    return max(candidates, key=lambda item: (
        item['score'], len(support[normalize(field, item['text'])])))


def read_field(executable, crop, field, debug_path):
                                                                     
    variants = [('gray', crop), ('contrast', ImageOps.autocontrast(crop))]
    for threshold in (90, 110, 130):
        variants.append((f'threshold_{threshold}',
                         crop.point(lambda pixel, t=threshold: 255 if pixel > t else 0)))
    candidates = []
    with tempfile.TemporaryDirectory(prefix='cheque_ocr_') as directory:
        path = Path(directory) / 'crop.png'
        for variant_name, variant in variants:
            variant = ImageOps.expand(variant, border=15, fill=255)
            variant.save(path)
            for psm in (('6',) if field in ('address', 'fractional_routing') else ('7', '13') if field in ('payee', 'signature') else ('7', '13') if field in ('date', 'amount') else ('7',)):
                args = [executable, str(path), 'stdout', '-l', 'eng', '--psm', psm]
                if field == 'date':
                    args += ['-c', 'tessedit_char_whitelist=0123456789/']
                elif field == 'amount':
                    args += ['-c', 'tessedit_char_whitelist=0123456789.,']
                elif field in ('routing', 'routing_printed', 'account', 'check_number'):
                    args += ['-c', 'tessedit_char_whitelist=0123456789']
                args += ['tsv']
                try:
                    result = subprocess.run(args, capture_output=True, text=True,
                                            encoding='utf-8', errors='replace', timeout=20)
                except subprocess.TimeoutExpired:
                    continue
                if result.returncode:
                    continue
                words = []
                confidences = []
                for item in csv.DictReader(io.StringIO(result.stdout), delimiter='\t'):
                    word = (item.get('text') or '').strip()
                    confidence = float(item.get('conf') or '-1')
                    if word and confidence >= 0:
                        words.append(word)
                        confidences.append(confidence)
                text = ' '.join(words)
                confidence = sum(confidences) / len(confidences) if confidences else 0
                candidates.append(dict(variant=variant_name, psm=psm, text=text,
                                       confidence=round(confidence, 2),
                                       score=candidate_score(field, text, confidence)))
    debug_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding='utf-8')
    if not candidates:
        raise RuntimeError('Hiçbir OCR denemesi tamamlanamadı.')
    if field == 'account':
                                                                                            
        return next(item['text'] for item in candidates if item['variant'] == 'gray')
    return select_candidate(field, candidates)['text']


def detect_micr_symbols(c):
 pixels=c.load();seen=set();boxes=[];all_boxes=[]
 for y in range(c.height):
  for x in range(c.width):
   if (x,y) in seen or pixels[x,y]>=100:continue
   stack=[(x,y)];seen.add((x,y));x1=x2=x;y1=y2=y;area=0
   while stack:
    a,b=stack.pop();area+=1;x1=min(x1,a);x2=max(x2,a);y1=min(y1,b);y2=max(y2,b)
    for n,m in [(a-1,b),(a+1,b),(a,b-1),(a,b+1)]:
     if 0<=n<c.width and 0<=m<c.height and (n,m) not in seen and pixels[n,m]<100:seen.add((n,m));stack.append((n,m))
   if area>=12:all_boxes.append((x1,y1,x2,y2))
   if 15<=area<=180 and 3<=x2-x1<=14 and 3<=y2-y1<=14:boxes.append((x1,y1,x2,y2))
 bars=[(a[0],a[2]) for a in all_boxes if a[2]-a[0]<=6 and a[3]-a[1]>=17]
 pairs=[]
 for a in boxes:
  for b in boxes:
   if abs(a[0]-b[0])<=4 and 10<=b[1]-a[1]<=30:pairs.append((min(a[0],b[0]),max(a[2],b[2])))
 return sorted(set(pairs)),bars

def bank_crops(gray):
    width, height = gray.size
                                                                           
    line = gray.crop((0, round(height * .83), round(width * .65), round(height * .91)))
    dots, bars = detect_micr_symbols(line)
    dots = [pair for pair in dots if .20 * width < pair[0] < .34 * width]
    result = {}
    if dots:
        left = dots[0]
        all_dots, _ = detect_micr_symbols(line)
        endings = [pair[0] for pair in all_dots if pair[0] > left[1] + width * .08]
        for a, b in zip(sorted(bars), sorted(bars)[1:]):
            if a[0] > left[1] + width * .08 and 3 <= b[0] - a[0] <= 15:
                endings.append(a[0])
        if endings:
            right = min(endings)
            result['account'] = line.crop((left[1] + 5, 0, right - 5, line.height))
                                                
        result['routing'] = line.crop((round(width * .034), 0, left[0] - 5, line.height))
    return result


def resize_crop(crop):
    return crop.resize((crop.width * 3, crop.height * 3), Image.Resampling.BICUBIC)


FIELDS = tuple(REGIONS)
CORE_FIELDS = ('date', 'payee', 'amount')
COLUMNS = ['filename', 'image_sha256', 'source_present', 'status', 'error',
           'routing_bottom_raw', 'routing_printed_raw', 'routing_sources_agree', 'account_boundary_detected']
for field in FIELDS:
    COLUMNS += [field + '_raw', field, field + '_verified', field + '_reviewed']


def load_rows(path):
    if not path.exists():
        return {}
    with path.open(encoding='utf-8-sig', newline='') as file:
        sample = file.read(4096)
        file.seek(0)
        delimiter = ';' if sample.splitlines()[0].count(';') > sample.splitlines()[0].count(',') else ','
        rows = {}
        for item in csv.DictReader(file, delimiter=delimiter):
            filename = item.get('filename')
            if not filename or filename in rows:
                raise ValueError('CSV içinde boş veya tekrarlanan filename var. İşlem durduruldu.')
            rows[filename] = item
        return rows


def write_csv(path, columns, rows):
                                                         
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', newline='',
                                     dir=path.parent, delete=False, suffix='.csv') as file:
        temporary = Path(file.name)
        writer = csv.DictWriter(file, fieldnames=columns, delimiter=';', extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def valid_value(field, value):
    if field == 'date':
        if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', value):
            return False
        try:
            datetime.strptime(value, '%m/%d/%Y')
        except ValueError:
            return False
    elif field == 'amount':
        return bool(re.fullmatch(r'\d+\.\d{2}', value))
    elif field == 'payee':
        return bool(value.strip())
    return True


def review_status(row):
    if row.get('source_present') != '1':
        return 'source_missing'
    if row.get('error'):
        return 'error'
    for field in CORE_FIELDS:
        value = row.get(field + '_verified', '').strip()
        if row.get(field + '_reviewed', '').strip() != '1' or not valid_value(field, value):
            return 'review'
    return 'verified'


def main():
    parser = argparse.ArgumentParser(description='100 farklı çek üzerinde tarih, alıcı ve tutar OCR denemesi.')
    parser.add_argument('--images', type=Path, default=IMAGE_DIR)
    parser.add_argument('--selection', type=Path, default=OUTPUT_DIR / 'cheque_unique_100.csv')
    parser.add_argument('--outputs', type=Path, default=OUTPUT_DIR / 'core_ocr')
    parser.add_argument('--limit', type=int, default=0, help='İlk deneme için örneğin 10; 0 tüm seçim.')
    args = parser.parse_args()
    if args.limit < 0:
        parser.error('--limit negatif olamaz.')
    selection = load_rows(args.selection)
    if not selection:
        raise FileNotFoundError(f'Seçim CSV bulunamadı veya boş: {args.selection}')
    args.outputs.mkdir(parents=True, exist_ok=True)
    executable = find_tesseract()
    rows = []
    seen = set()
    columns = ['filename', 'image_sha256', 'status', 'error']
    for field in CORE_FIELDS:
        columns += [field + '_previous', field + '_raw', field, field + '_confidence',
                    field + '_alternatives', field + '_review_reason']
    result_path = args.outputs / 'cheque_core_results.csv'
    if result_path.exists():
        shutil.copy2(result_path, args.outputs / ('backup_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.csv'))
    for name, previous in selection.items():
        if args.limit and len(rows) >= args.limit:
            break
        row = dict.fromkeys(columns, '')
        row['filename'] = name
        for field in CORE_FIELDS:
            row[field + '_previous'] = previous.get(field, '')
        try:
            if Path(name).name != name:
                raise ValueError('filename yalnızca dosya adı içermeli.')
            path = args.images / name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            row['image_sha256'] = digest
            if previous.get('image_sha256') and digest != previous['image_sha256']:
                raise ValueError('Görsel hash değeri seçim CSV ile eşleşmiyor.')
            if digest in seen:
                continue
            seen.add(digest)
            with Image.open(path) as original:
                gray = ImageOps.exif_transpose(original).convert('L')
            width, height = gray.size
            for field in CORE_FIELDS:
                try:
                    box = tuple(round(v * size) for v, size in zip(REGIONS[field], (width, height, width, height)))
                    crop = resize_crop(gray.crop(box))
                    crop.save(args.outputs / f'{path.stem}_{field}_crop.png')
                    debug = args.outputs / f'{path.stem}_{field}_candidates.json'
                    raw = read_field(executable, crop, field, debug)
                    value = normalize(field, raw)
                                                                                          
                    if field == 'date':
                        try:
                            value = datetime.strptime(value, '%m/%d/%Y').strftime('%m/%d/%Y')
                        except ValueError:
                            pass
                    if field == 'amount' and re.fullmatch(r'\d+[.,]\d{2}', value):
                        value = value.replace(',', '.')
                    candidates = json.loads(debug.read_text(encoding='utf-8'))
                    winner = select_candidate(field, candidates)
                    alternatives = sorted({normalize(field, item['text']) for item in candidates if item['text'].strip()})
                    reasons = []
                    if not valid_value(field, value):
                        reasons.append('Geçersiz veya eksik biçim')
                    if winner['confidence'] < 60:
                        reasons.append('Düşük OCR güveni')
                    if len(alternatives) > 1:
                        reasons.append('OCR denemeleri farklı sonuçlar verdi')
                    row.update({field + '_raw': raw, field: value,
                                field + '_confidence': winner['confidence'],
                                field + '_alternatives': json.dumps(alternatives, ensure_ascii=False),
                                field + '_review_reason': '; '.join(reasons)})
                except Exception as exc:
                    row[field + '_review_reason'] = str(exc)
                    row['error'] += f'{field}: {exc}; '
            row['status'] = 'error' if row['error'] else 'review'
        except Exception as exc:
            row['status'] = 'error'
            row['error'] = str(exc)
        rows.append(row)
        write_csv(result_path, columns, rows)
        print(f"{len(rows)}: {name} | {row['date']} | {row['payee']} | {row['amount']} | {row['status']}")
    print(f'Kaydedildi: {result_path} ({len(rows)} kayıt)')
    print('Güven puanı doğruluk değildir. Sonuçları etiketlerle ayrıca karşılaştırın.')


if __name__ == '__main__':
    main()
