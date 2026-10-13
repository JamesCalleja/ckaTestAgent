from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.markdown import Markdown
from rich.progress import Progress, BarColumn, TextColumn
from typing import List, Dict, Optional
from .models import Scenario, ExamState, CheckResult, Domain

console = Console()

class UI:
    """Rich terminal renderer for CKA Testing Agent."""

    @staticmethod
    def print_banner():
        banner = """[bold cyan]
  ██████╗██╗  ██╗ █████╗     ████████╗███████╗███████╗████████╗
 ██╔════╝██║ ██╔╝██╔══██╗    ╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝
 ██║     █████╔╝ ███████║       ██║   █████╗  ███████╗   ██║   
 ██║     ██╔═██╗ ██╔══██║       ██║   ██╔══╝  ╚════██║   ██║   
 ╚██████╗██║  ██╗██║  ██║       ██║   ███████╗███████║   ██║   
  ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝       ╚═╝   ╚══════╝╚══════╝   ╚═╝   
       [bold green]Certified Kubernetes Administrator Interactive Testing Agent[/bold green]
[/bold cyan]"""
        console.print(banner)

    @staticmethod
    def render_header(state: ExamState):
        total_q = len(state.scenarios)
        current_idx = state.current_index + 1
        elapsed_min = state.elapsed_seconds // 60
        score = state.total_score()
        max_score = state.max_possible_score()
        pct = (score / max_score * 100) if max_score > 0 else 0

        if state.is_timed and state.remaining_seconds is not None:
            rem_min = state.remaining_seconds // 60
            rem_sec = state.remaining_seconds % 60
            time_color = "green" if rem_min > 30 else ("yellow" if rem_min > 10 else "bold red")
            time_display = f"[{time_color}]⏱ Time Left: {rem_min:02d}:{rem_sec:02d}[/{time_color}] (Elapsed: {elapsed_min}m)"
        else:
            time_display = f"[dim cyan]⏱ Mode: Untimed Practice (Elapsed: {elapsed_min}m)[/dim cyan]"
        
        info_table = Table.grid(expand=True)
        info_table.add_column(justify="left")
        info_table.add_column(justify="center")
        info_table.add_column(justify="right")

        info_table.add_row(
            f"[bold blue]Exam:[/bold blue] {state.exam_name}  |  [bold blue]Task:[/bold blue] [bold white]{current_idx}/{total_q}[/bold white]",
            f"[bold yellow]Current Score:[/bold yellow] [bold white]{score:.1f} / {max_score:.1f} ({pct:.1f}%)[/bold white]",
            time_display
        )

        console.print(Panel(info_table, border_style="cyan", padding=(0, 1)))

    @staticmethod
    def render_scenario(scenario: Scenario, state: ExamState):
        content = []
        content.append(f"[bold magenta]Domain:[/bold magenta] {scenario.domain.value}")
        if scenario.namespace:
            content.append(f"[bold magenta]Target Namespace:[/bold magenta] [bold yellow]{scenario.namespace}[/bold yellow]")
        content.append(f"[bold magenta]Weight:[/bold magenta] [bold green]{scenario.weight}%[/bold green]\n")
        
        content.append(f"[bold white]{scenario.description}[/bold white]\n")
        
        content.append("[bold cyan]Requirements:[/bold cyan]")
        for i, req in enumerate(scenario.requirements, 1):
            content.append(f"  [bold cyan]{i}.[/bold cyan] {req}")

        revealed_count = state.hints_revealed.get(scenario.id, 0)
        if scenario.hints:
            if revealed_count > 0:
                content.append("\n[bold yellow]💡 Revealed Hints:[/bold yellow]")
                for h_idx in range(revealed_count):
                    content.append(f"  • {scenario.hints[h_idx]}")
            else:
                content.append(f"\n[dim italic]💡 {len(scenario.hints)} hint(s) available. Type 'hint' to reveal.[/dim italic]")

        panel = Panel(
            "\n".join(content),
            title=f"[bold green] Task {scenario.number}: {scenario.title} [/bold green]",
            border_style="green",
            padding=(1, 2)
        )
        console.print(panel)

    @staticmethod
    def render_results(scenario: Scenario, results: List[CheckResult]):
        table = Table(title=f"📋 Audit Results: Task {scenario.number} ({scenario.title})", border_style="blue", expand=True)
        table.add_column("Check / Verification Criteria", style="bold", ratio=4)
        table.add_column("Status", justify="center", ratio=1)
        table.add_column("Points", justify="right", ratio=1)
        table.add_column("Diagnostics / Output", ratio=4)

        total_earned = 0.0
        total_max = 0.0

        for res in results:
            status_str = "[bold green]✅ PASS[/bold green]" if res.passed else "[bold red]❌ FAIL[/bold red]"
            points_str = f"{res.score:.1f} / {res.max_score:.1f}"
            table.add_row(res.name, status_str, points_str, res.message)
            total_earned += res.score
            total_max += res.max_score

        console.print(table)
        pct = (total_earned / total_max * 100) if total_max > 0 else 0
        summary_color = "green" if pct >= 70 else ("yellow" if pct >= 40 else "red")
        console.print(f"[{summary_color}]Task Score: [bold]{total_earned:.1f} / {total_max:.1f} ({pct:.1f}%)[/bold][/{summary_color}]\n")

    @staticmethod
    def render_final_scorecard(state: ExamState):
        console.print(Panel("[bold cyan]🏆 CKA Final Examination Scorecard[/bold cyan]", border_style="gold1", expand=True))
        
        # Domain breakdown
        domain_scores: Dict[Domain, float] = {d: 0.0 for d in Domain}
        domain_max: Dict[Domain, float] = {d: 0.0 for d in Domain}

        table = Table(title="Task Breakdown", border_style="cyan", expand=True)
        table.add_column("Task #", justify="center", width=8)
        table.add_column("Title", ratio=3)
        table.add_column("Domain", ratio=3)
        table.add_column("Score", justify="right", ratio=1)
        table.add_column("Weight", justify="right", ratio=1)
        table.add_column("Result", justify="center", ratio=1)

        for sc in state.scenarios:
            earned = 0.0
            if sc.id in state.results:
                earned = sum(r.score for r in state.results[sc.id])
            
            domain_scores[sc.domain] += earned
            domain_max[sc.domain] += sc.weight

            status = "✅ PASS" if (earned / sc.weight >= 0.7) else "❌ FAIL"
            table.add_row(
                f"Task {sc.number}",
                sc.title,
                sc.domain.name,
                f"{earned:.1f}",
                f"{sc.weight:.1f}",
                status
            )

        console.print(table)

        # Domain summary table
        dom_table = Table(title="Domain Summary", border_style="magenta", expand=True)
        dom_table.add_column("Domain", ratio=4)
        dom_table.add_column("Score Earned", justify="right", ratio=2)
        dom_table.add_column("Max Weight", justify="right", ratio=2)
        dom_table.add_column("Percentage", justify="right", ratio=2)

        for dom in Domain:
            earned = domain_scores[dom]
            max_w = domain_max[dom]
            pct = (earned / max_w * 100) if max_w > 0 else 0
            dom_table.add_row(dom.value, f"{earned:.1f}", f"{max_w:.1f}", f"{pct:.1f}%")

        console.print(dom_table)

        # Final verdict
        total_earned = state.total_score()
        total_max = state.max_possible_score()
        final_pct = (total_earned / total_max * 100) if total_max > 0 else 0
        passed = final_pct >= 66.0  # Real CKA passing score is 66%

        if passed:
            verdict_panel = Panel(
                f"[bold green]🎉 CONGRATULATIONS! YOU PASSED THE CKA EXAM![/bold green]\n"
                f"Final Score: [bold white]{total_earned:.1f} / {total_max:.1f} ({final_pct:.1f}%)[/bold white] (Passing threshold: 66.0%)",
                border_style="green"
            )
        else:
            verdict_panel = Panel(
                f"[bold red]❌ EXAM RESULT: DID NOT PASS[/bold red]\n"
                f"Final Score: [bold white]{total_earned:.1f} / {total_max:.1f} ({final_pct:.1f}%)[/bold white] (Passing threshold: 66.0%)\n"
                f"[yellow]Focus on reviewing the domains with lower percentages above.[/yellow]",
                border_style="red"
            )
        console.print(verdict_panel)

    @staticmethod
    def render_command_bar():
        cmds = [
            "[bold cyan]audit[/bold cyan] (grade current)",
            "[bold cyan]audit-all[/bold cyan] (grade entire exam)",
            "[bold cyan]next[/bold cyan] / [bold cyan]prev[/bold cyan]",
            "[bold cyan]goto <N>[/bold cyan]",
            "[bold cyan]list[/bold cyan]",
            "[bold cyan]hint[/bold cyan]",
            "[bold cyan]setup[/bold cyan]",
            "[bold cyan]score[/bold cyan]",
            "[bold cyan]help[/bold cyan]",
            "[bold cyan]quit[/bold cyan]"
        ]
        console.print(f"[dim]Commands: {' | '.join(cmds)}[/dim]")
