# evals/runner.py
"""
Eval Runner: load test cases → chạy DevMate → judge → export report.
"""

import json
import time
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from evals.judge import JudgeResult, judge_response
from providers import LLMProvider, create_provider

console = Console()
EVALS_DIR = Path(__file__).parent
REPORTS_DIR = EVALS_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


class TestCase(BaseModel):
    id: str
    category: str
    input: str
    judge_criteria: list[str]
    expected_contains: str | None = None


class TestResult(BaseModel):
    test_id: str
    category: str
    provider: str
    model: str
    input: str
    response: str
    judge: JudgeResult
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost: float


def load_dataset(dataset_path: Path) -> list[TestCase]:
    """Load test cases từ YAML."""
    with open(dataset_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [TestCase(**t) for t in data["tests"]]


def run_test(test: TestCase, provider: LLMProvider) -> TestResult:
    """Chạy 1 test case với 1 provider."""
    start = time.time()

    # Gọi DevMate (giả lập chat thường, không streaming để đơn giản)
    result = provider.chat(
        messages=[{"role": "user", "content": test.input}],
        system="Bạn là DevMate, trợ lý AI cho lập trình viên Việt Nam.",
        max_tokens=1500,
    )

    latency_ms = int((time.time() - start) * 1000)
    response_text = result.text

    # Judge
    judge_result = judge_response(
        test_input=test.input,
        actual_response=response_text,
        criteria=test.judge_criteria,
        expected_contains=test.expected_contains,
    )

    cost = provider.calculate_cost(result.usage)

    return TestResult(
        test_id=test.id,
        category=test.category,
        provider=provider.provider_name,
        model=provider.model_name,
        input=test.input,
        response=response_text,
        judge=judge_result,
        latency_ms=latency_ms,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cost=cost,
    )


def run_eval(
    dataset_name: str = "basic",
    providers: list[str] = ["claude-sonnet"],
) -> list[TestResult]:
    """Chạy eval đầy đủ trên nhiều provider."""
    dataset_path = EVALS_DIR / "datasets" / f"{dataset_name}.yaml"
    tests = load_dataset(dataset_path)

    console.print(f"\n[bold cyan]🧪 Eval: {dataset_name}[/bold cyan]")
    console.print(f"  Tests: {len(tests)}")
    console.print(f"  Providers: {providers}\n")

    all_results = []

    with Progress() as progress:
        total = len(tests) * len(providers)
        task = progress.add_task("[cyan]Running tests...", total=total)

        for provider_name in providers:
            try:
                provider = create_provider(provider_name)
            except Exception as e:
                console.print(f"[red]❌ Skip {provider_name}: {e}[/red]")
                progress.update(task, advance=len(tests))
                continue

            for test in tests:
                try:
                    result = run_test(test, provider)
                    all_results.append(result)
                except Exception as e:
                    console.print(f"[red]❌ Test {test.id} fail: {e}[/red]")

                progress.update(task, advance=1)

    return all_results


def print_summary(results: list[TestResult]):
    """In summary bảng đẹp ra terminal."""
    # Group by provider
    by_provider: dict[str, list[TestResult]] = {}
    for r in results:
        key = f"{r.provider}/{r.model}"
        by_provider.setdefault(key, []).append(r)

    # Bảng tổng quan
    table = Table(title="📊 Eval Summary", show_header=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Pass", style="green")
    table.add_column("Avg Score", style="yellow")
    table.add_column("Avg Latency", style="magenta")
    table.add_column("Total Cost", style="white")

    for provider_key, prov_results in by_provider.items():
        passed = sum(1 for r in prov_results if r.judge.overall_score >= 7)
        avg_score = sum(r.judge.overall_score for r in prov_results) / len(prov_results)
        avg_latency = sum(r.latency_ms for r in prov_results) / len(prov_results)
        total_cost = sum(r.cost for r in prov_results)

        table.add_row(
            provider_key,
            f"{passed}/{len(prov_results)}",
            f"{avg_score:.1f}/10",
            f"{avg_latency:.0f}ms",
            f"${total_cost:.4f}",
        )

    console.print(table)

    # Failed tests
    failed = [r for r in results if r.judge.overall_score < 7]
    if failed:
        console.print(f"\n[bold red]❌ Failed tests ({len(failed)}):[/bold red]")
        for r in failed:
            console.print(
                f"  • [{r.provider}] {r.test_id}: {r.judge.overall_score}/10 - {r.judge.summary}"
            )


def save_report(results: list[TestResult]) -> Path:
    """Lưu report ra JSON + HTML."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON
    json_path = REPORTS_DIR / f"eval_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            [r.model_dump() for r in results],
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    # HTML report
    html_path = REPORTS_DIR / f"eval_{timestamp}.html"
    html_content = generate_html_report(results, timestamp)
    html_path.write_text(html_content, encoding="utf-8")

    return html_path


def generate_html_report(results: list[TestResult], timestamp: str) -> str:
    """Generate HTML report đẹp."""
    by_provider: dict[str, list[TestResult]] = {}
    for r in results:
        key = f"{r.provider}/{r.model}"
        by_provider.setdefault(key, []).append(r)

    # Build summary cards
    summary_cards = ""
    for provider_key, prov_results in by_provider.items():
        passed = sum(1 for r in prov_results if r.judge.overall_score >= 7)
        avg_score = sum(r.judge.overall_score for r in prov_results) / len(prov_results)
        total_cost = sum(r.cost for r in prov_results)
        pass_rate = (passed / len(prov_results)) * 100

        color = "green" if avg_score >= 7 else "orange" if avg_score >= 5 else "red"

        summary_cards += f"""
        <div class="card">
            <h3>{provider_key}</h3>
            <div class="score" style="color: {color}">{avg_score:.1f}/10</div>
            <div>Pass: {passed}/{len(prov_results)} ({pass_rate:.0f}%)</div>
            <div>Cost: ${total_cost:.4f}</div>
        </div>
        """

    # Build test rows
    test_rows = ""
    for r in results:
        score_color = "green" if r.judge.overall_score >= 7 else "red"
        criteria_html = "<ul>"
        for c in r.judge.criteria_scores:
            icon = "✅" if c.passed else "❌"
            criteria_html += f"<li>{icon} {c.criterion}: <i>{c.reasoning}</i></li>"
        criteria_html += "</ul>"

        test_rows += f"""
        <tr>
            <td>{r.test_id}</td>
            <td>{r.category}</td>
            <td>{r.provider}</td>
            <td style="color: {score_color}; font-weight: bold">{r.judge.overall_score}/10</td>
            <td>{r.latency_ms}ms</td>
            <td>${r.cost:.5f}</td>
            <td><details><summary>{r.judge.summary}</summary>{criteria_html}<hr><b>Response:</b><pre>{r.response[:500]}</pre></details></td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>DevMate Eval Report - {timestamp}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; padding: 20px; max-width: 1400px; margin: auto; background: #fafafa; }}
        h1 {{ color: #333; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 200px; }}
        .card h3 {{ margin-top: 0; color: #555; font-size: 14px; }}
        .score {{ font-size: 36px; font-weight: bold; margin: 10px 0; }}
        table {{ width: 100%; background: white; border-collapse: collapse; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f5f5f5; font-weight: 600; }}
        details summary {{ cursor: pointer; color: #333; }}
        pre {{ background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; }}
        ul {{ padding-left: 20px; }}
    </style>
</head>
<body>
    <h1>🧪 DevMate Eval Report</h1>
    <p>Generated: {timestamp} | Total tests: {len(results)}</p>
    
    <h2>📊 Summary by Provider</h2>
    <div class="summary">{summary_cards}</div>
    
    <h2>📋 Detail Results</h2>
    <table>
        <thead>
            <tr>
                <th>Test ID</th>
                <th>Category</th>
                <th>Provider</th>
                <th>Score</th>
                <th>Latency</th>
                <th>Cost</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>{test_rows}</tbody>
    </table>
</body>
</html>"""
