"""
System Configuration Service for Contract AI System v2.0
Manages system modes, enabled modules, and runtime configuration
"""
from typing import Dict, Any, List, Optional
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, update
import logging
import json

logger = logging.getLogger(__name__)


class SystemMode(str, Enum):
    """System operation modes"""
    FULL_LOAD = "full_load"          # All modules run in parallel
    SEQUENTIAL = "sequential"         # Modules run one by one (economy mode)
    MANUAL = "manual"                 # User selects which modules to enable


class PipelineModule(str, Enum):
    """Available pipeline modules"""
    OCR = "ocr"
    LEVEL1_EXTRACTION = "level1_extraction"
    LLM_EXTRACTION = "llm_extraction"
    RAG_FILTER = "rag_filter"
    VALIDATION = "validation"
    EMBEDDING_GENERATION = "embedding_generation"


class SystemConfigService:
    """
    Service for managing system configuration.

    Features:
    - Get/set system operation mode
    - Enable/disable pipeline modules
    - Track module execution status (for sequential mode)
    - Update RAG and Router settings dynamically
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize System Config Service.

        Args:
            db_session: Async database session
        """
        self.db = db_session
        logger.info("SystemConfigService initialized")

    async def get_system_mode(self) -> SystemMode:
        """
        Get current system operation mode.

        Returns:
            Current SystemMode
        """
        config = await self._get_config("system_mode")
        if config:
            mode_value = config.get("mode", "full_load")
            try:
                return SystemMode(mode_value)
            except ValueError:
                logger.warning(f"Invalid system mode: {mode_value}, defaulting to FULL_LOAD")
                return SystemMode.FULL_LOAD
        return SystemMode.FULL_LOAD

    async def set_system_mode(
        self,
        mode: SystemMode,
        updated_by: Optional[str] = None
    ):
        """
        Set system operation mode.

        Args:
            mode: New system mode
            updated_by: User ID who made the change
        """
        await self._update_config(
            "system_mode",
            {"mode": mode.value},
            updated_by=updated_by
        )
        logger.info(f"System mode set to: {mode.value} (by {updated_by or 'system'})")

    async def get_enabled_modules(self) -> List[PipelineModule]:
        """
        Get list of enabled pipeline modules.

        Returns:
            List of enabled modules
        """
        config = await self._get_config("enabled_modules")
        if config:
            module_names = config.get("modules", [])
            enabled_modules = []
            for name in module_names:
                try:
                    enabled_modules.append(PipelineModule(name))
                except ValueError:
                    logger.warning(f"Invalid module name: {name}")
            return enabled_modules

        # Default: all modules enabled
        return list(PipelineModule)

    async def set_enabled_modules(
        self,
        modules: List[PipelineModule],
        updated_by: Optional[str] = None
    ):
        """
        Set enabled pipeline modules (for manual mode).

        Args:
            modules: List of modules to enable
            updated_by: User ID who made the change
        """
        module_names = [m.value for m in modules]
        await self._update_config(
            "enabled_modules",
            {"modules": module_names},
            updated_by=updated_by
        )
        logger.info(f"Enabled modules updated: {module_names} (by {updated_by or 'system'})")

    async def is_module_enabled(self, module: PipelineModule) -> bool:
        """
        Check if a specific module is enabled.

        Args:
            module: Module to check

        Returns:
            True if module is enabled
        """
        mode = await self.get_system_mode()

        if mode == SystemMode.FULL_LOAD:
            # All modules always enabled in full load mode
            return True

        elif mode == SystemMode.MANUAL:
            # Check manual configuration
            enabled_modules = await self.get_enabled_modules()
            return module in enabled_modules

        elif mode == SystemMode.SEQUENTIAL:
            # Check sequential execution state
            return await self._check_sequential_module(module)

        return False

    async def _check_sequential_module(self, module: PipelineModule) -> bool:
        """
        Check if module should run in sequential mode.

        Sequential logic:
        - Modules execute in order: OCR → Level1 → LLM → RAG → Validation → Embedding
        - Only one module runs at a time
        - Current module from system_config (sequential_current_module)

        Args:
            module: Module to check

        Returns:
            True if this module should run now
        """
        config = await self._get_config("sequential_state")
        if not config:
            # Initialize sequential state
            await self._update_config("sequential_state", {
                "current_module": PipelineModule.OCR.value,
                "completed_modules": []
            })
            return module == PipelineModule.OCR

        current_module = config.get("current_module")
        return module.value == current_module

    async def advance_sequential_module(self, completed_module: PipelineModule):
        """
        Advance to next module in sequential mode.

        Args:
            completed_module: Module that just completed
        """
        config = await self._get_config("sequential_state") or {}
        completed_modules = config.get("completed_modules", [])
        completed_modules.append(completed_module.value)

        # Determine next module
        module_order = [
            PipelineModule.OCR,
            PipelineModule.LEVEL1_EXTRACTION,
            PipelineModule.LLM_EXTRACTION,
            PipelineModule.RAG_FILTER,
            PipelineModule.VALIDATION,
            PipelineModule.EMBEDDING_GENERATION
        ]

        try:
            current_index = module_order.index(completed_module)
            if current_index < len(module_order) - 1:
                next_module = module_order[current_index + 1]
            else:
                next_module = None  # All modules completed
        except ValueError:
            next_module = None

        await self._update_config("sequential_state", {
            "current_module": next_module.value if next_module else None,
            "completed_modules": completed_modules
        })

        logger.info(f"Sequential mode: {completed_module.value} completed, next: {next_module}")

    async def reset_sequential_state(self):
        """Reset sequential execution state (e.g., for new document)."""
        await self._update_config("sequential_state", {
            "current_module": PipelineModule.OCR.value,
            "completed_modules": []
        })
        logger.info("Sequential state reset")

    async def get_rag_config(self) -> Dict[str, Any]:
        """
        Get RAG configuration.

        Returns:
            RAG config dict
        """
        config = await self._get_config("rag_enabled")
        return config or {
            "enabled": True,
            "top_k": 5,
            "similarity_threshold": 0.7
        }

    async def update_rag_config(
        self,
        enabled: Optional[bool] = None,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        updated_by: Optional[str] = None
    ):
        """
        Update RAG configuration.

        Args:
            enabled: Enable/disable RAG
            top_k: Number of results to retrieve
            similarity_threshold: Minimum similarity score
            updated_by: User ID
        """
        current_config = await self.get_rag_config()

        if enabled is not None:
            current_config["enabled"] = enabled
        if top_k is not None:
            current_config["top_k"] = top_k
        if similarity_threshold is not None:
            current_config["similarity_threshold"] = similarity_threshold

        await self._update_config("rag_enabled", current_config, updated_by=updated_by)
        logger.info(f"RAG config updated: {current_config}")

    async def get_router_config(self) -> Dict[str, Any]:
        """
        Get Smart Router configuration.

        Returns:
            Router config dict
        """
        config = await self._get_config("router_config")
        return config or {
            "default_model": "deepseek-v3",
            "complexity_threshold": 0.8,
            "enable_fallback": True
        }

    async def update_router_config(
        self,
        default_model: Optional[str] = None,
        complexity_threshold: Optional[float] = None,
        enable_fallback: Optional[bool] = None,
        updated_by: Optional[str] = None
    ):
        """
        Update Smart Router configuration.

        Args:
            default_model: Default model to use
            complexity_threshold: Threshold for switching models
            enable_fallback: Enable fallback mechanism
            updated_by: User ID
        """
        current_config = await self.get_router_config()

        if default_model is not None:
            current_config["default_model"] = default_model
        if complexity_threshold is not None:
            current_config["complexity_threshold"] = complexity_threshold
        if enable_fallback is not None:
            current_config["enable_fallback"] = enable_fallback

        await self._update_config("router_config", current_config, updated_by=updated_by)
        logger.info(f"Router config updated: {current_config}")

    async def get_all_config(self) -> Dict[str, Any]:
        """
        Get all system configuration.

        Returns:
            Complete config dict
        """
        result = await self.db.execute(
            select(text("config_key, config_value")).select_from(text("system_config"))
        )
        rows = result.fetchall()

        all_config = {}
        for row in rows:
            all_config[row.config_key] = row.config_value

        return all_config

    async def _get_config(self, config_key: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration value by key.

        Args:
            config_key: Configuration key

        Returns:
            Configuration value (JSONB) or None
        """
        try:
            result = await self.db.execute(
                select(text("config_value")).select_from(text("system_config")).where(
                    text("config_key = :key")
                ),
                {"key": config_key}
            )
            row = result.first()

            if row:
                return row.config_value
            return None

        except Exception as e:
            logger.error(f"Failed to get config '{config_key}': {e}")
            return None

    async def _update_config(
        self,
        config_key: str,
        config_value: Dict[str, Any],
        updated_by: Optional[str] = None
    ):
        """
        Update configuration value.

        Args:
            config_key: Configuration key
            config_value: New value (will be stored as JSONB)
            updated_by: User ID
        """
        try:
            # Check if exists
            existing = await self._get_config(config_key)

            if existing is not None:
                # Update
                await self.db.execute(
                    update(text("system_config")).where(
                        text("config_key = :key")
                    ).values(
                        config_value=config_value,
                        updated_at=text("NOW()"),
                        updated_by=updated_by
                    ),
                    {"key": config_key}
                )
            else:
                # Insert
                await self.db.execute(
                    text(
                        "INSERT INTO system_config (config_key, config_value, updated_by) "
                        "VALUES (:key, :value, :updated_by)"
                    ),
                    {
                        "key": config_key,
                        "value": json.dumps(config_value),
                        "updated_by": updated_by
                    }
                )

            await self.db.commit()
            logger.debug(f"Config '{config_key}' updated")

        except Exception as e:
            logger.error(f"Failed to update config '{config_key}': {e}")
            await self.db.rollback()
            raise


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test_config_service():
        print("SystemConfigService test placeholder")
        print("In production, connect to real database")

        # Example operations:
        # await config_service.set_system_mode(SystemMode.SEQUENTIAL)
        # mode = await config_service.get_system_mode()
        # enabled = await config_service.is_module_enabled(PipelineModule.OCR)

    asyncio.run(test_config_service())
