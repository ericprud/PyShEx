"""All-RDF validation interface (experimental).

Schema, shape map, and results as rdflib Graphs -- see docs/all-rdf-interface.md
for the proposed shex: ShapeMap vocabulary this module implements.  The vocabulary
is a proposal under discussion with the ShEx CG and the companion Jena
implementation; the terms may change before this module is declared stable.
"""
from ShExJSG import ShExJ
from rdflib import BNode, Graph, Literal, Namespace, RDF, URIRef

from pyshex.shapemap_structure_and_language.p3_shapemap_structure import START
from pyshex.shex_evaluator import EvaluationResult, ShExEvaluator

SHEX = Namespace("http://www.w3.org/ns/shex#")


def shape_map_from_graph(g: Graph) -> list[tuple[URIRef | BNode | Literal, URIRef | type(START)]]:
    """ Read every shex:ShapeAssociation in ``g`` into (node, shape) pairs.

    Any resource carrying both shex:node and shex:shape is treated as an
    association, whether or not it hangs off a shex:ShapeMap.  shex:Start maps to
    the schema's start shape.
    """
    associations = []
    for a in sorted(set(g.subjects(SHEX.node, None)), key=str):
        node = g.value(a, SHEX.node)
        shape = g.value(a, SHEX.shape)
        if shape is None:
            raise ValueError(f"Shape association {a} has shex:node but no shex:shape")
        associations.append((node, START if shape == SHEX.Start else shape))
    if not associations:
        raise ValueError("No shex:ShapeAssociation (shex:node + shex:shape) found in shape map graph")
    return associations


def result_shape_map(results: list[EvaluationResult], target: Graph | None = None) -> Graph:
    """ Render evaluation results as a shex:ShapeMap graph (a result shape map).

    Result shape maps round-trip: the graph produced here is a valid input to
    shape_map_from_graph (status/reason are ignored on input per the ShapeMap spec).
    """
    g = target if target is not None else Graph()
    g.bind("shex", SHEX)
    m = BNode()
    g.add((m, RDF.type, SHEX.ShapeMap))
    for r in results:
        a = BNode()
        g.add((m, SHEX.association, a))
        g.add((a, RDF.type, SHEX.ShapeAssociation))
        g.add((a, SHEX.node, r.focus))
        start_is_start = r.start is START or isinstance(r.start, START)
        g.add((a, SHEX.shape, SHEX.Start if start_is_start else URIRef(str(r.start))))
        g.add((a, SHEX.status, SHEX.conformant if r.result else SHEX.nonconformant))
        if r.reason:
            g.add((a, SHEX.reason, Literal(r.reason)))
    return g


def schema_from_shexr(g: Graph) -> ShExJ.Schema:
    """ ShExR (schema-as-RDF) -> ShExJ.  Not yet implemented: the direct graph
    walk is specified in docs/all-rdf-interface.md and lands once the ShapeMap
    vocabulary discussion settles the reference-vs-definition conventions. """
    raise NotImplementedError(
        "ShExR ingestion is pending the vocabulary discussion -- see docs/all-rdf-interface.md")


def validate_graph(data: Graph,
                   schema: "Graph | ShExJ.Schema | str",
                   shape_map: Graph) -> Graph:
    """ Validate ``data`` against ``schema`` for every association in ``shape_map``.

    :param data: the data graph
    :param schema: ShExC or ShExJ text, a parsed ShExJ.Schema, or a Graph holding
        ShExR (the latter awaits schema_from_shexr)
    :param shape_map: Graph holding shex:ShapeAssociations
    :return: Graph holding the result shape map
    """
    if isinstance(schema, Graph):
        schema = schema_from_shexr(schema)
    evaluator = ShExEvaluator(rdf=data, schema=schema)
    results: list[EvaluationResult] = []
    for node, shape in shape_map_from_graph(shape_map):
        results.extend(evaluator.evaluate(focus=node, start=shape))
    return result_shape_map(results)
