import sys
from unittest.mock import MagicMock

# snakemake may not be installed in the test environment
if 'snakemake' not in sys.modules:
    sys.modules['snakemake'] = MagicMock()
