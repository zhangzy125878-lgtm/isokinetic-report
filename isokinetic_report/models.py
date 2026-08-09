from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class AthleteInfo:
    name: str
    sport: str
    sex: Optional[str]
    weight_kg: Optional[float]
    test_date: str
    injury: Optional[str]
    report_type: str


@dataclass
class TestRecord:
    row_number: int
    date_label: str
    is_current: bool
    joint: str
    speed: str
    muscle_a: str
    muscle_b: str
    left_a: Optional[float]
    left_b: Optional[float]
    right_a: Optional[float]
    right_b: Optional[float]
    existing_left_ratio: Optional[float] = None
    existing_right_ratio: Optional[float] = None
    existing_a_asymmetry: Optional[float] = None
    existing_b_asymmetry: Optional[float] = None
    left_ratio: Optional[float] = None
    right_ratio: Optional[float] = None
    a_asymmetry: Optional[float] = None
    b_asymmetry: Optional[float] = None
    left_ratio_status: str = "missing"
    right_ratio_status: str = "missing"
    a_asymmetry_state: Optional[str] = None
    b_asymmetry_state: Optional[str] = None


@dataclass(frozen=True)
class GaugeConfig:
    display_order: int
    joint: str
    gauge_min: float
    low_red_upper: float
    low_orange_upper: float
    target_low: float
    target_high: float
    high_yellow_upper: float
    high_orange_upper: float
    gauge_max: float
    source_status: str
    enabled: bool
    note: str = ""


@dataclass(frozen=True)
class AsymmetryLevel:
    order: int
    state: str
    minimum_inclusive: float
    maximum_exclusive: Optional[float]
    symbol: str
    color: str
    enabled: bool = True
    note: str = ""


@dataclass(frozen=True)
class PriorityRule:
    group: str
    order: int
    output_label: str
    metric: str
    operator: str
    threshold: float
    group_relation: str
    label_color: str
    enabled: bool = True
    note: str = ""


@dataclass
class Standards:
    gauges: dict[str, GaugeConfig] = field(default_factory=dict)
    target_ranges: dict[str, tuple[int, float, float]] = field(default_factory=dict)
    asymmetry_levels: list[AsymmetryLevel] = field(default_factory=list)
    priority_rules: list[PriorityRule] = field(default_factory=list)
    palette: dict[str, str] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    preview: bool = False

    @property
    def complete(self) -> bool:
        return not self.issues


@dataclass
class AnalysisResult:
    athlete: AthleteInfo
    records: list[TestRecord]
    standards: Standards
    joint_priorities: dict[str, Optional[str]]
    recommendations: list[str]
    warnings: list[str]
    original_comments: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ReportPaths:
    png: Path
    pdf: Optional[Path]
    additional_pngs: tuple[Path, ...] = ()

    @property
    def pngs(self) -> tuple[Path, ...]:
        return (self.png, *self.additional_pngs)
