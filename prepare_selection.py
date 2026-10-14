from pathlib import Path
import argparse
import csv
import hashlib


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--images', type=Path, default=Path('data/images'))
    parser.add_argument('--output', type=Path, default=Path('outputs/cheque_unique_100.csv'))
    args = parser.parse_args()
    rows = []
    seen = set()
    for path in sorted(args.images.iterdir()):
        if path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        rows.append({'filename': path.name, 'image_sha256': digest})
    if not rows:
        raise ValueError('No usable image files found')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8-sig', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['filename', 'image_sha256'], delimiter=';')
        writer.writeheader()
        writer.writerows(rows)
    print('Unique image files:', len(rows))
    print('Saved:', args.output)


if __name__ == '__main__':
    main()
