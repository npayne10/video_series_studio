"""VSCS application entry point."""

from __future__ import annotations

import logging
import sys
from types import TracebackType

from PySide6.QtWidgets import QApplication, QMessageBox

from vscs.application.universal_validation_refinement import install_universal_validation_refinement
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.infrastructure.configuration import ConfigurationError
from vscs.presentation.widgets import cap_manager as cap_manager_module
from vscs.presentation.widgets.cap_asset_reference_sync import install_cap_asset_reference_sync
from vscs.presentation.widgets.cap_reference_deletion import (
    install_canonical_reference_deletion,
)
from vscs.presentation.widgets.cap_reference_evaluation import (
    install_canonical_image_evaluation,
)
from vscs.presentation.widgets.cap_reference_file_management import (
    install_canonical_reference_file_management,
)
from vscs.presentation.widgets.cap_reference_preview import PreviewCAPManagerWidget
from vscs.presentation.widgets.cap_reference_production_readiness import (
    install_production_readiness_evaluation,
)
from vscs.presentation.widgets.cap_reference_regeneration import (
    install_feedback_regeneration,
)
from vscs.presentation.widgets.cap_reference_semantic_evaluation import (
    install_semantic_image_evaluation,
)
from vscs.presentation.widgets.provider_capability_validation_install import (
    install_provider_capability_validation_workspace,
)

cap_manager_module.CAPManagerWidget = PreviewCAPManagerWidget
install_cap_asset_reference_sync()
install_canonical_reference_file_management()
install_canonical_reference_deletion()
install_canonical_image_evaluation()
install_semantic_image_evaluation()
install_production_readiness_evaluation()
install_feedback_regeneration()
install_universal_validation_refinement()


def _install_exception_hook(logger: logging.Logger) -> None:
    default_hook = sys.excepthook

    def handle_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        if issubclass(exception_type, KeyboardInterrupt):
            default_hook(exception_type, exception, traceback)
            return
        logger.critical(
            "Unhandled exception",
            exc_info=(exception_type, exception, traceback),
        )
        default_hook(exception_type, exception, traceback)

    sys.excepthook = handle_exception


def main() -> int:
    """Launch the VSCS desktop application."""
    application = QApplication(sys.argv)
    application.setApplicationName("Video Series Studio")
    application.setOrganizationName("VSCS")

    try:
        context = build_application_context(
            BootstrapOptions(mode=StartupMode.NORMAL),
        )
    except (ConfigurationError, OSError, RuntimeError, ValueError) as exc:
        QMessageBox.critical(None, "VSCS Startup Error", str(exc))
        return 1

    if context.logger is not None:
        _install_exception_hook(context.logger)
        context.logger.info("Video Series Studio starting")

    if context.environment_messages:
        QMessageBox.warning(
            None,
            "VSCS Environment",
            "VSCS started, but external rendering needs attention:\n\n"
            + "\n".join(f"• {message}" for message in context.environment_messages),
        )

    window = context.create_main_window()
    install_provider_capability_validation_workspace(window)
    window.show()
    exit_code = application.exec()
    if context.logger is not None:
        context.logger.info("Video Series Studio stopped with exit code %s", exit_code)
    context.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
