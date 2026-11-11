"""Enrich prepared feature/sequence Parquet with exact-month LDAP (SPEC-001 §14)."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from itd.data.enrich_ldap import enrich_dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding='utf-8'))
        manifest = enrich_dataset(config)
        print(json.dumps({'output': config['paths']['output_root'],
                          'elapsed_seconds': manifest['elapsed_seconds'],
                          'branches': {name: {'rows': b['rows'], 'user_days': b['user_days'],
                                              'missing_user_days': b['missing_user_days']}
                                       for name, b in manifest['branches'].items()}}, indent=2))
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    main()
