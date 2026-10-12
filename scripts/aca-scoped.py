#!/usr/bin/env python3
"""Pin both ACA resource routing and its Azure CLI token lookup to the configured tenant.

ACA preview.4's resource --subscription does not select the az token tenant.
A process-local shim pins only its get-access-token requests. No global account
or credential cache is changed. The real Azure CLI still performs all auth.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from settings import required, check_account

SUBSCRIPTION = check_account()
az = shutil.which("az")
aca = shutil.which("aca")
if not az or not aca:
    raise SystemExit("Install Azure CLI and ACA CLI first.")
with tempfile.TemporaryDirectory(prefix="aca-scoped-") as directory:
    shim = Path(directory) / "az"
    shim.write_text(f"#!{sys.executable}\n" +
        "import os, sys\nargs=sys.argv[1:]\n" +
        "if args[:2] == ['account', 'get-access-token']:\n" +
        "    for flag in ('--subscription', '-s', '--tenant', '-t'):\n" +
        "        while flag in args:\n            pos=args.index(flag)\n            del args[pos:pos+2]\n" +
        f"    args += ['--subscription', {SUBSCRIPTION!r}]\n" +
        f"os.execv({az!r}, [{az!r}, *args])\n")
    shim.chmod(0o700)
    command = [aca, "--subscription", SUBSCRIPTION, "--resource-group", required("ACA_RESOURCE_GROUP"),
               "--sandbox-group", required("ACA_SANDBOX_GROUP"), "--region", required("ACA_REGION"), *sys.argv[1:]]
    raise SystemExit(subprocess.call(command, env={**os.environ, "PATH": directory + os.pathsep + os.environ["PATH"]}))
