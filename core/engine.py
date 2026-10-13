from typing import List, Optional, Dict
from .models import ExamState, Scenario, CheckResult
from .auditor import Auditor
from .ui import UI, console

class ExamEngine:
    """Core state engine that runs CKA exams, executes audits, and manages questions."""

    def __init__(self, exam_name: str, scenarios: List[Scenario], duration_minutes: Optional[int] = None):
        self.auditor = Auditor()
        duration_sec = (duration_minutes * 60) if duration_minutes is not None else None
        self.state = ExamState(
            exam_name=exam_name,
            scenarios=scenarios,
            current_index=0,
            duration_seconds=duration_sec
        )

    def get_current_scenario(self) -> Optional[Scenario]:
        return self.state.current_scenario

    def next_scenario(self) -> bool:
        if self.state.current_index < len(self.state.scenarios) - 1:
            self.state.current_index += 1
            return True
        return False

    def prev_scenario(self) -> bool:
        if self.state.current_index > 0:
            self.state.current_index -= 1
            return True
        return False

    def goto_scenario(self, task_number: int) -> bool:
        for idx, sc in enumerate(self.state.scenarios):
            if sc.number == task_number:
                self.state.current_index = idx
                return True
        return False

    def setup_current_scenario(self) -> bool:
        sc = self.get_current_scenario()
        if not sc:
            return False
        if sc.namespace and not self.auditor.namespace_exists(sc.namespace):
            self.auditor.kubectl(f"create ns {sc.namespace}")
        if sc.setup_fn:
            console.print(f"[cyan]Running environment setup for Task {sc.number}...[/cyan]")
            return sc.setup_fn(self.auditor)
        return True

    def reveal_hint(self) -> Optional[str]:
        sc = self.get_current_scenario()
        if not sc or not sc.hints:
            return None
        current_revealed = self.state.hints_revealed.get(sc.id, 0)
        if current_revealed < len(sc.hints):
            hint = sc.hints[current_revealed]
            self.state.hints_revealed[sc.id] = current_revealed + 1
            return hint
        return None

    def audit_scenario(self, scenario: Scenario) -> List[CheckResult]:
        results: List[CheckResult] = []
        for check in scenario.checks:
            try:
                res = check.check_fn(self.auditor)
                results.append(res)
            except Exception as e:
                results.append(CheckResult(
                    name=check.name,
                    passed=False,
                    score=0.0,
                    max_score=check.points,
                    message=f"Audit check execution error: {str(e)}"
                ))
        self.state.results[scenario.id] = results
        return results

    def audit_current(self) -> Optional[List[CheckResult]]:
        sc = self.get_current_scenario()
        if not sc:
            return None
        return self.audit_scenario(sc)

    def audit_all(self) -> Dict[str, List[CheckResult]]:
        for sc in self.state.scenarios:
            self.audit_scenario(sc)
        return self.state.results
