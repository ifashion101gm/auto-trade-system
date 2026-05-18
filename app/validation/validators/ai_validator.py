from app.ai_agents.orchestrator import AIAgentOrchestrator
from .base_validator import BaseValidator, ValidationResult, ValidationStatus


class AIAgentValidator(BaseValidator):

    @property
    def layer_name(self) -> str:
        return "AI Agents"

    @property
    def weight(self) -> float:
        return 5

    async def validate(self) -> ValidationResult:
        checks = []
        passed = 0
        total = 2

        try:
            orchestrator = AIAgentOrchestrator(use_openrouter=True)

            # Check 1: Orchestrator initialized with LLM client
            if orchestrator.use_openrouter and orchestrator.llm_client:
                passed += 1
                checks.append({'check': 'LLM Client Configured', 'status': 'PASS'})
            else:
                checks.append({'check': 'LLM Client Configured', 'status': 'WARNING',
                                'note': 'No LLM client — AI analysis will be skipped'})

            # Check 2: API key present in config
            from app.config import settings
            if getattr(settings, 'OPENROUTER_API_KEY', None) or getattr(settings, 'ANTHROPIC_API_KEY', None):
                passed += 1
                checks.append({'check': 'AI API Key', 'status': 'PASS'})
            else:
                checks.append({'check': 'AI API Key', 'status': 'FAIL', 'note': 'No AI API key configured'})

            score = (passed / total) * 100
            # AI agents are non-critical; WARNING is acceptable
            status = ValidationStatus.PASS if passed == total else ValidationStatus.WARNING
            return ValidationResult(
                layer_name=self.layer_name,
                status=status,
                score=score,
                checks_passed=passed,
                checks_total=total,
                details=checks,
            )

        except Exception as e:
            return ValidationResult(
                layer_name=self.layer_name,
                status=ValidationStatus.WARNING,  # Non-critical layer
                score=0, checks_passed=0, checks_total=total, errors=[str(e)],
            )
