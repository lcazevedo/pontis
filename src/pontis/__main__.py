# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point for ``python -m pontis``."""

import sys

from pontis.app import main

if __name__ == "__main__":
    sys.exit(main())
