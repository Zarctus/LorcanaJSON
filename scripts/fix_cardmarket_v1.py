#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path

def process_file(path: Path):
    changed = False
    with path.open('r', encoding='utf-8') as f:
        data = json.load(f)

    # find cards list (support either top-level list or dict with 'cards')
    if isinstance(data, dict) and 'cards' in data and isinstance(data['cards'], list):
        cards = data['cards']
        top_is_dict = True
    elif isinstance(data, list):
        cards = data
        top_is_dict = False
    else:
        print(f"Unknown file format: {path}")
        return False, 0

    # Map base path -> set of suffix numbers seen (as strings) and store card entries by their path
    base_map = {}
    card_by_path = {}

    for c in cards:
        ext = c.get('externalLinks') or {}
        url = ext.get('cardmarketUrl')
        if not url:
            continue
        # separate query part
        if '?' in url:
            part, q = url.split('?', 1)
            q = '?' + q
        else:
            part, q = url, ''

        m = re.search(r'-V(\d+)$', part)
        if m:
            num = m.group(1)
            base = part[:m.start()]
        else:
            num = None
            base = part

        base_map.setdefault(base, set()).add(num if num is not None else 'none')
        card_by_path.setdefault(base, []).append((c, part, q))

    updated_count = 0

    # For each base where V2 exists but V1 does not, update the card that currently has no suffix
    for base, nums in base_map.items():
        if '2' in nums and '1' not in nums:
            # find card with no suffix (i.e., part == base)
            entries = card_by_path.get(base, [])
            target = None
            for c, part, q in entries:
                if part == base:
                    target = (c, part, q)
                    break
            if target:
                c, part, q = target
                new_url = base + '-V1' + q
                if c.get('externalLinks', {}).get('cardmarketUrl') != new_url:
                    c.setdefault('externalLinks', {})['cardmarketUrl'] = new_url
                    changed = True
                    updated_count += 1

    if changed:
        # write backup
        bak = path.with_suffix(path.suffix + '.bak')
        path.rename(bak)
        with path.open('w', encoding='utf-8') as f:
            out = {'cards': cards} if top_is_dict else cards
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"Updated {updated_count} cards in {path} (backup at {bak})")
    else:
        print(f"No changes for {path}")

    return changed, updated_count

def main():
    root = Path('output')
    if not root.exists():
        print('No output/ directory found')
        return

    total_updates = 0
    total_files = 0
    for sub in root.iterdir():
        if sub.is_dir():
            f = sub / 'allCards.json'
            if f.exists():
                total_files += 1
                changed, cnt = process_file(f)
                total_updates += cnt

    print(f"Processed {total_files} files, total card updates: {total_updates}")

if __name__ == '__main__':
    main()
