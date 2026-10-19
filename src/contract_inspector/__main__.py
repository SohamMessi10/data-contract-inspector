"""Allow `python -m contract_inspector ...` as well as the `contract-inspector` command."""

import sys

from contract_inspector.cli import main

sys.exit(main())
