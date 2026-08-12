import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core.rule_config_manager import RuleConfigManager
from app.services.configuration_service import ConfigurationService
from app.services.system_rule_config_factory import SystemRuleConfigFactory


def test_editor_schema_exposes_model_owned_workflow_defaults():
    schema = ConfigurationService.get_editor_schema()
    workflow = schema["$defs"]["WorkflowRules"]["properties"]

    assert "QUEUED" in workflow["allowed_job_states"]["default"]
    assert workflow["job_state_transitions"]["default"]["QUEUED"][0] == "QUEUED"


def test_system_default_is_complete_and_safety_validated():
    config = SystemRuleConfigFactory.build()
    ConfigurationService.validate_config(config)

    assert config.version == SystemRuleConfigFactory.VERSION
    assert {"name", "location", "job_title", "company_name"}.issubset(config.fields)
    assert config.scoring.taxonomy.vacancy_rules
    assert config.scoring.taxonomy.candidate_rules
    assert config.scoring.domain_embedding.categories


def test_workflow_state_machine_is_reconstructed_from_normalized_profile():
    workflow = {
        "allowed_job_states": ["QUEUED", "PROCESSING", "COMPLETED", "FAILED"],
        "job_state_transitions": {"QUEUED": ["PROCESSING"], "PROCESSING": ["COMPLETED", "FAILED"]},
    }
    profile = SimpleNamespace(
        version_tag="dynamic-v1",
        description="Dynamic profile",
        updated_at=datetime.now(timezone.utc),
        components=[
            SimpleNamespace(
                component_type="workflow",
                system_rules=[
                    SimpleNamespace(
                        rule_type="workflow_state_machine",
                        rule_name="job_states",
                        target_value=json.dumps(workflow),
                    )
                ],
            )
        ],
    )

    assert RuleConfigManager._hydrate_profile(profile)["workflow"] == workflow


def test_taxonomy_branch_boundaries_are_reconstructed_deterministically():
    def condition(scope: str, branch: int) -> SimpleNamespace:
        return SimpleNamespace(
            condition_scope=scope,
            condition_mode="any",
            is_negated=False,
            branch_index=branch,
            values=[SimpleNamespace(value=scope)],
        )

    taxonomy_component = SimpleNamespace(
        component_type="scoring",
        component_name="taxonomy",
        weights=[],
        thresholds=[],
        system_rules=[
            SimpleNamespace(
                rule_type="vacancy_taxonomy",
                rule_name="dynamic_rule",
                target_value="Dynamic Domain::Dynamic Family",
                conditions=[condition("full_text", 1), condition("title", 0)],
            )
        ],
    )
    profile = SimpleNamespace(
        version_tag="dynamic-v1",
        description="Dynamic profile",
        updated_at=datetime.now(timezone.utc),
        components=[taxonomy_component],
    )

    branches = RuleConfigManager._hydrate_profile(profile)["scoring"]["taxonomy"]["vacancy_rules"][0]["branches"]

    assert branches[0]["conditions"][0]["scope"] == "title"
    assert branches[1]["conditions"][0]["scope"] == "full_text"


def test_rule_inventory_serializes_every_normalized_rule_kind():
    component = SimpleNamespace(
        component_type="scoring",
        component_name="match",
        system_rules=[
            SimpleNamespace(
                id=1,
                rule_name="recommendations",
                rule_type="recommendation_text",
                target_value="Review candidate",
                conditions=[SimpleNamespace()],
            )
        ],
        thresholds=[SimpleNamespace(id=2, threshold_key="high_min", threshold_value=80.0)],
        penalties=[SimpleNamespace(id=3, penalty_key="mandatory_failure", penalty_value=20.0)],
        weights=[SimpleNamespace(id=4, weight_key="skills", weight_value=0.25)],
    )

    inventory = ConfigurationService._serialize_rule_component(component)

    assert {rule["kind"] for rule in inventory["rules"]} == {"SYSTEM_RULE", "THRESHOLD", "PENALTY", "WEIGHT"}
    assert inventory["component_name"] == "match"
