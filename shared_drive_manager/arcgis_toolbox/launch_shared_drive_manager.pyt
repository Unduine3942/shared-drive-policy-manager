"""ArcGIS Pro Python Toolbox — launches the Shared Drive Policy Manager GUI."""
from __future__ import annotations

import os
import subprocess
import sys


class Toolbox:
    def __init__(self) -> None:
        self.label = "Shared Drive Policy Manager"
        self.alias = "sharedrive"
        self.tools = [LaunchSharedDriveManager]


class LaunchSharedDriveManager:
    def __init__(self) -> None:
        self.label = "Launch Shared Drive Policy Manager"
        self.description = (
            "Opens the Shared Drive Policy Manager desktop GUI. "
            "The application runs in the ArcGIS Pro Python environment and "
            "requires no additional package installation."
        )
        self.canRunInBackground = False

    def getParameterInfo(self) -> list:
        return []

    def isLicensed(self) -> bool:
        return True

    def updateParameters(self, parameters: list) -> None:
        return

    def updateMessages(self, parameters: list) -> None:
        return

    def execute(self, parameters: list, messages) -> None:
        toolbox_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(toolbox_dir)

        run_app = os.path.join(project_root, "..", "run_app.py")
        run_app = os.path.normpath(run_app)

        if not os.path.isfile(run_app):
            messages.addErrorMessage(
                f"Cannot find run_app.py at: {run_app}\n"
                "Ensure the toolbox is stored inside the Sharedrive_Manager project folder."
            )
            return

        python_exe = sys.executable
        messages.addMessage(f"Python: {python_exe}")
        messages.addMessage(f"Launching: {run_app}")

        try:
            subprocess.Popen(
                [python_exe, run_app],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
            messages.addMessage("Shared Drive Policy Manager launched successfully.")
        except Exception as exc:
            messages.addErrorMessage(f"Failed to launch application: {exc}")
