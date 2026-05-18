from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum


class ValidationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SKIP = "SKIP"


@dataclass
class ValidationResult:
    layer_name: str
    status: ValidationStatus
    score: float  # 0-100
    checks_passed: int
    checks_total: int
    details: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class BaseValidator(ABC):

    @abstractmethod
    async def validate(self) -> ValidationResult:
        pass

    @property
    @abstractmethod
    def layer_name(self) -> str:
        pass

    @property
    @abstractmethod
    def weight(self) -> float:
        pass
