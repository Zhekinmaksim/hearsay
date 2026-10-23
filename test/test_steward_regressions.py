"""State-machine regressions from the 23 October steward review.

Real Hearsay methods, scripted AI only. EVM custody is tested separately by
Foundry; this fake controls delayed/failed bridge delivery, not Solidity logic.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_tests import (hs, gl, glmod, ScriptedModel, fresh, env, write, as_,
                       WRITER, WRITER2, CHALLENGER, OWNER, WRITE_BOND, CHALLENGE_BOND)


class FakeVault:
    def __init__(self, controller):
        self.owner = controller
        self.receipts = {}
        self.messages = []

    def view(self):
        return self

    def controller(self):
        return self.owner

    def amountOf(self, wid):
        return self.receipts.get(wid, (None, 0))[1]

    def beneficiaryOf(self, wid):
        return self.receipts.get(wid, (None, 0))[0]

    def emit(self, value):
        vault = self

        class Message:
            def deposit(self, wid, who):
                vault.messages.append((wid, who, value))

        return Message()

    def deliver(self, index=0):
        wid, who, value = self.messages[index]
        if wid in self.receipts:
            raise ValueError("already funded")
        self.receipts[wid] = (who, value)


class StewardRegressions(unittest.TestCase):
    def setUp(self):
        self.model = ScriptedModel()
        self.c, _ = fresh(self.model, cascade_depth=1, admit_ttl=1)

    def tearDown(self):
        if hasattr(gl, "evm"):
            del gl.evm

    def chain(self, length=7):
        ids = []
        for i in range(length):
            ids.append(write(self.c, self.model, env("Chain claim %d" % i,
                             supports=ids[-1:])))
        return ids

    def revoke(self, eid):
        self.model.defeats = True
        as_(CHALLENGER, CHALLENGE_BOND)
        cid = self.c.challenge(eid, "The original source defeats this exact claim.")
        as_(CHALLENGER)
        self.c.confirm_challenge(cid)

    def test_rejected_claim_cannot_squat_legitimate_author(self):
        self.model.support = False
        first = write(self.c, self.model, env("Correctable claim", source="https://example.org/gone"))
        before = self.c.get_entry(first)
        self.model.support = True
        second = write(self.c, self.model, env("Correctable claim", source="https://example.org/a"), WRITER2)
        self.assertEqual(self.c.get_entry(first), before)
        self.assertEqual(self.c.get_entry(second)["status"], hs.ADMITTED)
        self.assertEqual(before["bond_state"], hs.SLASHED)
        self.assertEqual(self.c.get_entry(second)["bond_state"], hs.LOCKED)
        self.assertTrue(self.c.solvency()["balanced"])

    def test_same_author_can_correct_evidence_but_not_repeat_it(self):
        self.model.support = False
        first = write(self.c, self.model, env("Corrected claim"))
        with self.assertRaisesRegex(Exception, "unchanged evidence"):
            write(self.c, self.model, env("  corrected   claim  "))
        self.model.support = True
        second = write(self.c, self.model, env("Corrected claim", source="https://example.org/b"))
        self.assertEqual(self.c.get_entry(first)["status"], hs.UNSOURCED)
        self.assertEqual(self.c.get_entry(second)["status"], hs.ADMITTED)

    def test_per_author_limit_cannot_be_exhausted_for_someone_else(self):
        self.model.support = False
        for source in ("a", "b", "c"):
            write(self.c, self.model, env("Bounded retry", source="https://example.org/" + source))
        with self.assertRaisesRegex(Exception, "attempt limit"):
            write(self.c, self.model, env("Bounded retry", source="https://example.org/new"))
        self.model.support = True
        eid = write(self.c, self.model, env("Bounded retry"), WRITER2)
        self.assertEqual(self.c.get_entry(eid)["status"], hs.ADMITTED)

    def test_retry_fetches_new_bytes_and_requires_both_rounds(self):
        self.model.support = False
        first = write(self.c, self.model, env("Fresh support"))
        gl.nondet.web.pages["https://example.org/a"] = "A corrected authoritative source."
        self.model.support = (True, None)
        second = write(self.c, self.model, env("Fresh support"))
        self.assertNotEqual(self.c.get_entry(first)["snapshot_hash"], self.c.get_entry(second)["snapshot_hash"])
        self.assertEqual(self.c.get_entry(second)["status"], hs.INCONCLUSIVE)

    def test_normalized_admitted_claim_still_cannot_be_flooded(self):
        write(self.c, self.model, env("A recorded claim"))
        with self.assertRaisesRegex(Exception, "already recorded"):
            write(self.c, self.model, env(" a  recorded\u200b claim ", source="https://example.org/b"), WRITER2)

    def test_revocation_blocks_deep_unswept_premises_immediately(self):
        ids = self.chain()
        self.revoke(ids[0])
        self.assertEqual(self.c.entries[ids[-1]].status, hs.ADMITTED)  # physical walk stays bounded
        for eid in ids[1:]:
            self.assertEqual(self.c.get_entry(eid)["status"], hs.TAINTED)
            with self.assertRaisesRegex(Exception, "not admitted"):
                write(self.c, self.model, env("Cannot lean on %d" % eid, supports=[eid]))
        self.assertEqual(self.c.get_space(0)["admitted"], 0)
        self.assertEqual(self.c._recent_admitted(0, -1), [])

    def test_expiry_invalidates_the_entire_deep_chain(self):
        ids = self.chain()
        as_(OWNER)
        self.c.expire(ids[0])
        for eid in ids[1:]:
            self.assertEqual(self.c.get_entry(eid)["status"], hs.TAINTED)
        self.assertEqual(self.c._premise_block(ids[-1]), "")

    def test_deferred_batches_finish_and_survivors_are_source_verified(self):
        ids = self.chain()
        self.revoke(ids[0])
        self.model.support = True
        batches = 0
        while self.c.deferred_queue():
            self.assertLess(batches, 30)
            self.assertLessEqual(self.c.process_deferred(1), 1)
            batches += 1
            self.assertTrue(self.c.solvency()["balanced"])
        self.assertEqual(self.c.process_deferred(1), 0)
        self.assertTrue(all(self.c.get_entry(i)["status"] == hs.ADMITTED for i in ids[1:]))
        self.assertEqual(self.c.get_space(0)["admitted"], len(ids) - 1)

    def test_deferred_failed_rejudgement_revokes_and_completes(self):
        ids = self.chain()
        self.revoke(ids[0])
        self.model.support = False
        for _ in range(20):
            if not self.c.deferred_queue():
                break
            self.c.process_deferred(2)
        self.assertEqual(self.c.deferred_queue(), [])
        self.assertTrue(all(self.c.get_entry(i)["status"] == hs.REVOKED for i in ids))

    def test_repairing_ancestor_does_not_silently_readmit_descendants(self):
        ids = self.chain()
        as_(OWNER)
        self.c.expire(ids[0])
        self.c.rejudge(ids[0])
        self.assertEqual(self.c.get_entry(ids[0])["status"], hs.ADMITTED)
        self.assertEqual(self.c.get_entry(ids[-1])["status"], hs.TAINTED)
        # Even a physically unvisited descendant can be rejudged directly.
        self.assertEqual(self.c.rejudge(ids[-1]), hs.ADMITTED)
        self.assertEqual(self.c.get_entry(ids[-1])["supports"], [])

    def test_diamond_and_multiple_invalidations_do_not_double_decrement(self):
        a, b = self.chain(2)
        c = write(self.c, self.model, env("Other branch", supports=[a]))
        d = write(self.c, self.model, env("Shared descendant", supports=[b, c]))
        self.revoke(a)
        for _ in range(12):
            self.c.process_deferred(1)
        self.assertEqual(self.c.get_space(0)["admitted"], 3)
        self.assertEqual(int(self.c.spaces[0].admitted), 3)
        self.assertEqual(self.c.get_entry(d)["status"], hs.ADMITTED)

    def test_deferred_batch_and_round_configuration_are_bounded(self):
        for address in ("", "0x" + "00" * 20):
            with self.assertRaisesRegex(Exception, "nonzero payout vault"):
                hs.Hearsay(address)
        for limit in (0, -1, hs.DEFERRED_BATCH_CAP + 1):
            with self.assertRaisesRegex(Exception, "batch"):
                self.c.process_deferred(limit)
        for rounds in (0, -1, 3, 1000):
            with self.assertRaisesRegex(Exception, "min_rounds"):
                fresh(self.model, min_rounds=rounds)
        for rounds in (1, 2):
            c, _ = fresh(self.model, min_rounds=rounds)
            self.assertEqual(c.get_space(0)["min_rounds"], rounds)

    def test_dependency_fanout_limit_keeps_sweeps_bounded(self):
        a = self.chain(1)[0]
        for i in range(hs.MAX_DEPENDENTS):
            write(self.c, self.model, env("Fanout %d" % i, supports=[a]))
        with self.assertRaisesRegex(Exception, "dependent limit"):
            write(self.c, self.model, env("Too many dependents", supports=[a]))

    def test_removed_edge_cannot_retaint_an_independent_survivor(self):
        a, b = self.chain(2)
        as_(OWNER)
        self.c.expire(a)
        self.c.rejudge(b)
        self.assertEqual(self.c.get_entry(b)["supports"], [])
        self.assertNotIn(b, self.c.get_entry(a)["dependents"])
        self.c.rejudge(a)
        self.revoke(a)
        self.assertEqual(self.c.get_entry(b)["status"], hs.ADMITTED)

    def payout_setup(self):
        a = write(self.c, self.model, env("Payout claim"))
        self.revoke(a)
        self.c.payout_vault = "0x" + "77" * 20
        gl.message.contract_address = glmod.Address("0x" + "88" * 20)
        vault = FakeVault(gl.message.contract_address)

        class EVM:
            @staticmethod
            def contract_interface(cls):
                return lambda address: vault

        gl.evm = EVM()
        self.c.balance = self.c.solvency()["held"]
        as_(CHALLENGER)
        return vault

    def test_emission_is_pending_and_not_misreported_as_delivery(self):
        vault = self.payout_setup()
        held = self.c.solvency()["held"]
        wid = self.c.withdraw()
        self.assertEqual(self.c.withdrawal_count(), 1)
        self.assertEqual(self.c.get_withdrawal(wid)["status"], "PENDING")
        self.assertEqual(self.c.solvency()["held"], held)
        self.assertEqual(self.c.reconcile_withdrawal(wid), "PENDING")
        self.assertEqual(len(vault.messages), 1)
        with self.assertRaisesRegex(Exception, "nothing to withdraw"):
            self.c.withdraw()

    def test_failed_or_delayed_delivery_cannot_use_other_peoples_reserves(self):
        vault = self.payout_setup()
        wid = self.c.withdraw()
        amount = self.c.get_withdrawal(wid)["amount"]
        self.c.balance -= amount  # bridge holds the value; no proof of return
        with self.assertRaisesRegex(Exception, "reserves unavailable"):
            self.c.retry_withdrawal(wid)
        self.assertEqual(self.c.get_withdrawal(wid)["status"], "PENDING")
        self.assertEqual(len(vault.messages), 1)
        self.c.balance += amount  # failure returned value to custody
        self.assertEqual(self.c.retry_withdrawal(wid), "PENDING")
        vault.deliver(1)
        self.assertEqual(self.c.reconcile_withdrawal(wid), "FUNDED")
        self.assertEqual(self.c.solvency()["withdrawing"], 0)
        with self.assertRaisesRegex(Exception, "already funded"):
            vault.deliver(0)  # late first message cannot pay twice

    def test_success_receipt_is_verified_and_reconciliation_is_idempotent(self):
        vault = self.payout_setup()
        wid = self.c.withdraw()
        vault.deliver()
        self.assertEqual(self.c.retry_withdrawal(wid), "FUNDED")
        self.assertEqual(self.c.reconcile_withdrawal(wid), "FUNDED")
        self.assertEqual(len(vault.messages), 1)
        self.assertEqual(self.c.solvency()["withdrawing"], 0)

    def test_wrong_controller_and_forged_receipt_cannot_erase_claims(self):
        vault = self.payout_setup()
        before = self.c.balance_of(CHALLENGER.as_hex)
        vault.owner = WRITER
        with self.assertRaisesRegex(Exception, "controller mismatch"):
            self.c.withdraw()
        self.assertEqual(self.c.balance_of(CHALLENGER.as_hex), before)
        vault.owner = gl.message.contract_address
        wid = self.c.withdraw()
        vault.receipts[wid] = (WRITER, before)
        with self.assertRaisesRegex(Exception, "receipt mismatch"):
            self.c.reconcile_withdrawal(wid)
        self.assertEqual(self.c.get_withdrawal(wid)["status"], "PENDING")
        as_(WRITER)
        with self.assertRaisesRegex(Exception, "only beneficiary"):
            self.c.retry_withdrawal(wid)


if __name__ == "__main__":
    unittest.main()
