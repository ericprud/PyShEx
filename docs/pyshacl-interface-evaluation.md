# Is the pySHACL interface appropriate for PyShEx?

*Evaluation — RDFLib-org migration track. Companion to `all-rdf-interface.md`.*

pySHACL's public interface, reduced to its essentials:

```python
conforms, results_graph, results_text = pyshacl.validate(
    data_graph,                 # rdflib.Graph (or path/URL)
    shacl_graph=None,           # the shapes; defaults to shapes found in data_graph
    ont_graph=None,             # extra ontology to mix in
    inference="rdfs"|"owlrl"|None,
    abort_on_first=False, allow_warnings=False, ...
)
```

Its virtues: one module-level call; graphs in, graphs out; a three-part return whose
first element answers the question most callers ask; results additionally available
as an RDF `sh:ValidationReport` for downstream tooling. As the only widely deployed
RDF validator in the Python ecosystem, it also defines user expectations: an
RDFLib-org PyShEx that *feels* like pySHACL costs new users nothing to learn.

## Where the analogy holds

- **Module-level `validate(...)`** rather than mandatory object construction.
  PyShEx's `ShExEvaluator` is fine as the configurable engine underneath, but the
  one-shot function is the interface people reach for and quote in READMEs.
- **The return triple `(conforms, results_graph, results_text)`.** ShEx has natural
  values for all three: `conforms` = every association conformant; `results_graph` =
  the result shape map of `all-rdf-interface.md` (this is exactly where the all-RDF
  work makes the pySHACL convention *available* to PyShEx — without an RDF results
  vocabulary there is no honest `results_graph` to return); `results_text` = the
  per-association reasons PyShEx already produces.
- **Graphs (or paths/URLs) accepted for every RDF-valued argument**, with format
  sniffing. pySHACL's tolerant input handling is a real usability win.

## Where the analogy breaks: targeting

The structural difference is not cosmetic. SHACL shapes carry their own targets
(`sh:targetClass`, `sh:targetNode`, …), so `validate(data, shapes)` is a complete
question. ShEx deliberately separates *what to check* (the schema) from *what to
check it against* (the shape map); apart from `start`, a ShEx schema says nothing
about which nodes to validate. The shape map is not configuration — it is one of the
three first-class inputs, and result shape maps feed back in as input shape maps
(the composition UniProt's pipelines rely on).

Consequences for the interface:

1. **A two-argument `validate(data, schema)` must not be the headline signature.**
   Defaulting the shape map away (e.g. PyShEx's current "all non-bnode subjects
   against START") is a nonstandard convenience that misrepresents ShEx semantics
   and produces surprising O(nodes × shapes) runs on large graphs. It can survive as
   an explicit convenience (`start_everywhere=True` or a documented default *when
   the schema has a `start`*), never as the implicit behavior.
2. **The shape map belongs in the positional signature:**

   ```python
   conforms, results_graph, results_text = pyshex.validate(
       data_graph,
       shex_schema,      # ShExC text | ShExJ | ShExR graph
       shape_map,        # shex:ShapeMap graph | "node@shape" text | FixedShapeMap
   )
   ```

   Three positional arguments (data, schema, map) — same *style* as pySHACL, honest
   about ShEx's arity. The ShapeMap-spec compact syntax (`ex:obs1@ex:Observation`)
   should be accepted as text alongside the RDF form, mirroring how pySHACL accepts
   both parsed and serialized shapes.
3. **Arguments with no ShEx meaning should not be aped.** `inference=` and
   `ont_graph=` encode SHACL-community practice (pre-inference then validate). ShEx
   has no inference step; importing those parameters would suggest semantics PyShEx
   does not have. If a user wants RDFS closure first, they can do it to the data
   graph themselves.
4. **`sh:ValidationReport` is not the right output vocabulary.** The result shape
   map is (it round-trips as input). An optional lossy `to_shacl_report()` bridge
   for dashboard interop is defensible; making SHACL's report the primary output
   would bury the round-trip property.

## Verdict

Adopt pySHACL's *calling conventions* — module-level `validate`, permissive input
coercion, the `(conforms, results_graph, results_text)` return — and reject its
*arity*. The aesthetic rule: PyShEx should feel like pySHACL wherever ShEx and SHACL
agree (RDF in, verdict + RDF + text out), and visibly differ exactly where the
languages differ (the shape map as a first-class third input). The all-RDF interface
is what makes the convergence possible: with schema (ShExR), shape map, and result
shape map all defined as RDF, `pyshex.validate(data, schema, shape_map)` and
`pyshacl.validate(data, shapes)` become recognizably the same *kind* of function,
with the extra argument carrying ShEx's extra idea rather than hiding it.
