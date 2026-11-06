import json
from pathlib import Path

from FastMitoAssembler import util


BASE_DIR = Path(__file__).resolve().parent
MAIN_SMK = BASE_DIR.joinpath('smk', 'main.smk')
DEFAULT_CONFIG_FILE = BASE_DIR.joinpath('smk', 'config.yaml')
DEFAULT_OPTION_FILE = BASE_DIR.joinpath('smk', 'options.yaml')
DEFAULT_CONFIG = util.read_yaml(DEFAULT_CONFIG_FILE)
DEFAULT_OPTIONS = util.read_yaml(DEFAULT_OPTION_FILE)

BASE_DIR = Path(__file__).resolve().parent
VERSION = json.load(BASE_DIR.joinpath('version.json').open())
__version__ = VERSION['version']

CITATION = (
    'Yang D, Zeng S, Wang Z, Zhang Y, Yang D, Glasby CJ, Hwang J-S, Cai L (2024) '
    'Molecular systematics of Perinereis and an investigation of the status and relationships '
    'of the cultured species Perinereis wilsoni Glasby & Hsieh, 2006 (Annelida, Nereididae). '
    'Zoosystematics and Evolution 100(4): 1297-1314. https://doi.org/10.3897/zse.100.127201'
)

BANNER = BASE_DIR.joinpath('banner.txt').read_text().format(version=__version__)