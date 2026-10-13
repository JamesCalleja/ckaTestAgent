from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Callable, Any, Dict
import time

class Domain(Enum):
    STORAGE = "Storage (10%)"
    TROUBLESHOOTING = "Troubleshooting (30%)"
    WORKLOADS = "Workloads & Scheduling (15%)"
    CLUSTER_ARCH = "Cluster Architecture, Installation & Config (25%)"
    NETWORKING = "Services & Networking (20%)"

@dataclass
class CheckResult:
    name: str
    passed: bool
    score: float
    max_score: float
    message: str = ""
    details: str = ""

@dataclass
class VerificationCheck:
    name: str
    points: float
    check_fn: Callable[['Auditor'], CheckResult]
    description: str = ""

@dataclass
class Scenario:
    id: str
    number: int
    title: str
    domain: Domain
    weight: float
    namespace: Optional[str]
    description: str
    requirements: List[str]
    hints: List[str] = field(default_factory=list)
    setup_fn: Optional[Callable[['Auditor'], bool]] = None
    teardown_fn: Optional[Callable[['Auditor'], bool]] = None
    checks: List[VerificationCheck] = field(default_factory=list)

@dataclass
class ExamState:
    exam_name: str
    scenarios: List[Scenario]
    current_index: int = 0
    start_time: float = field(default_factory=time.time)
    duration_seconds: Optional[int] = None  # None for untimed practice
    results: Dict[str, List[CheckResult]] = field(default_factory=dict)
    hints_revealed: Dict[str, int] = field(default_factory=dict)
    is_completed: bool = False

    @property
    def is_timed(self) -> bool:
        return self.duration_seconds is not None

    @property
    def current_scenario(self) -> Optional[Scenario]:
        if 0 <= self.current_index < len(self.scenarios):
            return self.scenarios[self.current_index]
        return None

    @property
    def elapsed_seconds(self) -> int:
        return int(time.time() - self.start_time)

    @property
    def remaining_seconds(self) -> Optional[int]:
        if self.duration_seconds is None:
            return None
        rem = self.duration_seconds - self.elapsed_seconds
        return max(0, rem)

    def total_score(self) -> float:
        total = 0.0
        for sc in self.scenarios:
            if sc.id in self.results:
                total += sum(res.score for res in self.results[sc.id])
        return total

    def max_possible_score(self) -> float:
        return sum(sc.weight for sc in self.scenarios)
