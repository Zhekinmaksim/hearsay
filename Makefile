.PHONY: test receipts-test checkpoint-test submission-test chain-test bridge-test queue-test submission-signing-test app-test gate-parity parity page live-page vectors replay dry-run assets site gate check lint all

all: lint test receipts-test checkpoint-test submission-test chain-test bridge-test queue-test submission-signing-test app-test dry-run replay assets site parity gate-parity page live-page

test:
	python3 test/run_tests.py

receipts-test:
	python3 -m unittest discover -s test -p 'test_receipts.py'

checkpoint-test:
	python3 -m unittest discover -s test -p 'test_checkpoint.py'

submission-test:
	python3 -m unittest discover -s test -p 'test_submission_publication.py'

chain-test:
	node test/chain-receipt.mjs

bridge-test:
	node test/broadcast.mjs

queue-test:
	node test/queue-progress.mjs

submission-signing-test:
	node test/submission-signing-guard.mjs

app-test:
	node test/app-wallet.mjs
	node test/app-page.mjs

gate-parity:
	node test/gate-parity.mjs

dry-run:
	python3 scripts/dry_run.py

# The mark, the icons and the share card. The card is generated from the corpus
# rather than drawn, so it is a still of the page and not a picture of it.
assets:
	python3 scripts/build_assets.py

site: assets
	python3 scripts/build_site.py

vectors:
	python3 scripts/emit_vectors.py

# Every corpus row, re-derived from the votes it records. Not from its verdict.
replay:
	python3 scripts/replay_corpus.py

# The page reimplements hashing, flattening and verdict assembly in JavaScript.
# This is the only thing that makes a third copy acceptable.
parity: vectors
	node test/parity.mjs

# Drives every control on the built page. Skips itself if jsdom is absent.
page: site
	node test/page.mjs

live-page:
	@if test -f web/live.html; then node test/live-page.mjs; else echo "live run not published yet — skipping live page checks"; fi

# Every exit code the gate can produce, in one pass. `-` because a refusal is a
# non-zero exit and that is the point of the tool, not a build failure.
gate:
	-python3 cli/gate.py gate --entry examples/entries/01-honest-dissolution.json --corpus web/corpus.json --quiet; echo "admitted      -> $$?"
	-python3 cli/gate.py gate --entry examples/entries/09-forgery-real-page-wrong-claim.json --corpus web/corpus.json --quiet; echo "refused       -> $$?"
	-python3 cli/gate.py gate --entry examples/entries/14-flooding-unreadable.json --corpus web/corpus.json --quiet; echo "inconclusive  -> $$?"
	-python3 cli/gate.py gate --entry examples/entries/15-laundering.json --corpus web/corpus.json --quiet; echo "no record     -> $$?"

check:
	python3 cli/entry.py check examples/entries/01-honest-dissolution.json

lint:
	python3 -m py_compile contracts/hearsay.py cli/entry.py cli/gate.py \
		scripts/dry_run.py scripts/build_site.py scripts/replay_corpus.py \
		scripts/collect_receipts.py scripts/diagnose_missing.py scripts/run_live.py \
		scripts/build_deploy.py scripts/publish_live.py scripts/publish_checkpoint.py scripts/enrich_snapshots.py test/run_tests.py test/model.py
