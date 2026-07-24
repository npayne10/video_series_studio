"""User interface for inspecting and enabling VSCS plugins."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vscs.infrastructure.plugins import PluginError, PluginManager, PluginState


class PluginManagerDialog(QDialog):
    """Display discovered plugins and allow enable or disable actions."""

    def __init__(self, manager: PluginManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Plugin Manager")
        self.resize(680, 420)

        self.plugin_list = QListWidget()
        self.details = QLabel("Select a plugin to view details.")
        self.details.setWordWrap(True)
        self.toggle_button = QPushButton("Enable / Disable")
        self.refresh_button = QPushButton("Refresh")

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.toggle_button)
        buttons.addStretch()

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.plugin_list)
        layout.addWidget(self.details)
        layout.addLayout(buttons)
        layout.addWidget(close_buttons)

        self.plugin_list.currentItemChanged.connect(self._show_details)
        self.toggle_button.clicked.connect(self._toggle_selected)
        self.refresh_button.clicked.connect(self._refresh)
        self._populate()

    def _populate(self) -> None:
        self.plugin_list.clear()
        for plugin_id, record in self.manager.plugins.items():
            item = QListWidgetItem(f"{record.manifest.name} — {record.state.value}")
            item.setData(256, plugin_id)
            self.plugin_list.addItem(item)
        self.toggle_button.setEnabled(bool(self.manager.plugins))
        if self.plugin_list.count():
            self.plugin_list.setCurrentRow(0)

    def _show_details(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self.details.setText("No plugin selected.")
            return
        record = self.manager.plugins[str(current.data(256))]
        capabilities = ", ".join(record.manifest.capabilities) or "None"
        error = f"\nError: {record.error}" if record.error else ""
        self.details.setText(
            f"ID: {record.manifest.id}\nVersion: {record.manifest.version}\n"
            f"Author: {record.manifest.author or 'Unknown'}\nCapabilities: {capabilities}{error}"
        )

    def _toggle_selected(self) -> None:
        item = self.plugin_list.currentItem()
        if item is None:
            return
        plugin_id = str(item.data(256))
        record = self.manager.plugins[plugin_id]
        try:
            if record.state is PluginState.DISABLED:
                self.manager.enable(plugin_id)
            else:
                self.manager.disable(plugin_id)
        except PluginError as exc:
            QMessageBox.critical(self, "Plugin Error", str(exc))
        self._populate()

    def _refresh(self) -> None:
        self.manager.shutdown()
        self.manager.discover()
        self.manager.load_enabled()
        self._populate()
