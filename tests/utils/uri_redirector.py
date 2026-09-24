from typing import Union

from rdflib import URIRef


class URIRedirector:
    def __init__(self, base: URIRef, target: str) -> None:
        self.base = base
        # Forward slashes only: generate_base() uses them for the data graph's @base, so a
        # Windows target with backslashes produced focus IRIs that matched no data subject.
        self.target = target.replace('\\', '/')

    def uri_for(self, uri: URIRef) -> Union[URIRef, str]:
        unix_uri = str(uri).replace('\\', '/')
        return unix_uri.replace(self.base, self.target) if unix_uri.startswith(self.base) else uri
