import pytest
from rdflib import Graph, Literal, RDF, URIRef

from pyshex.rdf import SHEX, result_shape_map, shape_map_from_graph, validate_graph

EX = "http://example.org/"

SCHEMA = """
PREFIX ex: <http://example.org/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

start = @ex:ObservationShape

ex:ObservationShape {
  ex:status [ "final" "preliminary" ] ;
  ex:value xsd:integer
}
"""

DATA = """
@prefix ex: <http://example.org/> .

ex:obs1 ex:status "final" ; ex:value 42 .
ex:obs2 ex:status "bogus" ; ex:value 42 .
"""

SHAPE_MAP = """
@prefix shex: <http://www.w3.org/ns/shex#> .
@prefix ex: <http://example.org/> .

[] a shex:ShapeMap ;
   shex:association
     [ shex:node ex:obs1 ; shex:shape ex:ObservationShape ] ,
     [ shex:node ex:obs2 ; shex:shape shex:Start ] .
"""


def _status(g: Graph, node: URIRef) -> URIRef:
    for a in g.subjects(SHEX.node, node):
        return g.value(a, SHEX.status)
    raise AssertionError(f"no association for {node}")


def test_validate_graph_round_trip():
    data = Graph().parse(data=DATA, format="turtle")
    shape_map = Graph().parse(data=SHAPE_MAP, format="turtle")

    results = validate_graph(data, SCHEMA, shape_map)

    assert _status(results, URIRef(EX + "obs1")) == SHEX.conformant
    assert _status(results, URIRef(EX + "obs2")) == SHEX.nonconformant
    [reason] = [r for a in results.subjects(SHEX.node, URIRef(EX + "obs2"))
                for r in results.objects(a, SHEX.reason)]
    assert "bogus" in str(reason)

    # a result shape map is a valid input shape map
    pairs = shape_map_from_graph(results)
    assert {str(n) for n, _ in pairs} == {EX + "obs1", EX + "obs2"}

    # the ShapeMap/association envelope is present
    [m] = list(results.subjects(RDF.type, SHEX.ShapeMap))
    assert len(list(results.objects(m, SHEX.association))) == 2


def test_shape_map_requires_shape():
    g = Graph()
    g.add((URIRef(EX + "a"), SHEX.node, URIRef(EX + "n")))
    with pytest.raises(ValueError, match="no shex:shape"):
        shape_map_from_graph(g)


def test_empty_shape_map_rejected():
    with pytest.raises(ValueError, match="No shex:ShapeAssociation"):
        shape_map_from_graph(Graph())


def test_shexr_schema_not_yet_implemented():
    data = Graph().parse(data=DATA, format="turtle")
    shape_map = Graph().parse(data=SHAPE_MAP, format="turtle")
    with pytest.raises(NotImplementedError):
        validate_graph(data, Graph(), shape_map)


def test_literal_focus_node():
    g = Graph()
    a = URIRef(EX + "assoc")
    g.add((a, SHEX.node, Literal("final")))
    g.add((a, SHEX.shape, SHEX.Start))
    [(node, shape)] = shape_map_from_graph(g)
    assert node == Literal("final")
