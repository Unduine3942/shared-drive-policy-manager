"""Unit tests for shared_drive_manager.core.policy_engine module."""
from datetime import datetime, timezone

import pytest

from shared_drive_manager.core.models import FileRecord, Policy, Rule, Violation
from shared_drive_manager.core.policy_engine import (
    PolicyEngine,
    validate_rule_value,
)


# Test data fixtures
@pytest.fixture
def sample_file_record():
    """Create a sample FileRecord for testing."""
    return FileRecord(
        file_id=1,
        root_id=1,
        path_hash="abc123",
        full_path=r"C:\Users\TestUser\Documents\report.xlsx",
        parent_path=r"C:\Users\TestUser\Documents",
        name="report.xlsx",
        extension=".xlsx",
        section_name="Finance",
        size_bytes=5_242_880,  # 5 MB
        path_depth=4,
        path_length=45,
        is_empty=False,
        ctime_utc="2024-01-01T10:00:00Z",
        mtime_utc="2024-02-15T14:30:00Z",
        atime_utc="2024-05-08T09:15:00Z",
        owner_sid="S-1-5-21-3623811015-3361044348-30300820-1013",
        owner_name="DOMAIN\\testuser",
    )


@pytest.fixture
def sample_policy():
    """Create a sample Policy for testing."""
    rule = Rule(
        rule_id=1,
        policy_id=1,
        field_name="extension",
        operator="equals",
        value=".xlsx",
        case_sensitive=False,
        negated=False,
        sort_order=0,
    )
    return Policy(
        policy_id=1,
        name="Excel Files",
        severity="warning",
        match_mode="all",
        scope_prefixes=[],
        rules=[rule],
        enabled=True,
    )


class TestValidateRuleValue:
    """Tests for validate_rule_value() validation helper."""

    def test_validate_no_value_operators_accept_empty(self):
        """Operators that don't need values should accept empty strings."""
        for op in ["is_true", "is_false", "is_missing", "is_not_missing"]:
            result = validate_rule_value(op, "")
            assert result is None

    def test_validate_operator_requires_value(self):
        """Operators that need values should reject empty strings."""
        result = validate_rule_value("contains", "")
        assert result is not None
        assert "required" in result.lower()

    def test_validate_regex_valid(self):
        """Valid regex should pass validation."""
        result = validate_rule_value("regex", r"\d{3}-\d{4}")
        assert result is None

    def test_validate_regex_invalid(self):
        """Invalid regex should fail validation."""
        result = validate_rule_value("regex", "[invalid(regex")
        assert result is not None
        assert "invalid" in result.lower()

    def test_validate_regex_too_long(self):
        """Regex longer than 500 chars should fail validation."""
        long_regex = "a" * 501
        result = validate_rule_value("regex", long_regex)
        assert result is not None
        assert "too long" in result.lower()

    def test_validate_between_valid(self):
        """Valid between values should pass."""
        result = validate_rule_value("between", "10, 100")
        assert result is None

    def test_validate_between_missing_value(self):
        """Between without two values should fail."""
        result = validate_rule_value("between", "10")
        assert result is not None

    def test_validate_between_non_numeric(self):
        """Between with non-numeric values should fail."""
        result = validate_rule_value("between", "abc, xyz")
        assert result is not None

    def test_validate_numeric_operators_valid(self):
        """Numeric operators with valid numbers should pass."""
        for op in ["gt", "gte", "lt", "lte", "older_than_days", "newer_than_days"]:
            result = validate_rule_value(op, "100")
            assert result is None

    def test_validate_numeric_operators_invalid(self):
        """Numeric operators with non-numeric values should fail."""
        for op in ["gt", "gte", "lt", "lte"]:
            result = validate_rule_value(op, "not_a_number")
            assert result is not None


class TestStringOperators:
    """Tests for string-based operators."""

    def test_equals_operator(self, sample_file_record):
        """equals operator should match exact strings."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="equals",
            value=".xlsx",
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_equals_case_insensitive(self, sample_file_record):
        """equals with case_sensitive=False should ignore case."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="equals",
            value=".XLSX",
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_not_equals_operator(self, sample_file_record):
        """not_equals operator should match non-equal strings."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="not_equals",
            value=".doc",
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_contains_operator(self, sample_file_record):
        """contains operator should find substring."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="name",
            operator="contains",
            value="report",
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_starts_with_operator(self, sample_file_record):
        """starts_with operator should match prefixes."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="name",
            operator="starts_with",
            value="report",
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_ends_with_operator(self, sample_file_record):
        """ends_with operator should match suffixes."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="name",
            operator="ends_with",
            value=".xlsx",
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_glob_operator(self, sample_file_record):
        """glob operator should match wildcard patterns."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="name",
            operator="glob",
            value="*.xlsx",
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_regex_operator(self, sample_file_record):
        """regex operator should match regex patterns."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="name",
            operator="regex",
            value=r"report.*\.xlsx",
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_in_operator(self, sample_file_record):
        """in operator should check if value is in list."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="in",
            value=[".xlsx", ".docx", ".pdf"],
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_not_in_operator(self, sample_file_record):
        """not_in operator should check if value is not in list."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="not_in",
            value=[".exe", ".bat", ".cmd"],
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1


class TestNumericOperators:
    """Tests for numeric operators."""

    def test_gt_operator(self, sample_file_record):
        """gt (greater than) should compare numbers."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="size_bytes",
            operator="gt",
            value=1_000_000,  # 1 MB
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_lt_operator(self, sample_file_record):
        """lt (less than) should compare numbers."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="size_bytes",
            operator="lt",
            value=10_000_000,  # 10 MB
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_gte_operator(self, sample_file_record):
        """gte (>=) operator should work."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="size_bytes",
            operator="gte",
            value=5_242_880,
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_between_operator(self, sample_file_record):
        """between operator should check range."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="size_bytes",
            operator="between",
            value=[1_000_000, 10_000_000],
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1


class TestDateOperators:
    """Tests for date-based operators."""

    def test_older_than_days_operator(self, sample_file_record):
        """older_than_days should flag old files."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="mtime_utc",
            operator="older_than_days",
            value=10,
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        # File modified 2024-02-15, should be older than 10 days from today (2026-05-08)
        assert len(violations) == 1

    def test_newer_than_days_operator(self, sample_file_record):
        """newer_than_days should flag recent files."""
        # Create a file with recent mtime
        recent_record = FileRecord(
            file_id=2,
            root_id=1,
            path_hash="def456",
            full_path=r"C:\recent.txt",
            parent_path=r"C:",
            name="recent.txt",
            extension=".txt",
            size_bytes=1024,
            path_depth=1,
            path_length=15,
            is_empty=False,
            mtime_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="mtime_utc",
            operator="newer_than_days",
            value=30,
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(recent_record, [policy], run_id=1)
        assert len(violations) == 1


class TestBooleanOperators:
    """Tests for boolean operators."""

    def test_is_true_operator(self, sample_file_record):
        """is_true should flag true values."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="is_empty",
            operator="is_true",
            value=None,
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        empty_record = FileRecord(
            file_id=1,
            root_id=1,
            path_hash="abc123",
            full_path=r"C:\empty.txt",
            parent_path=r"C:",
            name="empty.txt",
            extension=".txt",
            size_bytes=0,
            path_depth=1,
            path_length=15,
            is_empty=True,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="info",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(empty_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_is_false_operator(self, sample_file_record):
        """is_false should flag false values."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="is_empty",
            operator="is_false",
            value=None,
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1


class TestNullOperators:
    """Tests for null/missing value operators."""

    def test_is_missing_operator(self, sample_file_record):
        """is_missing should flag None/empty values."""
        no_owner_record = FileRecord(
            file_id=1,
            root_id=1,
            path_hash="abc123",
            full_path=r"C:\file.txt",
            parent_path=r"C:",
            name="file.txt",
            extension=".txt",
            size_bytes=1024,
            path_depth=1,
            path_length=15,
            is_empty=False,
            owner_name=None,
        )
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="owner_name",
            operator="is_missing",
            value=None,
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="info",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(no_owner_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_is_not_missing_operator(self, sample_file_record):
        """is_not_missing should flag non-None values."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="owner_name",
            operator="is_not_missing",
            value=None,
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1


class TestNegatedRules:
    """Tests for negated rules."""

    def test_negated_rule(self, sample_file_record):
        """Negated rules should invert the match."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="equals",
            value=".docx",
            case_sensitive=True,
            negated=True,  # NOT equals .docx
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        # File is .xlsx, so NOT .docx should match
        assert len(violations) == 1


class TestMatchModes:
    """Tests for policy match modes (all vs any)."""

    def test_match_mode_all_all_true(self, sample_file_record):
        """match_mode='all' with all true rules should match."""
        rules = [
            Rule(
                rule_id=1,
                policy_id=1,
                field_name="extension",
                operator="equals",
                value=".xlsx",
                case_sensitive=True,
                negated=False,
                sort_order=0,
            ),
            Rule(
                rule_id=2,
                policy_id=1,
                field_name="section_name",
                operator="equals",
                value="Finance",
                case_sensitive=True,
                negated=False,
                sort_order=1,
            ),
        ]
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=rules,
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_match_mode_all_one_false(self, sample_file_record):
        """match_mode='all' with one false rule should not match."""
        rules = [
            Rule(
                rule_id=1,
                policy_id=1,
                field_name="extension",
                operator="equals",
                value=".xlsx",
                case_sensitive=True,
                negated=False,
                sort_order=0,
            ),
            Rule(
                rule_id=2,
                policy_id=1,
                field_name="section_name",
                operator="equals",
                value="HR",  # File is Finance, not HR
                case_sensitive=True,
                negated=False,
                sort_order=1,
            ),
        ]
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=rules,
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 0

    def test_match_mode_any_one_true(self, sample_file_record):
        """match_mode='any' with one true rule should match."""
        rules = [
            Rule(
                rule_id=1,
                policy_id=1,
                field_name="extension",
                operator="equals",
                value=".docx",  # File is .xlsx
                case_sensitive=True,
                negated=False,
                sort_order=0,
            ),
            Rule(
                rule_id=2,
                policy_id=1,
                field_name="section_name",
                operator="equals",
                value="Finance",  # This matches
                case_sensitive=True,
                negated=False,
                sort_order=1,
            ),
        ]
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="any",
            scope_prefixes=[],
            rules=rules,
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_match_mode_any_all_false(self, sample_file_record):
        """match_mode='any' with all false rules should not match."""
        rules = [
            Rule(
                rule_id=1,
                policy_id=1,
                field_name="extension",
                operator="equals",
                value=".docx",
                case_sensitive=True,
                negated=False,
                sort_order=0,
            ),
            Rule(
                rule_id=2,
                policy_id=1,
                field_name="section_name",
                operator="equals",
                value="HR",
                case_sensitive=True,
                negated=False,
                sort_order=1,
            ),
        ]
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="any",
            scope_prefixes=[],
            rules=rules,
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 0


class TestScopePrefixes:
    """Tests for scope_prefixes filtering."""

    def test_scope_prefix_matches(self, sample_file_record):
        """Policy with matching scope prefix should apply."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="equals",
            value=".xlsx",
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[r"C:\Users"],  # File path starts with this
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1

    def test_scope_prefix_no_match(self, sample_file_record):
        """Policy with non-matching scope prefix should not apply."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="equals",
            value=".xlsx",
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[r"D:\Different"],  # File path doesn't start with this
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 0

    def test_multiple_scope_prefixes_any_match(self, sample_file_record):
        """Policy should apply if any scope prefix matches."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="equals",
            value=".xlsx",
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[r"D:\NoMatch", r"C:\Users"],  # Second one matches
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_no_file_id_returns_no_violations(self):
        """Record with file_id=None should return no violations."""
        record = FileRecord(
            file_id=None,  # Missing file_id
            root_id=1,
            path_hash="abc123",
            full_path=r"C:\file.txt",
            parent_path=r"C:",
            name="file.txt",
            extension=".txt",
            size_bytes=1024,
            path_depth=1,
            path_length=15,
            is_empty=False,
        )
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="equals",
            value=".txt",
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(record, [policy], run_id=1)
        assert len(violations) == 0

    def test_empty_rules_list_no_match(self, sample_file_record):
        """Policy with no rules should not match."""
        policy = Policy(
            policy_id=1,
            name="test",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[],  # No rules
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 0

    def test_multiple_policies(self, sample_file_record):
        """Evaluating multiple policies should flag all matches."""
        rule1 = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="equals",
            value=".xlsx",
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy1 = Policy(
            policy_id=1,
            name="Excel files",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule1],
        )
        rule2 = Rule(
            rule_id=2,
            policy_id=2,
            field_name="size_bytes",
            operator="gt",
            value=1_000_000,
            case_sensitive=False,
            negated=False,
            sort_order=0,
        )
        policy2 = Policy(
            policy_id=2,
            name="Large files",
            severity="critical",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule2],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(
            sample_file_record, [policy1, policy2], run_id=1
        )
        assert len(violations) == 2

    def test_violation_has_correct_severity(self, sample_file_record):
        """Violation should preserve policy severity."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="equals",
            value=".xlsx",
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="test",
            severity="critical",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1
        assert violations[0].severity == "critical"

    def test_violation_has_reason(self, sample_file_record):
        """Violation should include a reason."""
        rule = Rule(
            rule_id=1,
            policy_id=1,
            field_name="extension",
            operator="equals",
            value=".xlsx",
            case_sensitive=True,
            negated=False,
            sort_order=0,
        )
        policy = Policy(
            policy_id=1,
            name="Excel Policy",
            severity="warning",
            match_mode="all",
            scope_prefixes=[],
            rules=[rule],
        )
        engine = PolicyEngine()
        violations = engine.evaluate(sample_file_record, [policy], run_id=1)
        assert len(violations) == 1
        assert len(violations[0].reason) > 0
