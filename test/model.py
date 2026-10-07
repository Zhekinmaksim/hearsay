"""Scripted model for the offline run.

This is not a simulator of consensus. It is a way to drive the state machine,
the money and the cascade into every branch on purpose, without waiting on
Bradbury. Each round is identified by wording the contract itself produces, so
a test can make the two framings disagree, or make one of them unreadable, and
see what the contract does with that.

Values a test can set:

    support        True | False | None | (framing1, framing2)
    needs_premise  True when the claim only stands with a live premise
    conflict  None | (entry_id) | "unreadable"
    defeats   True | False | None | (stage_a, stage_b)

None means the round comes back unreadable, which is not the same as a clean
negative and must not be treated as one.
"""

import json
import re

UNREADABLE = "I am unable to answer that."


class ScriptedModel:
    def __init__(self):
        self.support = True
        self.conflict = None
        self.defeats = False
        self.needs_premise = False
        self.seen = []

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _has_premise(prompt):
        """True when the PREMISES block carries at least one live claim.

        The block is written by the contract from the supports that are still
        admitted, so an empty one means everything this entry leaned on has
        been thrown out.
        """
        return re.search(r"^\[\d+\] ", prompt, re.M) is not None

    @staticmethod
    def _pick(value, framing):
        if isinstance(value, tuple):
            return value[0] if framing == 1 else value[1]
        return value

    # ---------------------------------------------------------------- entry

    def __call__(self, prompt):
        self.seen.append(prompt)

        if '"supported"' in prompt:
            framing = 1 if "directly and unambiguously entail" in prompt else 2
            # `needs_premise` models the claim that only stands on top of
            # something the memory already holds. It is the only way to test the
            # cascade honestly: with a flat support flag, a tainted entry whose
            # page has not changed always comes back, and a rejudge decides
            # nothing at all.
            if self.needs_premise and not self._has_premise(prompt):
                return json.dumps({"supported": False})
            answer = self._pick(self.support, framing)
            if answer is None:
                return UNREADABLE
            return json.dumps({"supported": bool(answer)})

        if '"conflicts"' in prompt:
            if self.conflict == "unreadable":
                return UNREADABLE
            if self.conflict is None:
                return json.dumps({"conflicts": False, "entry_id": -1})
            return json.dumps({"conflicts": True, "entry_id": int(self.conflict)})

        if '"defeats"' in prompt:
            stage = 1 if "actually visible in this source" in prompt else 2
            answer = self._pick(self.defeats, stage)
            if answer is None:
                return UNREADABLE
            return json.dumps({"defeats": bool(answer)})

        raise RuntimeError("scripted model saw an unrecognised prompt")
