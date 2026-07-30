"""
Implementation of `5.7 Semantic Actions <http://shex.io/shex-semantics/#semantic-actions>`_

Implements the `Test extension <http://shex.io/extensions/Test/>`_: ``print(...)``
records its argument and succeeds, ``fail(...)`` records its argument and fails.
Per the extension definition, string arguments are stripped of their delimiters
and the two sanctioned escape sequences (``\\\\`` and ``\\"``) are decoded; the
``s``, ``p`` and ``o`` particles resolve to the corresponding component of the
matched triple.  Semantic actions for all other extensions are ignored.
"""
import re

from ShExJSG import ShExJ

from pyshex.shape_expressions_language.p5_context import Context
from pyshex.shapemap_structure_and_language.p1_notation_and_terminology import RDFGraph

TEST_EXTENSION = "http://shex.io/extensions/Test/"

# The Test directive grammar, from http://shex.io/extensions/Test/#parsing
test_pattern = re.compile(r'^ *(fail|print) *\( *(?:("(?:[^\\"]|\\\\|\\")*")|([spo])) *\) *$')


def semActsSatisfied(acts: list[ShExJ.SemAct] | None, cntxt: Context, matched: RDFGraph | None = None) -> bool:
    """ `5.7.1 Semantic Actions Semantics <http://shex.io/shex-semantics/#semantic-actions-semantics>`_

    The evaluation semActsSatisfied on a list of SemActs returns success or failure. The evaluation of an
    individual SemAct is implementation-dependent; this implementation evaluates Test extension actions and
    ignores all others.

    :param acts: semantic actions to evaluate
    :param cntxt: evaluation context
    :param matched: the triples matched by the containing expression, when in scope
    """
    return all(evaluate_test_extension(act, cntxt, matched)
               for act in (acts or []) if str(act.name) == TEST_EXTENSION)


def evaluate_test_extension(act: ShExJ.SemAct, cntxt: Context, matched: RDFGraph | None) -> bool:
    """ Evaluate a single Test extension directive, recording its argument in cntxt.semact_prints """
    if act.code is None:
        return True                     # externally supplied code is not implemented
    m = test_pattern.match(str(act.code))
    if m is None:
        cntxt.fail_reason = f"{TEST_EXTENSION}: invocation error on: {act.code}"
        return False
    if m.group(2) is not None:
        # strip the delimiters, then decode the sanctioned escapes in a single pass
        arg = re.sub(r'\\([\\"])', r'\1', m.group(2)[1:-1])
    else:
        triple = next(iter(matched), None) if matched is not None else None
        if triple is None:
            cntxt.fail_reason = f"{TEST_EXTENSION}: no triple in scope for: {act.code}"
            return False
        arg = str(triple[{"s": 0, "p": 1, "o": 2}[m.group(3)]])
    cntxt.semact_prints.append(arg)
    return m.group(1) == "print"
