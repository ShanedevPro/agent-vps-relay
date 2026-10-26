"""OS-owned workers only. There is deliberately no nohup/thread fallback."""
import getpass
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import sys
import xml.etree.ElementTree as ET

from .core import RelayError, require, run, write_private


class Scheduler:
    def __init__(self, system=None):
        self.system = system or platform.system()

    def launch(self, label, directory, runtime, *, interpreter=None):
        require(label.startswith("agent-vps-relay-") and all(c.isalnum() or c == "-" for c in label),
                "invalid_job", "Invalid owned job identifier.")
        argv = [interpreter or sys.executable, str(runtime / "relay_agent/worker.py"), str(directory)]
        if self.system == "Darwin":
            job = {"Label": label, "ProgramArguments": argv, "RunAtLoad": True,
                   "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 2,
                   "StandardOutPath": str(directory / "worker.stdout"),
                   "StandardErrorPath": str(directory / "worker.stderr")}
            path = directory / "job.plist"
            write_private(path, plistlib.dumps(job), raw=True)
            run(["launchctl", "bootstrap", "gui/" + str(os.getuid()), str(path)])
        elif self.system == "Linux":
            run(["systemd-run", "--user", "--unit=" + label, "--property=Restart=on-failure",
                 "--property=RestartSec=2", *argv])
        elif self.system == "Windows":
            ns = "http://schemas.microsoft.com/windows/2004/02/mit/task"
            ET.register_namespace("", ns)
            def element(parent, tag, text=None):
                e = ET.SubElement(parent, "{" + ns + "}" + tag)
                e.text = text
                return e
            task = ET.Element("{" + ns + "}Task", {"version": "1.2"})
            principals = element(task, "Principals")
            principal = element(principals, "Principal")
            element(principal, "UserId", getpass.getuser())
            element(principal, "LogonType", "InteractiveToken")
            element(principal, "RunLevel", "LeastPrivilege")
            settings = element(task, "Settings")
            element(settings, "DisallowStartIfOnBatteries", "false")
            element(settings, "StopIfGoingOnBatteries", "false")
            element(settings, "ExecutionTimeLimit", "PT20M")
            restart = element(settings, "RestartOnFailure")
            element(restart, "Interval", "PT1M")
            element(restart, "Count", "3")
            action = element(element(task, "Actions"), "Exec")
            element(action, "Command", argv[0])
            element(action, "Arguments", subprocess.list2cmdline(argv[1:]))
            path = directory / "task.xml"
            write_private(path, ET.tostring(task, encoding="utf-16", xml_declaration=True), raw=True)
            run(["schtasks", "/Create", "/TN", label, "/XML", str(path)])
            try:
                run(["schtasks", "/Run", "/TN", label])
            except RelayError:
                run(["schtasks", "/Delete", "/TN", label, "/F"], check=False)
                raise
        else:
            raise RelayError("needs_user_action", "No verified OS scheduler adapter; do not automate network takeover.")

    def cancel(self, label):
        require(label.startswith("agent-vps-relay-") and all(c.isalnum() or c == "-" for c in label),
                "invalid_job", "Refusing to operate on an unrelated OS job.")
        if self.system == "Darwin":
            run(["launchctl", "bootout", "gui/" + str(os.getuid()) + "/" + label], check=False)
            absent = run(["launchctl", "print", "gui/" + str(os.getuid()) + "/" + label], check=False).returncode != 0
        elif self.system == "Linux":
            run(["systemctl", "--user", "stop", label + ".service"], check=False)
            absent = run(["systemctl", "--user", "is-active", "--quiet", label + ".service"], check=False).returncode != 0
        elif self.system == "Windows":
            run(["schtasks", "/End", "/TN", label], check=False)
            run(["schtasks", "/Delete", "/TN", label, "/F"], check=False)
            absent = run(["schtasks", "/Query", "/TN", label], check=False).returncode != 0
        else:
            raise RelayError("needs_user_action", "Cannot verify recovery-job retirement on this OS.")
        require(absent, "job_retirement_failed", "The owned recovery job is still present or active; inspect it locally before declaring retirement.")
