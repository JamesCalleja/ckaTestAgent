#!/usr/bin/env python3
"""
CKA Testing Agent - Interactive Terminal Testing Suite
"""
import sys
import os
import argparse
from typing import List, Optional

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models import Scenario
from core.engine import ExamEngine
from core.ui import UI, console
from scenarios.cka_exam_1 import get_cka_exam_1

def parse_args():
    parser = argparse.ArgumentParser(description="CKA Interactive Testing Agent")
    parser.add_argument("--exam", type=int, default=1, help="Exam number to start (default: 1)")
    parser.add_argument("--timed", action="store_true", help="Enable 2-hour official CKA exam countdown timer")
    parser.add_argument("--minutes", type=int, default=120, help="Custom timer duration in minutes when --timed is active (default: 120)")
    parser.add_argument("--audit-all", action="store_true", help="Audit all tasks and display final scorecard immediately")
    parser.add_argument("--reset", action="store_true", help="Reset minikube cluster to clean vanilla state")
    return parser.parse_args()

def reset_cluster(engine: ExamEngine):
    console.print("[yellow]Resetting cluster to vanilla state...[/yellow]")
    namespaces = ["cka-auth", "cka-deploy", "cka-lab1", "cka-lab2", "cka-network", "cka-rbac", "cka-sched", "cka-storage", "cka-workload", "cks-storage", "cka-daemon", "cka-services", "cka-troubleshoot", "cka-resources", "cka-config", "cka-ingress"]
    ns_str = " ".join(namespaces)
    engine.auditor.kubectl(f"delete ns {ns_str} --ignore-not-found=true")
    engine.auditor.kubectl("delete pv pv-data --ignore-not-found=true")
    engine.auditor.kubectl("delete clusterrole pod-reader --ignore-not-found=true")
    engine.auditor.kubectl("label node minikube-m02 tier- 2>/dev/null")
    engine.auditor.kubectl("taint node minikube-m02 dedicated:NoSchedule- 2>/dev/null")
    engine.auditor.kubectl("uncordon minikube minikube-m02 2>/dev/null")
    engine.auditor.run_cmd("minikube ssh 'sudo rm -f /etc/kubernetes/manifests/static-web.yaml' 2>/dev/null")
    console.print("[bold green]✅ Cluster reset complete![/bold green]\n")

def list_tasks(engine: ExamEngine):
    from rich.table import Table
    table = Table(title="Exam Task List", border_style="cyan", expand=True)
    table.add_column("Task #", justify="center", width=8)
    table.add_column("Title", ratio=3)
    table.add_column("Domain", ratio=3)
    table.add_column("Weight", justify="right", ratio=1)
    table.add_column("Score", justify="right", ratio=1)
    table.add_column("Status", justify="center", ratio=1)

    for idx, sc in enumerate(engine.state.scenarios):
        earned = 0.0
        status = "[dim]Not Audited[/dim]"
        if sc.id in engine.state.results:
            results = engine.state.results[sc.id]
            earned = sum(r.score for r in results)
            if earned >= sc.weight * 0.7:
                status = "[bold green]✅ PASS[/bold green]"
            else:
                status = "[bold red]❌ FAIL[/bold red]"
        
        prefix = "👉 " if idx == engine.state.current_index else "   "
        table.add_row(
            f"{prefix}Task {sc.number}",
            sc.title,
            sc.domain.name,
            f"{sc.weight:.1f}%",
            f"{earned:.1f}",
            status
        )
    console.print(table)

def main():
    args = parse_args()
    scenarios = get_cka_exam_1()
    duration_min = args.minutes if args.timed else None
    engine = ExamEngine(exam_name=f"CKA Practice Exam {args.exam}", scenarios=scenarios, duration_minutes=duration_min)

    if args.reset:
        reset_cluster(engine)
        return

    if args.audit_all:
        console.print("[cyan]Auditing all exam tasks against cluster...[/cyan]\n")
        engine.audit_all()
        UI.render_final_scorecard(engine.state)
        return

    # Interactive Mode
    UI.print_banner()
    console.print("[bold green]Welcome to the CKA Testing Agent![/bold green]")
    console.print("Type [bold cyan]help[/bold cyan] to see available commands or [bold cyan]audit[/bold cyan] when you complete a task.\n")

    while True:
        sc = engine.get_current_scenario()
        if not sc:
            break

        UI.render_header(engine.state)
        UI.render_scenario(sc, engine.state)
        UI.render_command_bar()

        try:
            prompt_str = f"[Task {sc.number}] > "
            user_input = console.input(f"\n[bold green]{prompt_str}[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Exiting CKA Testing Agent. Good luck with your studies![/yellow]")
            break

        if not user_input:
            continue

        parts = user_input.split()
        cmd = parts[0].lower()

        if cmd in ["quit", "exit", "q"]:
            console.print("[yellow]Exiting CKA Testing Agent.[/yellow]")
            break

        elif cmd in ["audit", "check", "grade"]:
            console.print(f"[cyan]Auditing Task {sc.number} ({sc.title})...[/cyan]")
            results = engine.audit_current()
            if results:
                UI.render_results(sc, results)
            console.input("[dim]Press Enter to continue...[/dim]")

        elif cmd in ["audit-all", "grade-all"]:
            console.print("[cyan]Auditing all 15 exam tasks across the cluster...[/cyan]")
            engine.audit_all()
            UI.render_final_scorecard(engine.state)
            console.input("[dim]Press Enter to continue...[/dim]")

        elif cmd in ["next", "n"]:
            if not engine.next_scenario():
                console.print("[yellow]You are already on the last task.[/yellow]")
            else:
                engine.setup_current_scenario()

        elif cmd in ["prev", "p"]:
            if not engine.prev_scenario():
                console.print("[yellow]You are on the first task.[/yellow]")

        elif cmd in ["goto", "g"]:
            if len(parts) > 1 and parts[1].isdigit():
                target = int(parts[1])
                if not engine.goto_scenario(target):
                    console.print(f"[red]Task number {target} not found.[/red]")
                else:
                    engine.setup_current_scenario()
            else:
                console.print("[red]Usage: goto <task_number> (e.g. goto 4)[/red]")

        elif cmd in ["list", "ls"]:
            list_tasks(engine)
            console.input("[dim]Press Enter to continue...[/dim]")

        elif cmd in ["setup", "init"]:
            engine.setup_current_scenario()
            console.print(f"[green]Setup for Task {sc.number} completed.[/green]")

        elif cmd in ["hint", "h"]:
            hint = engine.reveal_hint()
            if hint:
                console.print(f"[bold yellow]💡 Hint:[/bold yellow] {hint}")
            else:
                console.print("[dim]No more hints available for this task.[/dim]")

        elif cmd in ["score", "summary", "report"]:
            UI.render_final_scorecard(engine.state)
            console.input("[dim]Press Enter to continue...[/dim]")

        elif cmd in ["reset-cluster", "clean"]:
            reset_cluster(engine)

        elif cmd in ["help", "?"]:
            console.print(Panel(
                """[bold cyan]Available Commands:[/bold cyan]
  • [bold green]audit[/bold green]          : Grade the current task and display diagnostic results
  • [bold green]audit-all[/bold green]      : Grade all tasks and generate full exam scorecard
  • [bold green]next[/bold green] / [bold green]prev[/bold green]     : Move forward or backward through tasks
  • [bold green]goto <N>[/bold green]       : Jump directly to Task N (e.g., 'goto 5')
  • [bold green]list[/bold green]           : Display list of all exam tasks with pass/fail status
  • [bold green]hint[/bold green]           : Reveal a hint for the current task
  • [bold green]setup[/bold green]          : Create the target namespace / pre-requisites for current task
  • [bold green]score[/bold green]          : View full scorecard and domain breakdown
  • [bold green]reset-cluster[/bold green]  : Clean up all lab namespaces, PVs, node taints & static pods
  • [bold green]quit[/bold green]           : Exit the exam session
""",
                title="[bold yellow]Command Reference[/bold yellow]",
                border_style="yellow"
            ))
            console.input("[dim]Press Enter to continue...[/dim]")

        else:
            console.print(f"[red]Unknown command: '{cmd}'. Type 'help' for command list.[/red]")

if __name__ == "__main__":
    main()
