import sys
import os
from unittest.mock import MagicMock

# Only mock snakemake for unit tests; integration tests need the real module.
_integration = os.environ.get('FMA_INTEGRATION', '').lower() in ('1', 'true', 'yes')
if not _integration and 'snakemake' not in sys.modules:
    sys.modules['snakemake'] = MagicMock()
