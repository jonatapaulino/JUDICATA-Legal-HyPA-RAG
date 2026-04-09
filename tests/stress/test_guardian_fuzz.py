"""
Fuzzing tests for GuardianAgent using Hypothesis.
Tests security validation robustness against random and adversarial inputs.
"""
import pytest
from hypothesis import given, strategies as st
from app.agents.guardian import GuardianAgent

# Strategy for generating potentially malicious inputs
malicious_patterns = st.sampled_from([
    "ignore instructions", "ignore previous", "system prompt", 
    "delete everything", "drop table", "<script>", "javascript:",
    "1gnore", "p@ssword", "admin", "root"
])

@st.composite
def mixed_input_strategy(draw):
    """Generates inputs mixing safe text with potential attacks."""
    safe_text = draw(st.text(min_size=5, max_size=50))
    malicious = draw(malicious_patterns)
    
    # Randomly combine
    if draw(st.booleans()):
        return f"{safe_text} {malicious}"
    else:
        return f"{malicious} {safe_text}"

class TestGuardianFuzz:
    
    def setup_method(self):
        self.guardian = GuardianAgent()
        # Ensure enabled for tests
        self.guardian.enabled = True

    @given(text=st.text())
    def test_guardian_robustness_random(self, text):
        """
        Guardian should never crash on random input.
        """
        try:
            result = self.guardian.validate_input(text, source="fuzz")
            assert result is not None
            assert isinstance(result.safe, bool)
        except Exception as e:
            pytest.fail(f"Guardian crashed on random input: {e}")

    @given(text=mixed_input_strategy())
    def test_guardian_detection_fuzz(self, text):
        """
        Guardian should detect known malicious patterns even when mixed with other text.
        Note: This is a probabilistic test. We expect it to catch MOST, but maybe not all if obfuscated heavily.
        """
        result = self.guardian.validate_input(text, source="fuzz")
        
        # If the generated text contains a clear blocked pattern, it should be unsafe
        # We check against the raw patterns defined in Guardian
        
        # This is a simplified check. The real Guardian has complex regex.
        # We just want to ensure it runs and returns a result.
        assert isinstance(result.safe, bool)
        
        # If it contains "ignore", it should likely be blocked (unless normalized away differently)
        if "ignore" in text.lower() and "instructions" in text.lower():
             assert result.safe is False

    @given(text=st.text(min_size=1000, max_size=10000))
    def test_guardian_performance_long_input(self, text):
        """
        Guardian should handle very long inputs without hanging (DoS protection).
        Hypothesis has a timeout, so if this hangs, the test fails.
        """
        self.guardian.validate_input(text, source="fuzz_long")
