from pathlib import Path
import argparse
import json
from run_cheques_llm import load_csv, write_csv, evidence_support, valid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--saved-json', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.results.resolve() == args.output.resolve():
        parser.error('Use a separate output file')
    rows = load_csv(args.results)
    columns = list(rows[0])
    for field in ('cached_amount_check',):
        if field not in columns:
            columns.append(field)
    changed = 0
    for row in rows:
        stem = Path(row['filename']).stem
        input_path = args.saved_json / (stem + '_input.json')
        response_path = args.saved_json / (stem + '_response.json')
        row['cached_amount_check'] = 'not_rechecked'
        if not input_path.exists() or not response_path.exists():
            continue
        evidence = json.loads(input_path.read_text(encoding='utf-8'))
        response = json.loads(response_path.read_text(encoding='utf-8'))
        answer = json.loads(response['message']['content'])
        value = row.get('llm_amount', '')
        if answer.get('amount') != value:
            raise ValueError('Saved response does not match result: ' + stem)
        fields = evidence.get('fields', {})
        if any(fields.get(f, {}).get('baseline', '') != row.get('ocr_' + f, '') for f in ('date', 'payee', 'amount')):
            raise ValueError('Saved OCR input does not match result: ' + stem)
        support = evidence_support('amount', value, answer.get('evidence', {}).get('amount'), evidence)
        row['cached_amount_check'] = support or 'unsupported'
        if valid('amount', value) and support and row.get('source_amount') == 'ocr_fallback':
            row['final_amount'] = value
            row['source_amount'] = 'llm_proposal'
            if row['status'] != 'error':
                row['status'] = 'review'
            row['needs_review'] = '1'
            row['reason'] = row.get('reason', '') + '; amount: saved OCR evidence supports proposal; human review retained'
            changed += 1
    write_csv(args.output, rows, columns)
    print('Updated amount proposals:', changed)
    print('Saved:', args.output)
    print('No OCR or model calls were made; review flags retained.')


if __name__ == '__main__':
    main()
