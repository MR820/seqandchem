"""Python client for the SeqChem API — https://seqandchem.com.

    >>> from seqchem import Client
    >>> Client().convert("CCO", to="inchi")["result"]
    'InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3'
"""
from .client import DEFAULT_BASE_URL, Client, SeqChemError

__version__ = "0.1.0"
__all__ = ["Client", "SeqChemError", "DEFAULT_BASE_URL", "__version__"]
