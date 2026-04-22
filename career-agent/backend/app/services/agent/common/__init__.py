from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.agent.common.agent_llm_profiles import AgentLLMProfile, build_agent_llm_service, get_agent_llm_profile
from app.services.agent.common.business_agent_runtime import (
    BusinessAgentResult,
    collect_actions,
    merge_context_patches,
    render_agent_reply,
    run_tool_pipeline,
    run_tools,
)
from app.services.agent.common.entity_extractor import EntityExtractor, get_entity_extractor
from app.services.agent.common.hf_model_loading import quiet_hf_model_load
from app.services.agent.common.model_manager import (
    ModelDownloadError,
    ModelNotAvailableError,
    ensure_model_available,
    is_model_ready,
    load_cross_encoder,
    load_sentence_transformer,
    log_model_config,
)
from app.services.agent.common.intent_classifier import IntentClassifier, get_intent_classifier
from app.services.agent.common.intent_refiner import IntentRefiner, get_intent_refiner

if TYPE_CHECKING:
    from app.services.agent.common.flowchart_business_agents import FlowchartAgentHub

__all__ = [
    "AgentLLMProfile",
    "BusinessAgentResult",
    "EntityExtractor",
    "FlowchartAgentHub",
    "IntentClassifier",
    "IntentRefiner",
    "build_agent_llm_service",
    "collect_actions",
    "get_entity_extractor",
    "get_agent_llm_profile",
    "get_intent_classifier",
    "get_intent_refiner",
    "merge_context_patches",
    "quiet_hf_model_load",
    "render_agent_reply",
    "run_tool_pipeline",
    "run_tools",
]


def __getattr__(name: str):
    if name == "FlowchartAgentHub":
        from app.services.agent.common.flowchart_business_agents import FlowchartAgentHub

        return FlowchartAgentHub
    raise AttributeError(name)
