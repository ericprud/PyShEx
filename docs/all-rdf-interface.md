# An all-RDF interface for PyShEx

*Proposal — RDFLib-org migration track. Prompted by Jerven Bolleman (UniProt), whose
toolchains are RDF end-to-end and want to drive ShEx validation without leaving RDF:
schema, shape map, and results all as graphs. A companion implementation for Apache
Jena is underway; this proposes the PyShEx side.*

## Where the three artifacts stand today

A ShEx validation involves four artifacts. In PyShEx's current interfaces
(`ShExEvaluator`, `evaluate_cli`) they arrive in different syntaxes:

| Artifact | Current form(s) | RDF form |
|---|---|---|
| data | `rdflib.Graph` | already RDF |
| schema | ShExC text, ShExJ JSON | **ShExR** — defined; `http://www.w3.org/ns/shex#` vocabulary, JSON-LD context at `https://www.w3.org/ns/shex.jsonld` |
| shape map | `focus=` + `start=` args; internal `FixedShapeMap` of `ShapeAssociation(node, shape)`; sht/JSON shape maps in the test harness | **no RDF vocabulary exists** — proposed below |
| results | `list[EvaluationResult(result, focus, start, reason)]` | **no RDF vocabulary exists** — proposed below (result shape map); EARL covers only the test-suite reporting case |

So the schema side is a solved design (ShExR is exactly "ShExJ read through the
shex.jsonld context") and the work is (a) an RDF vocabulary for shape maps and result
shape maps, (b) ShExR ingestion in PyShEx, (c) an API that closes the loop.

## Proposed vocabulary: ShapeMap terms in `shex:`

The shex.jsonld context currently defines 71 terms, all schema-structural
(`Schema`, `Shape`, `TripleConstraint`, …). None of the ShapeMap-spec notions —
association, node, shape, status, reason, appinfo — are taken, so the natural home is
the same `http://www.w3.org/ns/shex#` namespace (whose context the ShEx CG controls
and can extend):

```turtle
@prefix shex: <http://www.w3.org/ns/shex#> .

# classes
shex:ShapeMap            # a (fixed or result) shape map
shex:ShapeAssociation    # one node↦shape entry

# properties
shex:association         # ShapeMap → ShapeAssociation (repeated)
shex:node                # association → focus node: IRI, bnode, or literal
shex:shape               # association → shape label (IRI/bnode), or shex:Start
shex:status              # result association → shex:conformant | shex:nonconformant
shex:reason              # result association → xsd:string (one per line of the ShapeMap spec's reason)
shex:appinfo             # result association → application-specific node

# individuals
shex:Start               # the START shape reference of the ShapeMap spec
shex:conformant
shex:nonconformant
```

Notes on the choices:

- **`shex:node` may be a literal.** The ShapeMap spec explicitly allows literal focus
  nodes; as the *object* of `shex:node` a literal is unproblematic RDF.
- **`shex:Start`** reifies the spec's `START` token so `shex:shape` is uniformly a
  resource. (`shex:start` — lowercase — already exists as the Schema property and is
  not disturbed.)
- **Result maps are input maps plus `status`/`reason`/`appinfo`** — exactly the
  ShapeMap spec's fixed-map → result-map relationship. A validator's output result
  shape map is therefore itself a valid input shape map, which is the property
  Jerven's pipeline composition needs (validate → filter conformant → feed onward).
- **Ordering.** The ShapeMap spec treats maps as ordered lists; RDF multi-valued
  `shex:association` is unordered. Proposal: unordered by default (validation
  semantics don't depend on order), with a context/`@list` variant only if a concrete
  need appears. This mirrors how `shexTest` manifests already treat entries.
- **Query shape maps** (triple-pattern selectors with `FOCUS`/`_`) are deferred to a
  follow-up. PyShEx already models them internally (`p3_shapemap_structure`:
  `SparqlTriplePattern`, `FOCUS`, `WILD_CARD`), and `shex:predicate`/`shex:object`
  exist in the context for reuse, but fixed maps cover the UniProt use case and the
  FOCUS-marker design deserves its own discussion with the Jena implementation so the
  two agree.

Example fixed shape map:

```turtle
@prefix shex: <http://www.w3.org/ns/shex#> .
@prefix ex: <http://example.org/> .

[] a shex:ShapeMap ;
   shex:association
     [ shex:node ex:obs1 ; shex:shape ex:ObservationShape ] ,
     [ shex:node ex:obs2 ; shex:shape shex:Start ] .
```

and the corresponding result:

```turtle
[] a shex:ShapeMap ;
   shex:association
     [ shex:node ex:obs1 ; shex:shape ex:ObservationShape ;
       shex:status shex:conformant ] ,
     [ shex:node ex:obs2 ; shex:shape shex:Start ;
       shex:status shex:nonconformant ;
       shex:reason "  Testing ex:obs2 against shape ex:ObservationShape\n    No matching triples found for predicate ex:status" ] .
```

## Proposed PyShEx API

A new module `pyshex.rdf` (working name), sitting *beside* the existing interfaces —
this is an additional interface, not a replacement:

```python
from rdflib import Graph
from pyshex.rdf import validate_graph, schema_from_shexr, shape_map_from_graph

result_graph: Graph = validate_graph(
    data,                    # rdflib.Graph
    schema,                  # rdflib.Graph holding ShExR (or a ShExJ.Schema)
    shape_map,               # rdflib.Graph holding a shex:ShapeMap
)                            # → rdflib.Graph holding the result shex:ShapeMap
```

with the composable pieces exposed individually:

- `schema_from_shexr(g: Graph) -> ShExJ.Schema` — ShExR → ShExJ. (The inverse,
  `schema_to_shexr`, falls out of serializing ShExJ as JSON-LD with the shex.jsonld
  context and is worth exposing for round-tripping.)
- `shape_map_from_graph(g: Graph) -> FixedShapeMap` — reuses the existing
  `p3_shapemap_structure` classes unchanged.
- `result_shape_map(results: list[EvaluationResult]) -> Graph`.
- `ShExEvaluator` grows nothing; `validate_graph` wraps it. (If the pySHACL-style
  façade of `docs/pyshacl-interface-evaluation.md` lands, `validate_graph` is its
  all-RDF sibling with the same argument order: data, schema, map.)

### ShExR ingestion

ShExR is by construction "ShExJ seen through shex.jsonld", so the ingestion options
are:

1. **JSON-LD serialization + framing** to recover the nested ShExJ tree, then the
   existing jsg loader. rdflib serializes JSON-LD but does not frame; pyld would be a
   new dependency — runs against the dependency-diet goal of the RDFLib-org
   migration.
2. **Direct graph walk** (recommended): start at the `shex:Schema` node, walk
   `shapes`/`shapeExprs`/`expressions`/… constructing `ShExJ` objects directly. The
   eight `@list`-valued properties in the context (`shapes`, `shapeExprs`,
   `expressions`, `values`, `annotations`, `semActs`, `startActs`, `exclusions`) are
   RDF collections — `rdflib.collection.Collection` reads them; everything else is
   single-valued. Bounded work (~200 lines), no new dependencies, and precise error
   reporting on malformed ShExR.

### Blank-node caveat (needs stating in the docs)

A shape map graph can only reference focus nodes by IRI or literal: a blank node in
the shape-map graph is a *different* blank node from any in the data graph. Options,
in order of preference: (a) put the shape map in the same graph/document as nothing —
just document the restriction; (b) accept skolem IRIs (`.skolemize()`) on both sides;
(c) allow the shape map and data to be handed over as one graph. The same caveat
applies to bnode focus nodes in *results*: PyShEx reports them with the data graph's
labels, which are only meaningful to a consumer holding that same parsed graph.

## Interop notes

- **EARL**: the existing EARL report generation is orthogonal (per-test assertions
  for shexTest); result shape maps are per-node validation outcomes. Both can
  coexist; no need to unify.
- **SHACL validation reports**: a `shex:ShapeMap` result is structurally close to
  `sh:ValidationReport` (`sh:conforms`, per-focus `sh:result`). A lossy
  `to_shacl_report()` bridge would let ShEx results flow into SHACL-report-consuming
  dashboards; cheap to add later, not part of the core proposal.
- **Jena alignment**: the vocabulary above is deliberately minimal so the Jena and
  PyShEx implementations can share it verbatim; the query-shape-map extension should
  be co-designed rather than shipped unilaterally.

## Suggested sequencing

1. Circulate the vocabulary (this document) with the Jena work and the ShEx CG;
   add the terms to shex.jsonld / the `shex:` namespace document once agreed.
2. Implement `shape_map_from_graph` / `result_shape_map` (small, no design risk).
3. Implement `schema_from_shexr` as the direct graph walk, tested by round-tripping
   every ShExJ schema in shexTest through JSON-LD → graph → `schema_from_shexr` and
   comparing ShExJ.
4. Ship `validate_graph` and document it as the RDF-native entry point.
