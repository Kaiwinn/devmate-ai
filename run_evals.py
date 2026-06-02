# run_evals.py
"""CLI để chạy eval suite."""

import argparse
import webbrowser

from dotenv import load_dotenv

load_dotenv()

from evals.runner import print_summary, run_eval, save_report


def main():
    parser = argparse.ArgumentParser(description="Run DevMate evals")
    parser.add_argument(
        "--dataset",
        default="basic",
        help="Dataset name (file in evals/datasets/)",
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["groq-llama"],
        help="Providers to test",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Đừng auto-open HTML report",
    )
    args = parser.parse_args()

    # Run
    results = run_eval(args.dataset, args.providers)

    # Summary
    print_summary(results)

    # Save
    report_path = save_report(results)
    print(f"\n💾 Reports saved: {report_path.parent}")
    print(f"   📄 HTML: {report_path.name}")

    # Open
    if not args.no_open:
        webbrowser.open(f"file://{report_path.absolute()}")


if __name__ == "__main__":
    main()
