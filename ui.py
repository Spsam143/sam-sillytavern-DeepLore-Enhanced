import sys
import asyncio
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QComboBox, QCheckBox, QHeaderView
)
from PySide6.QtCore import Qt, Signal, QObject, Slot
import qasync

# ---------------------------------------------------------
# Mock Backend (State Manager)
# ---------------------------------------------------------
class StateManager(QObject):
    pipeline_state_changed = Signal(str)
    ai_status_changed = Signal(str)
    gaps_updated = Signal(list)
    tokens_updated = Signal(int, int) # used, max

    def __init__(self):
        super().__init__()
        self._gaps = [
            {"id": 1, "term": "Bloodchain", "status": "flagged"},
            {"id": 2, "term": "Schism", "status": "resolved"}
        ]

    async def run_pipeline(self):
        self.pipeline_state_changed.emit("Running Phase 1")
        await asyncio.sleep(1)
        self.pipeline_state_changed.emit("Running Phase 2")
        await asyncio.sleep(1)
        self.pipeline_state_changed.emit("Idle")

    async def simulate_gaps(self):
        await asyncio.sleep(2)
        self._gaps.append({"id": 3, "term": "Old King", "status": "flagged"})
        self.gaps_updated.emit(self._gaps)

        await asyncio.sleep(2)
        self.tokens_updated.emit(500, 1000)

# ---------------------------------------------------------
# UI Components
# ---------------------------------------------------------
class StatusPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.setObjectName("statusPanel")

        # Status Row
        row_layout = QHBoxLayout()
        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("statusLabel")

        self.entries_label = QLabel("0 entries indexed")
        self.entries_label.setObjectName("entriesLabel")
        self.mode_label = QLabel("AI Search: Default")
        self.mode_label.setObjectName("modeLabel")

        system_status = QLabel("System Status:")
        system_status.setObjectName("systemStatusLabel")

        row_layout.addWidget(system_status)
        row_layout.addWidget(self.status_label)
        row_layout.addStretch()
        row_layout.addWidget(self.entries_label)
        row_layout.addWidget(self.mode_label)

        # Progress Bars
        self.token_bar = QProgressBar()
        self.token_bar.setValue(0)
        self.token_bar.setFormat("Tokens: %p%")
        self.token_bar.setObjectName("tokenBar")

        self.entries_bar = QProgressBar()
        self.entries_bar.setValue(0)
        self.entries_bar.setFormat("Entries: %p%")
        self.entries_bar.setObjectName("entriesBar")

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.scribe_btn = QPushButton("Scribe")
        self.new_lore_btn = QPushButton("New Lore")
        self.graph_btn = QPushButton("Graph")
        self.reroll_btn = QPushButton("Reroll")

        for btn in (self.refresh_btn, self.scribe_btn, self.new_lore_btn, self.graph_btn, self.reroll_btn):
            btn.setObjectName("actionBtn")
            btn_layout.addWidget(btn)

        layout.addLayout(row_layout)
        layout.addWidget(self.token_bar)
        layout.addWidget(self.entries_bar)
        layout.addLayout(btn_layout)

    @Slot(str)
    def update_pipeline_state(self, state):
        self.status_label.setText(state)

    @Slot(int, int)
    def update_tokens(self, used, max_val):
        self.token_bar.setMaximum(max_val)
        self.token_bar.setValue(used)

class LibrarianUI(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.setObjectName("librarianUI")

        # Toolbar
        toolbar_layout = QHBoxLayout()

        self.flags_btn = QPushButton("Flags")
        self.flags_btn.setCheckable(True)
        self.flags_btn.setChecked(True)
        self.flags_btn.setObjectName("tabBtn")

        self.activity_btn = QPushButton("Activity")
        self.activity_btn.setCheckable(True)
        self.activity_btn.setObjectName("tabBtn")

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Newest", "Frequency", "Urgency"])
        self.sort_combo.setObjectName("sortCombo")

        sort_lbl = QLabel("Sort by:")
        sort_lbl.setObjectName("sortLabel")

        toolbar_layout.addWidget(self.flags_btn)
        toolbar_layout.addWidget(self.activity_btn)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(sort_lbl)
        toolbar_layout.addWidget(self.sort_combo)

        # Select All Bar
        select_all_layout = QHBoxLayout()
        self.select_all_cb = QCheckBox("Toggle select all")
        self.select_all_cb.setObjectName("selectAllCb")
        self.select_count = QLabel("0 selected")
        self.select_count.setObjectName("selectCount")
        select_all_layout.addWidget(self.select_all_cb)
        select_all_layout.addWidget(self.select_count)
        select_all_layout.addStretch()

        # List/Table
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Term", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setObjectName("librarianTable")

        # Actions
        actions_layout = QHBoxLayout()
        self.open_btn = QPushButton("Open")
        self.done_btn = QPushButton("Mark Done")
        self.remove_btn = QPushButton("Remove")

        for btn in (self.open_btn, self.done_btn, self.remove_btn):
            btn.setObjectName("tableActionBtn")
            actions_layout.addWidget(btn)

        # Bottom Toolbar
        bottom_layout = QHBoxLayout()
        self.new_entry_btn = QPushButton("New Entry")
        self.vault_review_btn = QPushButton("Vault Review")

        for btn in (self.new_entry_btn, self.vault_review_btn):
            btn.setObjectName("bottomActionBtn")
            bottom_layout.addWidget(btn)

        # Add to main layout
        layout.addLayout(toolbar_layout)
        layout.addLayout(select_all_layout)
        layout.addWidget(self.table)
        layout.addLayout(actions_layout)
        layout.addLayout(bottom_layout)

    @Slot(list)
    def update_gaps(self, gaps):
        self.table.setRowCount(len(gaps))
        for row, gap in enumerate(gaps):
            self.table.setItem(row, 0, QTableWidgetItem(str(gap["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(gap["term"]))
            self.table.setItem(row, 2, QTableWidgetItem(gap["status"]))

class DrawerUI(QMainWindow):
    def __init__(self, state_manager):
        super().__init__()
        self.setWindowTitle("DeepLore Drawer")
        self.setMinimumSize(600, 800)
        self.setObjectName("drawerUI")

        self.state_manager = state_manager

        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Status Panel (Always visible at top)
        self.status_panel = StatusPanel()
        main_layout.addWidget(self.status_panel)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")

        # Librarian Tab
        self.librarian_ui = LibrarianUI()
        self.tabs.addTab(self.librarian_ui, "Librarian")

        # Dummy Tabs
        self.tabs.addTab(QWidget(), "Injection")
        self.tabs.addTab(QWidget(), "Browse")
        self.tabs.addTab(QWidget(), "Gating")
        self.tabs.addTab(QWidget(), "Tools")

        main_layout.addWidget(self.tabs)

        # Wiring Signals and Slots
        self.state_manager.pipeline_state_changed.connect(self.status_panel.update_pipeline_state)
        self.state_manager.tokens_updated.connect(self.status_panel.update_tokens)
        self.state_manager.gaps_updated.connect(self.librarian_ui.update_gaps)

        # Connect UI buttons to trigger async tasks
        self.status_panel.refresh_btn.clicked.connect(self.on_refresh_clicked)

        # Initialize
        self.state_manager.gaps_updated.emit(self.state_manager._gaps)

    def on_refresh_clicked(self):
        # Fire and forget async task
        asyncio.create_task(self.state_manager.run_pipeline())
        asyncio.create_task(self.state_manager.simulate_gaps())

# ---------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------
DARK_THEME = """
/* Global Settings */
QWidget {
    background-color: #1c1c1e;
    color: #e5e5e5;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* Typography and Labels */
QLabel {
    color: #e5e5e5;
}

#statusLabel {
    font-weight: bold;
    color: #a0a0a0;
}

#systemStatusLabel, #sortLabel {
    color: #a0a0a0;
    font-weight: bold;
}

/* Push Buttons */
QPushButton {
    background-color: #2c2c2e;
    border: 1px solid #3a3a3c;
    border-radius: 5px;
    padding: 6px 12px;
    color: #ffffff;
}

QPushButton:hover {
    background-color: #3a3a3c;
    border: 1px solid #48484a;
}

QPushButton:pressed {
    background-color: #48484a;
}

QPushButton:checked {
    background-color: #0a84ff;
    border: 1px solid #0060df;
    color: white;
}

/* Progress Bars */
QProgressBar {
    border: 1px solid #3a3a3c;
    border-radius: 4px;
    text-align: center;
    background-color: #1c1c1e;
    color: #e5e5e5;
    font-weight: bold;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #0a84ff;
    border-radius: 3px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #3a3a3c;
    border-radius: 5px;
    background-color: #1c1c1e;
}

QTabBar::tab {
    background-color: #2c2c2e;
    border: 1px solid #3a3a3c;
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    color: #a0a0a0;
}

QTabBar::tab:selected {
    background-color: #1c1c1e;
    color: #ffffff;
    font-weight: bold;
}

QTabBar::tab:hover {
    background-color: #3a3a3c;
}

/* Table */
QTableWidget {
    background-color: #1c1c1e;
    alternate-background-color: #2c2c2e;
    gridline-color: #3a3a3c;
    border: 1px solid #3a3a3c;
    border-radius: 5px;
    selection-background-color: #0a84ff;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #2c2c2e;
    color: #a0a0a0;
    padding: 6px;
    border: none;
    border-right: 1px solid #3a3a3c;
    border-bottom: 1px solid #3a3a3c;
    font-weight: bold;
}

/* Combo Box */
QComboBox {
    background-color: #2c2c2e;
    border: 1px solid #3a3a3c;
    border-radius: 5px;
    padding: 4px 8px;
    color: #ffffff;
}

QComboBox::drop-down {
    border-left: 1px solid #3a3a3c;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #2c2c2e;
    border: 1px solid #3a3a3c;
    selection-background-color: #0a84ff;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #e5e5e5;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3a3a3c;
    border-radius: 4px;
    background-color: #1c1c1e;
}

QCheckBox::indicator:checked {
    background-color: #0a84ff;
    border: 1px solid #0060df;
}
"""

# ---------------------------------------------------------
# Main Application Runner
# ---------------------------------------------------------
def run_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    app.setStyleSheet(DARK_THEME)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    state_manager = StateManager()
    window = DrawerUI(state_manager)
    window.show()

    with loop:
        loop.run_forever()

if __name__ == "__main__":
    try:
        run_app()
    except Exception as e:
        print(f"Error: {e}")
