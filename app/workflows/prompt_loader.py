"""Utility to load prompts and system messages from JSON configuration."""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Path to prompts.json (relative to this file)
PROMPTS_FILE = Path(__file__).parent / "prompts.json"


class PromptLoader:
    """Loads and manages prompts from JSON configuration."""
    
    _prompts_data: Dict[str, Any] = None
    _last_modified: float = 0
    
    @classmethod
    def _load_prompts(cls) -> Dict[str, Any]:
        """Load prompts from JSON file with caching."""
        if cls._prompts_data is None or cls._should_reload():
            try:
                with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
                    cls._prompts_data = json.load(f)
                    cls._last_modified = os.path.getmtime(PROMPTS_FILE)
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"Prompts file not found: {PROMPTS_FILE}\n"
                    f"Please create {PROMPTS_FILE} with prompt configurations."
                )
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in prompts file {PROMPTS_FILE}: {e}\n"
                    f"Please check the JSON syntax."
                )
        return cls._prompts_data
    
    @classmethod
    def _should_reload(cls) -> bool:
        """Check if prompts file has been modified."""
        try:
            current_modified = os.path.getmtime(PROMPTS_FILE)
            return current_modified > cls._last_modified
        except OSError:
            return False
    
    @classmethod
    def get_system_message(cls, node_name: str, **kwargs) -> str:
        """Get system message for a specific node.
        
        Args:
            node_name: Name of the node (e.g., 'generate_query_or_respond')
            **kwargs: Variables to format into the template
            
        Returns:
            Formatted system message string
        """
        data = cls._load_prompts()
        system_messages = data.get('system_messages', {})
        
        if node_name not in system_messages:
            raise KeyError(
                f"System message not found for node '{node_name}'.\n"
                f"Available nodes: {list(system_messages.keys())}"
            )
        
        # Auto-inject today's date if not provided
        if 'today_date' not in kwargs:
            kwargs['today_date'] = datetime.now().strftime('%Y-%m-%d')
        
        template = system_messages[node_name]['template']
        return template.format(**kwargs)
    
    @classmethod
    def get_prompt(cls, prompt_name: str, **kwargs) -> str:
        """Get prompt template for a specific use case.
        
        Args:
            prompt_name: Name of the prompt (e.g., 'grade_documents')
            **kwargs: Variables to format into the template
            
        Returns:
            Formatted prompt string
        """
        data = cls._load_prompts()
        prompts = data.get('prompts', {})
        
        if prompt_name not in prompts:
            raise KeyError(
                f"Prompt not found: '{prompt_name}'.\n"
                f"Available prompts: {list(prompts.keys())}"
            )
        
        template = prompts[prompt_name]['template']
        return template.format(**kwargs)
    
    @classmethod
    def get_retriever_tool_config(cls) -> Dict[str, str]:
        """Get retriever tool configuration.
        
        Returns:
            Dict with 'name' and 'description' keys
        """
        data = cls._load_prompts()
        return data.get('retriever_tool', {
            'name': 'retrieve_documents',
            'description': 'Search and return information from ingested documents.'
        })
    
    @classmethod
    def get_settings(cls) -> Dict[str, Any]:
        """Get default settings.
        
        Returns:
            Dict with model, temperature, k, streaming settings
        """
        data = cls._load_prompts()
        return data.get('settings', {
            'default_model': 'gpt-4o-mini',
            'default_temperature': 0,
            'default_k': 5,
            'streaming_enabled': True
        })
    
    @classmethod
    def reload(cls) -> None:
        """Force reload prompts from file (useful for testing)."""
        cls._prompts_data = None
        cls._last_modified = 0
    
    @classmethod
    def get_hitl_settings(cls) -> Dict[str, Any]:
        """Get HITL (Human-in-the-Loop) configuration settings.
        
        Returns:
            Dict with HITL settings including enabled, require_approval_for, etc.
        """
        data = cls._load_prompts()
        return data.get('hitl_settings', {
            'enabled': False,
            'require_approval_for': [],
            'multi_step_approval_for': [],
            'review_documents': False,
            'validate_inputs': False,
            'use_node_level_gate': False,
            'timeout_seconds': 300
        })
    
    @classmethod
    def should_require_approval(cls, tool_name: str) -> bool:
        """Check if a tool requires human approval.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if the tool requires approval, False otherwise
        """
        hitl = cls.get_hitl_settings()
        if not hitl.get('enabled', False):
            return False
        return tool_name in hitl.get('require_approval_for', [])
    
    @classmethod
    def should_use_multi_step(cls, tool_name: str) -> bool:
        """Check if a tool should use multi-step approval.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if the tool should use multi-step approval, False otherwise
        """
        hitl = cls.get_hitl_settings()
        if not hitl.get('enabled', False):
            return False
        return tool_name in hitl.get('multi_step_approval_for', [])
    
    @classmethod
    def should_validate_inputs(cls) -> bool:
        """Check if input validation is enabled.
        
        Returns:
            True if input validation is enabled, False otherwise
        """
        hitl = cls.get_hitl_settings()
        if not hitl.get('enabled', False):
            return False
        return hitl.get('validate_inputs', False)
    
    @classmethod
    def should_review_documents(cls) -> bool:
        """Check if document review is enabled.
        
        Returns:
            True if document review is enabled, False otherwise
        """
        hitl = cls.get_hitl_settings()
        if not hitl.get('enabled', False):
            return False
        return hitl.get('review_documents', False)
    
    @classmethod
    def should_use_node_level_gate(cls) -> bool:
        """Check if node-level approval gate is enabled.
        
        Returns:
            True if node-level gate is enabled, False otherwise
        """
        hitl = cls.get_hitl_settings()
        if not hitl.get('enabled', False):
            return False
        return hitl.get('use_node_level_gate', False)


# Convenience functions
def get_system_message(node_name: str, **kwargs) -> str:
    """Get system message for a node."""
    return PromptLoader.get_system_message(node_name, **kwargs)


def get_prompt(prompt_name: str, **kwargs) -> str:
    """Get prompt template."""
    return PromptLoader.get_prompt(prompt_name, **kwargs)


def get_retriever_tool_config() -> Dict[str, str]:
    """Get retriever tool configuration."""
    return PromptLoader.get_retriever_tool_config()


def get_settings() -> Dict[str, Any]:
    """Get default settings."""
    return PromptLoader.get_settings()


def get_hitl_settings() -> Dict[str, Any]:
    """Get HITL configuration settings."""
    return PromptLoader.get_hitl_settings()


def should_require_approval(tool_name: str) -> bool:
    """Check if a tool requires human approval."""
    return PromptLoader.should_require_approval(tool_name)


def should_use_multi_step(tool_name: str) -> bool:
    """Check if a tool should use multi-step approval."""
    return PromptLoader.should_use_multi_step(tool_name)


def should_validate_inputs() -> bool:
    """Check if input validation is enabled."""
    return PromptLoader.should_validate_inputs()


def should_review_documents() -> bool:
    """Check if document review is enabled."""
    return PromptLoader.should_review_documents()


def should_use_node_level_gate() -> bool:
    """Check if node-level approval gate is enabled."""
    return PromptLoader.should_use_node_level_gate()

