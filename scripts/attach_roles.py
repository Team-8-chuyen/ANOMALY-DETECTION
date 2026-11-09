"""Attach exact-month LDAP roles to one feature file (SPEC-001)."""
import argparse
import csv
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from itd.data.ldap import FEATURES, attach_roles, load_monthly_roles, read_csv_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ldap-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    temporary_path = None
    try:
        # SPEC-001 §4.1: validate before creating or replacing output.
        if args.input.resolve() == args.output.resolve() or (
            args.input.exists() and args.output.exists() and args.input.samefile(args.output)
        ):
            raise ValueError("input and output must be different files")
        if args.output.exists() and not args.overwrite:
            raise FileExistsError(f"{args.output}: exists; use --overwrite")
        roles = load_monthly_roles(args.ldap_dir)
        header, rows = read_csv_rows(args.input, {"user_id", "date", *FEATURES})
        try:
            joined = attach_roles(rows, roles)
        except ValueError as error:
            raise ValueError(f"{args.input}: {error}") from error
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", delete=False,
            dir=args.output.parent, prefix=".attach-roles-", suffix=".csv",
        ) as stream:
            temporary_path = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=[*header, "role", "role_missing"])
            writer.writeheader()
            writer.writerows(joined)
        if args.overwrite:
            os.replace(temporary_path, args.output)
        else:
            # Windows rename refuses an existing destination.
            os.rename(temporary_path, args.output)
        temporary_path = None
        missing = sum(row["role_missing"] for row in joined)
        print(f"Rows: {len(joined)}; matched: {len(joined) - missing}; missing: {missing}")
        print(f"Saved: {args.output}")
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(1, f"Error: {error}\n")
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
